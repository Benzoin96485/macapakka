# From a single arrangement task to a reusable agent

This review describes work performed in the local v1/v2/v3 projects and the neighboring Claude project. Model prompts are only one part of the workflow.

## 1. Confirm the input and musical goal

The original task required Lead + SATB + VP + Whistle while preserving the recording's harmonic color. Hashes confirmed that both projects used the same source audio. Performance roles and rehearsal playback instruments are separate: piano renders the five vocal parts, flute renders Whistle, and drums render VP. This does not add piano to the performance arrangement.

The reusable system binds evidence to an input snapshot, duration, and hash. Playback presets belong to the export layer. Each run is stored separately so that new work cannot overwrite a version already used in rehearsal.

## 2. Separate source separation, transcription, and phrasing

Demucs supplies source clues; GAME and Basic Pitch supply note candidates. Melody f0 from a mix can be affected by backing vocals and harmonics, and piano stems can contain vocal leakage. Candidate selection depends on melodic continuity, duration, and context.

A local worker operates independently of the API model and stores each candidate's source, time, pitch, and confidence diagnostics. Expensive steps are cached; missing analysis dependencies cause explicit failures. The LLM reads structured evidence rather than claiming to have heard audio that was never uploaded.

## 3. Establish timing before notation

The introduction, main body, and ending cannot always share one constant-tempo grid. The v3 workflow used boundaries tied to the recording's flexible timing and checked the resulting musical duration. Lyrics and ties require the same mapping.

Source-seconds-to-tick anchors and per-bar meters are shared data. Automatic estimates are drafts. Corrected evidence can describe pickups, changing meter, and rubato; automatic meter detection is not presented as a reliable final decision.

## 4. Preserve the harmony in the sounding notes

The v2 fixed chord table and whole-bar root selection lost suspensions, inversions, sevenths, ninths, and half-bar changes. Restoring chord labels alone was insufficient: the actual SATB notes also needed the defining tones.

Harmony segments, candidates, and locks are explicit data. Validation checks `required_pcs` and `bass_pc`. Existing themes are not forced onto a replacement chord template. Automatic candidates require review, and locked references cannot be freely reharmonized by the LLM.

## 5. Preserve texture, instrument identity, and backing vocals

Piano motives and moving lines need singable role assignments. Spreading chord tones into repetitive arpeggios loses that material. Whistle follows actual flute evidence; piano themes in introductions and endings remain vocal material. Original backing vocals and newly composed harmonic support have different evidence status.

Tools assign piano material using source onsets and pitch classes. The LLM can revise rhythm, ties, and selection while retaining source tracking. Backing roles are accounted for separately. The `other` stem is not automatically flute; absent evidence produces rests and an explicit review item.

## 6. Arrange VP for one performer

Band-based drum onset analysis can report one snare hit in several frequency bands. Copying simultaneous drum tracks does not produce a playable single-person vocal percussion part. Entries, dynamics, breathing, transitions, and fills also need design.

The system selects one articulation per grid position and controls density using source onsets and section strategy. Composed cymbal gestures and fills are marked editorial. Separate VP audio and notation help expose problems hidden by the full mix.

## 7. Give arrangement and review separate contexts

Generating an entire song in one long answer makes constraints easy to forget and revisions difficult to target. Arrangement decisions need another evidence review.

The same API model serves two logical roles with separate tasks. Windowed arrangement is followed by review in a fresh context. Each step has tool results, a budget, and a checkpoint. Machine validation is independent of LLM self-assessment. Missing `finish` calls or critical errors prevent successful export.

## 8. Verify the export chain

The historical v3 MuseScore CLI could not initialize in the available GUI environment, so audio used local MS Basic samples. It was not described as direct MuseScore export. Notation and audio received event-level checks.

The reusable system explicitly selects MuseScore, FluidSynth, or the project sampler and does not silently switch engines after failure. MusicXML, MIDI, PDF, and audio share a canonical score. Backend identity and sound-library hashes are recorded. Proof PDFs are distinguished from publication engraving.

## 9. Deliver a draft for rehearsal

Hashes, durations, event comparisons, and range checks catch software errors. They do not establish transcription accuracy, timbral quality, or musical expression, and do not replace human listening.

The system retains `human_listening_review: false` and unresolved warnings, and exports materials suited to isolated listening and score revision. It does not treat automated approval as human acceptance or promise a performance-ready score from arbitrary audio in one pass.
