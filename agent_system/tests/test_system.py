import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from vibacappella.agent import MusicTools, run_agents, run_window, SCHEMAS
from vibacappella.arrange import arrange_bars
from vibacappella.cli import create_run
from vibacappella.config import load_config, endpoint_config
from vibacappella.demo import fixture, ScriptedClient
from vibacappella.export import musicxml, midi, audit_notation, read_midi
from vibacappella.llm import Client
from vibacappella.music import empty_score, check_evidence, sound_events, note, fill_rests, tick_to_seconds
from vibacappella.storage import Store, write_json, digest
from vibacappella.validate import validate


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.evidence = fixture(Path(cls.tmp.name)/"fixture.wav")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.store = Store(self.work.name)
        self.cfg = load_config()
        self.score = empty_score(self.evidence, "Test")

    def arrange(self):
        arrange_bars(self.score, self.evidence, 1, 4, vp_style="fill")
        return self.score


class MusicalInvariants(Base):
    def test_complete_source_led_arrangement(self):
        report = validate(self.arrange(), self.evidence)
        self.assertTrue(report["passed"], report)
        roles = {ev["role"] for p in self.score["parts"] for ev in sound_events(self.score, p)}
        self.assertTrue({"lead", "piano", "vocal_backing", "flute", "vp_source"}.issubset(roles))
        self.assertFalse(report["human_listening_review"])

    def test_colour_missing_is_error_even_with_correct_chord_label(self):
        self.arrange()
        for part in ("Soprano", "Alto", "Tenor"):
            for e in self.score["score"][part][0]:
                if e["pitch"] is not None and e["pitch"] % 12 == 2:
                    e["pitch"] = 60
                    e.update(role="editorial", source_ids=[])
        self.assertIn("missing_harmonic_colour", [e["code"] for e in validate(self.score, self.evidence)["errors"]])

    def test_only_flute_may_become_whistle(self):
        self.arrange()
        source = next(n for n in self.evidence["notes"] if n["source"] == "piano")
        self.score["score"]["Whistle"][0] = fill_rests([note(72, 0, 240, "flute", [source["id"]])], 1920)
        codes = [e["code"] for e in validate(self.score, self.evidence)["errors"]]
        self.assertIn("whistle_without_flute", codes)
        self.assertIn("source_role_mismatch", codes)

    def test_harmony_lock_and_tool_boundary(self):
        self.store.write("score.json", self.arrange())
        tools = MusicTools(self.store, self.cfg, self.evidence, 1, 2, "arranger")
        with self.assertRaises(ValueError):
            tools.arrange_bars(1, 4)
        score = self.store.read("score.json")
        score["harmonies"][0]["candidates"].append(dict(score["harmonies"][0]["candidates"][0], symbol="C"))
        self.store.write("score.json", score)
        with self.assertRaisesRegex(ValueError, "locked"):
            tools.choose_harmony("h:0", 1, "simplify")
        with self.assertRaises(ValueError):
            tools.dispatch("exec", {"command": "echo unsafe"})
        with self.assertRaises(ValueError):
            tools.dispatch("replace_events", {"part": "Lead", "bar": 1, "events": [], "reason": "x", "shell": "x"})

    def test_source_pitch_and_timing_are_checked(self):
        self.arrange()
        lead = next(e for e in self.score["score"]["Lead"][0] if e["pitch"] is not None)
        lead["pitch"] += 1
        self.assertIn("source_pitch_changed", [e["code"] for e in validate(self.score, self.evidence)["errors"]])

    def test_editorial_label_cannot_bypass_lead_source_rules(self):
        self.arrange()
        lead = next(e for e in self.score["score"]["Lead"][0] if e["pitch"] is not None)
        lead["role"] = "editorial"
        lead["pitch"] += 1
        codes = [e["code"] for e in validate(self.score, self.evidence)["errors"]]
        self.assertIn("lead_role", codes)
        self.assertIn("lead_without_evidence", codes)

    def test_vocal_interpretation_retains_raw_evidence(self):
        self.store.write("score.json", self.arrange())
        before = digest(self.evidence)
        tools = MusicTools(self.store, self.cfg, self.evidence, 1, 4, "arranger")
        source = next(n for n in self.evidence["notes"] if n["source"] == "backing")
        tools.assign_vocal_roles([source["id"]], "backing_candidate", "Sustained independent lower vocal line")
        view = tools.inspect_bars(1, 4)
        changed = next(n for n in view["notes"] if n["id"] == source["id"])
        self.assertEqual(changed["original_role"], "backing")
        self.assertEqual(digest(self.evidence), before)
        piano = next(n for n in self.evidence["notes"] if n["source"] == "piano")
        with self.assertRaises(ValueError):
            tools.assign_vocal_roles([piano["id"]], "lead", "Not actually vocal evidence")

    def test_ties_and_single_performer_vp(self):
        self.arrange()
        first = next(e for e in self.score["score"]["Lead"][0] if e["pitch"] is not None)
        first["tie_start"] = True
        self.assertIn("broken_tie_start", [e["code"] for e in validate(self.score, self.evidence)["errors"]])
        for bar in self.score["score"]["VP"]:
            self.assertEqual(sum(e["duration"] for e in bar), 1920)
            for a, b in zip(bar, bar[1:]):
                self.assertEqual(a["offset"]+a["duration"], b["offset"])

    def test_evidence_rejects_invalid_times_and_hash_mismatch(self):
        e = copy.deepcopy(self.evidence)
        e["timing"]["anchors"][1]["seconds"] = 0
        with self.assertRaises(ValueError):
            check_evidence(e)
        from vibacappella.analysis import prepare
        run = create_run(Path(self.tmp.name)/"fixture.wav", self.cfg, Path(self.work.name)/"new")
        e = copy.deepcopy(self.evidence); e["audio_sha256"] = "wrong"
        write_json(Path(self.work.name)/"bad.json", e)
        with self.assertRaisesRegex(ValueError, "hash"):
            prepare(run, self.cfg, Path(self.work.name)/"bad.json")


