# Data contract and extension interfaces

## Timing and provenance

All score pitches use sounding MIDI note numbers; the Tenor octave clef is a display convention. There are 480 ticks per quarter note, with a current editing grid of 120 ticks (sixteenth notes). Timing anchors must increase strictly.

`evidence.json` is the fixed analysis input for a run and includes the original audio SHA-256. Human corrections to timing, harmony, or instrument attribution require a new run using `--evidence`; do not overwrite evidence in an existing run.

```json
{
  "schema_version": 1,
  "audio_sha256": "actual-sha256-of-the-recording",
  "duration_seconds": 2.0,
  "timing": {"anchors": [
    {"tick": 0, "seconds": 0.0},
    {"tick": 480, "seconds": 0.5},
    {"tick": 960, "seconds": 1.0},
    {"tick": 1440, "seconds": 1.5},
    {"tick": 1920, "seconds": 2.0}
  ]},
  "bars": [{"number": 1, "start_tick": 0, "duration_ticks": 1920,
            "numerator": 4, "denominator": 4, "section": "A"}],
  "notes": [{"id": "piano:0", "source": "piano", "instrument": "piano",
             "role": "candidate", "start": 0.0, "end": 0.5,
             "pitch": 64, "confidence": 0.7}],
  "drums": [{"id": "drums:0", "time": 0.0, "kind": "K", "strength": 0.8}],
  "harmonies": [{"id": "h:0", "start_tick": 0, "end_tick": 1920,
    "locked": true, "confidence": "reviewed_reference",
    "candidates": [{"symbol": "Cadd9", "pcs": [0,2,4,7],
                    "required_pcs": [2,4], "bass_pc": 0, "score": 1.0}]}],
  "alerts": ["Note confidence values are not calibrated probabilities."],
  "provenance": {"human_review": false}
}
```

This illustrates fields rather than a complete melody. Generate a working sample with `demo.fixture()` or the demo command; historical run files are not included in the repository.

| Field | Meaning |
|---|---|
| `timing.anchors` | Piecewise-linear mapping between ticks and source-audio seconds; supports rubato without forcing one BPM across the song |
| `bars` | Per-bar meter; shorter first/final bars can represent pickups or endings and require review |
| `notes[].source` | Actual analysis source, such as piano, guitar, bass, vocals, lead, backing, flute, or other |
| `role` | Evidence role before arrangement: candidate, lead, backing, backing_candidate, or flute |
| `instrument_confidence` | Flute attribution confidence used by the threshold; a high melody alone does not justify 1.0 |
| `syllable` | Optional aligned lyric syllable, not a full lyric-ASR input interface |
| `harmonies[].locked` | Prevents the LLM from replacing reference harmony with another candidate; corrections require new evidence |
| `required_pcs` | Defining pitch classes required in the sounding parts, including thirds and relevant sevenths, ninths, or suspensions |
| `bass_pc` | Root or slash-chord bass pitch class |
| `score` / `confidence` | Transcription/retrieval diagnostics, not claimed accuracy rates |

## Event score

`score.json` contains the same bars and timing, selected harmony, per-bar events for seven parts, and decision records.

Optional `source_roles` records the LLM's interpretation of vocal candidates as lead, backing_candidate, or ignore, with reasons. It may reference only existing vocals/lead/backing candidates and cannot alter their pitch, timing, or instrument identity. Original evidence remains unchanged.

A typical note event contains:

```json
{
  "pitch": 64,
  "offset": 240,
  "duration": 480,
  "role": "piano",
  "source_ids": ["piano:0"],
  "velocity": 64,
  "confidence": 0.7,
  "syllable": "du"
}
```

`pitch: null` denotes a rest. Offsets are relative to the current bar, and events must cover the whole bar; tools fill gaps with rests. Individual events do not cross bar boundaries. Cross-bar sustained notes use matching pitches with `tie_start`/`tie_stop`; MIDI and audio merge ties without retriggering.

Source notes may be octave-displaced, but their pitch classes cannot change while retaining the original source ID. Lead and Whistle require provenance. `harmonic_support`, `editorial`, and `vp_editorial` explicitly mark newly arranged material. `vp_source` references drum-onset IDs.

VP syllables map to GM MIDI notes: K=36, pf=38, ka=37, t=42, ts=46, ksh=49, dm=45. Every vocal and VP part is monophonic; overlapping events are invalid.

## Adding tools and models

1. Add a local analysis-worker adapter that outputs notes, drums, and timing mappings as above. Do not let model output directly write final MusicXML.
2. Declare new arrangement-tool schemas in `agent.py` under `SCHEMAS` and bind methods in `MusicTools`. Save versions through `save()`. Do not expose arbitrary shell access, network URLs, or file paths to the LLM.
3. Implement providers as `complete(messages, schemas) -> assistant_message`, retaining normalized `tool_calls`, persistent budgets, credential handling, and bounded retries.
4. New audio engines must read the same `sound_events()`, handle ties and timing anchors, and inspect actual exported files. Do not silently replace a failed engine with an oscillator while retaining the original engine label.
5. Extend the canonical schema, validator, and MusicXML/MIDI round-trip comparisons before adding PDF support for new notation features.

## Run files

- `input/`: original-file snapshot; `work/`: normalized WAV, stems, and transcription caches.
- `evidence.json`: fixed candidate evidence; `score.json`: current event score.
- `revisions/`: score snapshots; `agent/`: per-window message checkpoints for both roles.
- `events.jsonl`: tool inputs, results, and stage events; `budget.json`: API budget accumulated across resumes.
- `validation.json`: musical structure checks; `exports/revision-N/`: scores, audio, review page, review notes, and manifest.
- `state.json`: created, analyzing, analyzed, arranging, exporting, then exported_draft_needs_review. Exceptions set failed while preserving earlier artifacts.
