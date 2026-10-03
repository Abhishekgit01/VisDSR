# Changelog

## Unreleased: v2 preparation

- Prepared a separate v2 protocol with shared worked examples and explicit JSON field types.
- Matched calibration to the 8/16-element and 1/4-operation main design.
- Added bounded inference, token and device logging, checked archive restore, and a freeze audit against raw caches.
- Added Qwen and InternVL Kaggle notebooks that default to three smoke calls and export after each inference chunk.
- Audited the three-call Qwen v2 smoke: all responses validated, all were wrong. Text and rendered text copied the initial state; the diagram response matched operations on a fresh forest.
- Added eight separately cached diagnostic checks before full calibration. No v2 calibration or main study has occurred.

## V1 calibration and feasibility

- Completed the first Qwen pilot on 12 four-operation tasks. T-dir, R-dir, and G-dir each scored 0/12 on final-state exact match; the protocol remains unfrozen.
- Completed the second Qwen pilot with the same rules, images, prompts, model settings, and strict scorer. T-dir scored 1/12; R-dir and G-dir scored 0/12. The Qwen main run remains stopped, with no protocol freeze.
- Noted that the structured prompt does not explicitly state the JSON-object type of `transcription`; official scores remain unchanged.
- Ran and audited the three-call InternVL3.5 HF smoke test on an existing pilot2 task. T-dir was strict-correct; R-dir and G-dir failed strict JSON parsing after emitting `<think>` text. No full pilot or main run followed.
- Kept generated tasks, images, raw responses, and scores out of Git. SHA-256 checksums for the reviewed private archives are in the README.
- Wrote a pilot and feasibility report from the audited results; the main study remains stopped.