class ExportRoundTrip(Base):
    def test_stale_validation_blocks_export(self):
        from vibacappella.export import export_bundle
        self.arrange()
        self.store.write("score.json", self.score)
        self.store.write("validation.json", validate(self.score, self.evidence))
        self.score["title"] = "Changed after validation"
        self.store.write("score.json", self.score)
        with self.assertRaisesRegex(ValueError, "stale"):
            export_bundle(self.store, self.cfg)

    def test_all_eight_xml_and_midi_exports(self):
        self.arrange()
        for selected in [self.score["parts"]]+[[p] for p in self.score["parts"]]:
            xml, mid = Path(self.work.name)/"test.musicxml", Path(self.work.name)/"test.mid"
            musicxml(self.score, xml, selected); midi(self.score, mid, selected)
            self.assertEqual(audit_notation(self.score, xml, mid, selected), [])

    def test_variable_meter_rubato_and_tie_roundtrip(self):
        e = copy.deepcopy(self.evidence)
        # 3/4 + 6/8 with a shorter final bar, all legal ticks and changing tempi.
        e["bars"] = [dict(number=i+1, start_tick=i*1440, duration_ticks=1440 if i < 5 else 480,
                          numerator=3 if i < 3 else 6, denominator=4 if i < 3 else 8) for i in range(6)]
        e["timing"]["anchors"][4]["seconds"] = 2.1
        check_evidence(e)
        s = empty_score(e, "Rubato")
        for p in s["parts"]:
            s["score"][p] = [fill_rests([], b["duration_ticks"]) for b in s["bars"]]
        s["score"]["Lead"][0] = [dict(note(67, 0, 1440, "editorial"), tie_start=True)]
        s["score"]["Lead"][1] = [dict(note(67, 0, 1440, "editorial"), tie_stop=True)]
        xml, mid = Path(self.work.name)/"rubato.musicxml", Path(self.work.name)/"rubato.mid"
        musicxml(s, xml); midi(s, mid)
        self.assertEqual(audit_notation(s, xml, mid), [])
        tracks, tempos = read_midi(mid)
        self.assertEqual(tracks[1]["notes"], [(0, 2880, 67)])
        self.assertAlmostEqual(tick_to_seconds(e, 1920), 2.1)

    def test_notation_corruption_is_detected(self):
        self.arrange()
        xml, mid = Path(self.work.name)/"test.musicxml", Path(self.work.name)/"test.mid"
        musicxml(self.score, xml); midi(self.score, mid)
        xml.write_text(xml.read_text().replace("<octave>4</octave>", "<octave>5</octave>", 1))
        self.assertTrue(audit_notation(self.score, xml, mid))


