# Changelog

## Unreleased: v2 preparation

- Audited the second Qwen v2 calibration chunk: 43/60 responses, two correct final maps, and eleven format failures. All earlier responses and all sixty InternVL results are preserved; seventeen Qwen requests remain.
- Added a worked DSU example to the README with the exact calibration diagram, complete task, and independently checked expected states.
- Published the current study on `main`, updated the Kaggle notebook defaults, and clarified calibration progress in the README and implementation notes.
- Audited the first Qwen v2 calibration chunk: 23/60 responses, one correct final map, and three format failures. All sixty InternVL responses and earlier study files are unchanged; 37 Qwen requests remain.
- Audited the complete InternVL v2 calibration: 60/60 responses, one correct final map, and 38 format failures. T-dir and G-dir each scored 0/12. Prepared Qwen calibration from the combined backup; main remains disabled.
- Audited the second InternVL v2 calibration chunk: 43/60 responses, zero correct final maps, and 27 format failures. Earlier caches and aggregate records are preserved; seventeen InternVL requests remain.
- Audited the first InternVL v2 calibration chunk: 23/60 responses, zero correct final maps, and 16 format failures. The earlier combined smoke payload is unchanged; calibration remains incomplete.
- Added calibration recovery without notebook setup variables, with smoke-cache and input validation, a 20-call limit, and automatic export.

- Prepared a separate v2 protocol with shared worked examples and explicit JSON field types.
- Matched calibration to the 8/16-element and 1/4-operation main design.
- Added bounded inference, token and device logging, checked archive restore, and a freeze audit against raw caches.
- Added Qwen and InternVL Kaggle notebooks that default to three smoke calls and export after each inference chunk.
- Audited the three-call Qwen v2 smoke: all responses validated, all were wrong. Text and rendered text copied the initial state; the diagram response matched operations on a fresh forest.
- Added a standalone Kaggle diagnostic recovery script so a reset kernel can restore the saved smoke without relying on notebook variables.
- Audited all eight Qwen v2 diagnostics and preserved the three original smoke responses. Text and rendered-text transcription were correct; diagram extraction and all five DSU checks failed. No calibration or main study was run during these checks.
- Audited the InternVL v2 smoke and unchanged Qwen payloads. Approved one fixed representative calibration set per model in bounded chunks; main remains blocked pending calibration review and freeze.

## V1 calibration and feasibility

- Completed the first Qwen pilot on 12 four-operation tasks. T-dir, R-dir, and G-dir each scored 0/12 on final-state exact match; the protocol remains unfrozen.
- Completed the second Qwen pilot with the same rules, images, prompts, model settings, and strict scorer. T-dir scored 1/12; R-dir and G-dir scored 0/12. The Qwen main run remains stopped, with no protocol freeze.
- Noted that the structured prompt does not explicitly state the JSON-object type of `transcription`; official scores remain unchanged.
- Ran and audited the three-call InternVL3.5 HF smoke test on an existing pilot2 task. T-dir was strict-correct; R-dir and G-dir failed strict JSON parsing after emitting `<think>` text. No full pilot or main run followed.
- Kept generated tasks, images, raw responses, and scores out of Git. SHA-256 checksums for the reviewed private archives are in the README.
- Wrote a pilot and feasibility report from the audited results; the main study remains stopped.
