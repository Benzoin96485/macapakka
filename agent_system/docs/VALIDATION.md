# Validation record

Date: 2026-11-13. Offline checks and historical live-provider checks are recorded separately below. Historical run data and exported results remain local and are not included in the repository.

## Automated regression tests

```sh
cd agent_system
python3 -m unittest discover -s tests -v
```

The current suite has 29 tests. The initial validation used 25 tests, and the later Sonnet run used 28. Coverage includes:

- Complete arrangement and review tool loops, including integration with the HTTP request adapter.
- Checkpoint recovery without duplicate notes and without recalling the model for completed windows.
- Locked reference harmony and detection of missing ninths even when chord labels are correct.
- Rejection of piano material assigned to Whistle and attempts to bypass lead provenance using editorial labels.
- Lead pitch classes, backing-role interpretation, immutable source candidates, single-person VP, and broken ties.
- Event comparisons across eight MusicXML/MIDI pairs, including 3/4, 6/8, short final bars, tempo changes, and merged ties.
- Native tool requests, JSON fallback, credential redaction, no retry on 401, bounded retries on 429, persistent budgets, invalid URLs, and malformed tool responses.
- Path boundaries, single-writer run locks, and rejection of incomplete scores as completed work.
- Export validation covering the whole song and matching the exact score digest, preventing stale checks from approving modified scores.
- Prime file credentials, environment precedence, optional team billing, usage requests, missing-key handling, and two simulated tool-call turns.

HTTP tests use in-memory response doubles. They verify request construction and response parsing rather than connectivity to Prime or Parley. A clean export of the staged source passed all 29 tests without local data or secrets before the initial GitHub upload.

## Historical audio analysis smoke test

Input: seconds 30-38 of the existing EYKM recording and matching excerpts of six previously separated stems from the neighboring project. Full-length Demucs separation was not rerun.

The test executed FFmpeg, local Basic Pitch ONNX inference, and timing, harmony, and drum-onset analysis:

| Metric | Result |
|---|---:|
| Input duration | 8 seconds |
| Note candidates | 194 |
| Bars | 6 |
| Half-bar harmony segments | 12 |
| Drum-onset candidates | 120 |

Timing was explicitly configured as 126 BPM in 3/4. This does not validate automatic meter detection. Local output: `runs/analysis-smoke/evidence.json`; log: `runs/analysis-smoke/logs/analysis.log`. These counts demonstrate execution, not transcription accuracy. Duplicate detections across drum bands still require selection for single-person VP.

## Complete offline delivery test

The local `runs/demo-final` used eight seconds of original synthetic test audio, known evidence, and an explicit scripted provider:

- Four bars containing Cadd9, G7/B, Am7, and Fadd9, with moving piano lines, backing vocals, and flute restricted to designated passages.
- Eight MusicXML files, eight MIDI files, and eight PDFs.
- Sixteen WAV and sixteen MP3 files: full mix, no-lead accompaniment, seven isolated parts, and seven part-emphasized practice mixes.
- Audio at 44.1 kHz, with eight seconds of music and 2.5 seconds of sample release; full-mix peak approximately 0.91.
- Forty-one samples from local MS Basic.sf3, rendered by the project sampler rather than the MuseScore audio engine. No source recording was mixed in.
- Passing WAV/MP3 duration checks and MusicXML/MIDI event checks.
- Full-score PDF rendered to images for inspection of seven staves, notes, rests, accidentals, ties, VP syllables, chords, and meters. This validates a proof score, not publication engraving quality.

## External validation still outstanding

- Live Prime inference and model-specific tool compatibility have not been verified with a real Prime key.
- Full-song Demucs separation has not been downloaded and rerun from scratch; the adapter requires a working local installation and models.
- GAME was adapted from the earlier workflow, but its inference was not rerun during these checks.
- MuseScore and FluidSynth are optional explicit backends; the delivery checks above used the sampler and proof PDF backend.
- No human note-by-note listening review, independent melody-accuracy evaluation, automatic flute classification, or complete lyric recognition/forced alignment has been completed.

Successful delivery therefore retains `human_listening_review: false`.

## Historical live Parley checks

Two-turn tool calls were verified with Sonnet 4.6 and Sonnet 5.5 through Parley, using 1,358 and 945 tokens respectively. These checks are distinct from the offline tests and do not establish Prime compatibility.

## 2026-11-13 Sonnet 5.5 full-song EYKM run

- All 198 bars were arranged and independently reviewed using live Parley `claude-sonnet-5-5` calls.
- The complete first pass and reviewed version remain locally under `outputs/EYKM_Sonnet55/original` and `reviewed`. First-pass conversations and tool logs were preserved separately.
- The first pass had no hard errors and 118 warnings. The reviewed version had no hard errors and 55 long-phrase reminders. Human listening review remains outstanding.
- Each version included eight PDFs, eight MusicXML files, eight MIDI files, sixteen WAV files, and sixteen MP3 files. Tracks were 298.72 seconds. Hash checks passed for 95 exported files per version, and MusicXML/MIDI note comparisons passed.
- Twenty-eight tests passed at that stage. Original and reviewed full scores, lyric pages, and VP pages were spot-checked. Section seeking and synchronized version switching on the comparison page were verified in a browser.
- Original audio was not sent to the LLM. Timing, lead/lyrics, and harmony references came from v3, with existing instrumental transcription candidates. SATB and VP were newly arranged through model tool calls.
- Cost scope and exact local file locations were recorded in `outputs/EYKM_Sonnet55/usage-and-validation.json` and `comparison.json`.