class AgentRuntime(Base):
    def test_tied_notes_keep_all_source_references(self):
        from vibacappella.music import sound_events
        s = self.score
        dur = s["bars"][0]["duration_ticks"]
        s["score"]["Lead"][0] = [dict(note(67, 0, dur, "lead", ["first"]), tie_start=True)]
        s["score"]["Lead"][1] = [dict(note(67, 0, dur, "lead", ["second"]), tie_stop=True)]
        events = sound_events(s, "Lead")
        self.assertEqual(events[0]["source_ids"], ["first", "second"])
        self.assertEqual(events[0]["end"], 2*dur)
        self.assertEqual(s["score"]["Lead"][0][0]["source_ids"], ["first"])

    def test_short_breath_extension_retains_onset_and_is_idempotent(self):
        from vibacappella.arrange import lengthen_breath_releases
        s = self.score
        # At 126 BPM a 120-tick gap is shorter than the 0.12 s phrase threshold.
        end = s["bars"][-1]["start_tick"] + s["bars"][-1]["duration_ticks"]
        s["timing"] = {"anchors": [{"tick": 0, "seconds": 0},
            {"tick": end, "seconds": end/480*60/126}]}
        dur = s["bars"][0]["duration_ticks"]
        s["score"]["Soprano"][0] = [note(72, 0, dur-120, "harmonic_support"),
            note(None, dur-120, 120, "rest")]
        self.assertEqual(len(lengthen_breath_releases(s)), 1)
        self.assertEqual(s["score"]["Soprano"][0][0]["offset"], 0)
        self.assertEqual(s["score"]["Soprano"][0][-1]["duration"], 240)
        self.assertEqual(lengthen_breath_releases(s), [])

    def test_invalid_event_role_rejected_before_score_mutation(self):
        self.store.write("score.json", self.score)
        tools = MusicTools(self.store, self.cfg, self.evidence, 1, 4, "arranger")
        before = self.store.read("score.json")
        with self.assertRaisesRegex(ValueError, "vp_source"):
            tools.dispatch("replace_events", {"part": "VP", "bar": 1,
                "events": [{"pitch": 36, "offset": 0, "duration": 120,
                            "role": "vp_kick", "source_ids": []}], "reason": "test invalid role"})
        self.assertEqual(self.store.read("score.json"), before)

    def test_two_role_agent_and_resume(self):
        run_agents(ScriptedClient(), self.store, self.cfg, self.evidence)
        before = self.store.read("score.json")
        class NoCalls:
            def complete(*args):
                raise AssertionError("Completed window must not call the model again")
        run_agents(NoCalls(), self.store, self.cfg, self.evidence)
        self.assertEqual(self.store.read("score.json"), before)
        self.assertEqual({n["role"] for n in before["review_notes"]}, {"arranger", "reviewer"})

    def test_failure_and_resume_without_duplicate_notes(self):
        class Interrupted(ScriptedClient):
            def complete(self, messages, schemas):
                if len([m for m in messages if m["role"] == "tool"]) == 2:
                    raise RuntimeError("simulated network loss")
                return super().complete(messages, schemas)
        with self.assertRaisesRegex(RuntimeError, "network loss"):
            run_agents(Interrupted(), self.store, self.cfg, self.evidence)
        before = self.store.read("score.json")["score"]
        run_agents(ScriptedClient(), self.store, self.cfg, self.evidence)
        self.assertEqual(before, self.store.read("score.json")["score"])

    def test_failed_finish_does_not_claim_success(self):
        self.store.write("score.json", self.score)
        tools = MusicTools(self.store, self.cfg, self.evidence, 1, 4, "reviewer")
        result = tools.finish("This deliberately incomplete score must not finish.")
        self.assertFalse(result["finished"])
        self.assertTrue(result["errors"])

    def test_path_escape_and_single_writer_lock(self):
        with self.assertRaises(ValueError):
            self.store.path("../outside")
        with self.store.lock():
            with self.assertRaises(RuntimeError):
                with Store(self.work.name).lock():
                    pass


