# Sources, inherited code, and third-party dependencies

Review date: 2026-11-13. These entries record the project's integration history; they are not a fresh audit of external services.

| Source | Use and verification scope |
|---|---|
| [Prime Inference documentation](https://docs.primeintellect.ai/inference/overview) | Default OpenAI-compatible endpoint, Bearer authentication, model IDs, and optional team billing. Local request tests pass; live Prime calls remain unverified. |
| [MIT Parley documentation](https://parley-docs.mit.edu/) | Authenticated Chat Completions and Tool Calling documentation was reviewed on 2026-11-13. Subsequent live Sonnet 4.6 and 5.5 tool-call checks are recorded in the README and validation history. |
| [MIT Parley API announcement](https://orgchart.mit.edu/letters/parley-api-now-available-mit-community) | Identifies MIT's service and distinguishes it from unrelated products with the same name; not used to infer endpoints. |
| [Demucs source](https://github.com/facebookresearch/demucs) | Six-stem separation CLI adapter. The upstream repository was recorded as archived; consult upstream for maintenance status. No model modifications or weights are bundled. |
| [Basic Pitch source](https://github.com/spotify/basic-pitch) | Per-stem note candidates through `predict` and ONNX. Uses separately installed models; weights are not bundled. |
| [MuseScore command-line documentation](https://handbook.musescore.org/appendix/command-line-usage) | Export through `-o`. Parts of the documentation were inherited from v3; verify behavior against the installed version. |
| Local historical v3 technical report | Arrangement and validation experience from this project, not an externally published reference score. The report is not distributed with this source repository. |
| [`render_samples.py`](../../legacy/outputs/EYKM_Acappella_v3/source/render_samples.py) | `SampleBank` was extracted and decoupled into `samples.py`, removing EYKM data loading, fixed paths, and meter assumptions. |
| Neighboring Claude project's `_work/scripts/v2_game.py` | Adapted into `game.py`, with model directory, language, and audio supplied through configuration. GAME weights are not copied. |

`proof.py` is a general proof-score renderer, not MuseScore rendering. `samples.py` reads a local SoundFont and implements the sample zones, envelopes, and loops needed here; it is not a complete SoundFont implementation. Piano for the five vocal parts, flute for Whistle, and drums for VP are rehearsal playback conventions.

Demucs, Basic Pitch, GAME, ONNX Runtime, MuseScore, SoundFonts, and fonts retain their own licenses. This repository does not grant redistribution rights for third-party models, music, sound libraries, or fonts. This record does not change the user's authorization to use existing recordings.
