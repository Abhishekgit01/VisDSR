# Changelog

## Unreleased

- Completed the first Qwen pilot on 12 four-operation tasks. T-dir, R-dir, and G-dir each scored 0/12 on final-state exact match; the protocol remains unfrozen.
- Completed the second Qwen pilot with the same rules, images, prompts, model settings, and strict scorer. T-dir scored 1/12; R-dir and G-dir scored 0/12. The Qwen main run remains stopped, with no protocol freeze.
- Noted that the structured prompt does not explicitly state the JSON-object type of `transcription`; official scores remain unchanged.
- Ran and audited the three-call InternVL3.5 HF smoke test on an existing pilot2 task. T-dir was strict-correct; R-dir and G-dir failed strict JSON parsing after emitting `<think>` text. No full pilot or main run followed.
- Kept generated tasks, images, raw responses, and scores out of Git. SHA-256 checksums for the reviewed private archives are in the README.