class ProviderContract(Base):
    def configure(self, mode="native"):
        self.cfg["llm"].update(base_url="https://example.invalid/v1", model="configured-model", tool_mode=mode,
                                base_url_env="PARLEY_BASE_URL", model_env="PARLEY_MODEL",
                                api_key_env="PARLEY_API_KEY", secrets_file="", include_usage=False, team_id_env="PARLEY_TEAM_ID")
        self.env = patch.dict(os.environ, {"PARLEY_API_KEY": "test-secret-123", "PARLEY_BASE_URL": "", "PARLEY_MODEL": ""})
        self.env.start(); self.addCleanup(self.env.stop)

    def test_prime_file_credentials_and_two_tool_turns(self):
        secret_file = Path(self.work.name) / "prime.env"
        secret_file.write_text('PRIME_API_KEY="prime-test-key"\nPRIME_TEAM_ID=test-team\nPRIME_MODEL=catalog/model\n')
        self.cfg["llm"]["secrets_file"] = str(secret_file)
        captured = []
        class Opener:
            def open(self, request, timeout):
                captured.append(request)
                return io.BytesIO(json.dumps({"choices": [{"message": {"role": "assistant", "content": None,
                    "tool_calls": [{"id": "a", "type": "function", "function": {"name": "validate", "arguments": "{}"}}]}}],
                    "usage": {"total_tokens": 12}}).encode())
        with patch.dict(os.environ, {}, clear=True):
            client = Client(self.cfg, self.store, Opener())
            messages = [{"role": "user", "content": "inspect"}]
            first = client.complete(messages, SCHEMAS)
            client.complete(messages + [first, {"role": "tool", "tool_call_id": "a", "content": "{}"}], SCHEMAS)
            self.assertNotIn("PRIME_API_KEY", os.environ)
        self.assertEqual(captured[0].full_url, "https://api.pinference.ai/api/v1/chat/completions")
        self.assertEqual(captured[0].get_header("Authorization"), "Bearer prime-test-key")
        self.assertEqual(captured[0].get_header("X-prime-team-id"), "test-team")
        body = json.loads(captured[1].data)
        self.assertEqual(body["model"], "catalog/model")
        self.assertEqual(body["usage"], {"include": True})
        self.assertEqual(body["messages"][-1]["tool_call_id"], "a")
        self.assertNotIn("prime-test-key", self.store.path("events.jsonl").read_text())
        with patch.dict(os.environ, {"PRIME_API_KEY": "env-key"}, clear=True):
            self.assertEqual(endpoint_config(self.cfg)[2], "env-key")
        secret_file.unlink()
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "PRIME_API_KEY"):
                endpoint_config(self.cfg)

    def test_native_tool_request_and_secret_redaction(self):
        self.configure()
        captured = []
        class Opener:
            def open(self, request, timeout):
                captured.append(request)
                return io.BytesIO(json.dumps({"choices": [{"message": {"role": "assistant", "content": "test-secret-123",
                    "tool_calls": [{"id": "a", "type": "function", "function": {"name": "validate", "arguments": "{}"}}]}}], "usage": {"total_tokens": 12}}).encode())
        result = Client(self.cfg, self.store, Opener()).complete([{"role": "user", "content": "inspect"}], SCHEMAS)
        self.assertEqual(captured[0].full_url, "https://example.invalid/v1/chat/completions")
        self.assertEqual(captured[0].get_header("Authorization"), "Bearer test-secret-123")
        body = json.loads(captured[0].data)
        self.assertEqual(body["tools"], SCHEMAS)
        self.assertNotIn("test-secret-123", json.dumps(result))
        self.assertNotIn("test-secret-123", self.store.path("events.jsonl").read_text())
        self.assertEqual(self.store.read("budget.json")["tokens"], 12)

    def test_json_tool_fallback(self):
        self.configure("json")
        class Opener:
            def open(self, request, timeout):
                assert "tools" not in json.loads(request.data)
                return io.BytesIO(json.dumps({"choices": [{"message": {"content": '{"tool":"validate","arguments":{}}'}}]}).encode())
        result = Client(self.cfg, self.store, Opener()).complete([], SCHEMAS)
        self.assertEqual(result["tool_calls"][0]["function"]["name"], "validate")

    def test_http_protocol_drives_two_role_agent(self):
        self.configure()
        class Opener:
            def open(self, request, timeout):
                body = json.loads(request.data)
                message = ScriptedClient().complete(body["messages"], body["tools"])
                return io.BytesIO(json.dumps({"choices": [{"message": message}], "usage": {"total_tokens": 100}}).encode())
        report = run_agents(Client(self.cfg, self.store, Opener()), self.store, self.cfg, self.evidence)
        self.assertTrue(report["passed"])
        self.assertEqual(self.store.read("budget.json")["calls"], 7)

    def test_authentication_error_is_not_retried(self):
        self.configure()
        class Opener:
            calls = 0
            def open(self, request, timeout):
                self.calls += 1
                raise HTTPError(request.full_url, 401, "unauthorized", {}, None)
        opener = Opener()
        with self.assertRaisesRegex(RuntimeError, "401"):
            Client(self.cfg, self.store, opener).complete([], SCHEMAS)
        self.assertEqual(opener.calls, 1)
        self.assertEqual(self.store.read("budget.json")["calls"], 1)

    def test_budget_checked_before_request_and_survives_restart(self):
        self.configure()
        self.store.write("budget.json", {"calls": 512, "tokens": 0})
        with self.assertRaisesRegex(RuntimeError, "budget"):
            Client(self.cfg, self.store).complete([], SCHEMAS)

    def test_rate_limit_retries_with_persistent_budget(self):
        self.configure()
        class Opener:
            calls = 0
            def open(self, request, timeout):
                self.calls += 1
                if self.calls == 1:
                    raise HTTPError(request.full_url, 429, "rate limited", {}, None)
                return io.BytesIO(b'{"choices":[{"message":{"role":"assistant","content":"ok"}}],"usage":{"total_tokens":3}}')
        with patch("vibacappella.llm.time.sleep"):
            Client(self.cfg, self.store, Opener()).complete([], SCHEMAS)
        self.assertEqual(self.store.read("budget.json")["calls"], 2)

    def test_malformed_tool_response_is_not_executed(self):
        self.configure()
        class Opener:
            def open(self, request, timeout):
                return io.BytesIO(b'{"choices":[{"message":{"role":"assistant","tool_calls":[{"id":"x"}]}}]}')
        with self.assertRaisesRegex(RuntimeError, "Malformed"):
            Client(self.cfg, self.store, Opener()).complete([], SCHEMAS)

    def test_insecure_or_credential_url_rejected(self):
        self.configure()
        for url in ("http://example.com/v1", "https://key@example.com/v1", "https://example.com/v1?key=secret"):
            self.cfg["llm"]["base_url"] = url
            with self.assertRaises(ValueError):
                endpoint_config(self.cfg)


if __name__ == "__main__":
    unittest.main()
