# Evaluation kit validation

This verifies the **materials and grading tools**, not any AI's physics ability. **No independent model forecast has been collected or scored.**

- Initial parameters were exported from a newly constructed Rapier world without calling release or step. The physical source SHA-256 is recorded in both the input specification and measured label file.
- Four images were captured in installed headless Chromium. Every capture checked time = 0, all nine stage flags false and the requested initial options. Page UI was temporarily hidden only while capturing, so it does not obscure the machine. No application source or physical configuration was changed for these views.
- Browser capture reported zero page/console errors and zero external requests; non-loopback requests were blocked.
- `record-truth.mjs` executed the real Machine for REF and X1–X4: 3 repeats each, 3600 fixed solver steps per run, 15 measured runs in total. All scored observations and first bell times agreed between repeats. The reference calibration was checked, and a source/input version mismatch would reject collection.
- The measured observations, source hash and input manifest hash are in `ground-truth.json`; unabridged reports are in `solver-evidence.json`.
- `node --test tests/evaluation.mjs`: **10 tests passed**, 0 failed/skipped. They checked perfect and inverted synthetic fixtures, declared weights, order invariance, optional time handling, contradiction warnings, malformed forecasts, BOM/fence parsing, input modification, frozen-forecast modification, dataset mismatch, no-overwrite behavior, evidence counts and allowed input contents.
- Perfect synthetic fixtures score 100 and inverted fixtures score 0; these are manufactured unit-test inputs, **not model achievements**. Synthetic receipts are created in temporary folders and removed.
- The input package is allowlisted: four initial PNG images, prompt, scene description, physics parameters, empty response template and a file-hash manifest. No answer key, solver trace, project README, test report, running screenshot, executable simulation or repository URL is packaged into it.
- The operator package contains the answers and Node-only freeze/score tools separately. Keep it away from the model.

Environment: Node.js 24.19.0, Rapier compat 0.20.0, Linux Chromium with SwiftShader. Native Windows execution has not been performed. The scorer uses built-in Node modules only. The machine and application runtime source remain unchanged by this evaluation work.

## Interpretation limits

There are only four related questions. X2 is a reference-restoration control and X4 is a combination-consistency question. Binary outcomes, contact flags and stage flags overlap causally; a 100-point aggregate is not a count of independent physical tasks. Score subcomponents and inspect explanations alongside the aggregate. Probability Brier scores from four correlated questions do not establish general calibration.

Labels are withheld **from the input package**, not secret on the internet: the repository contains old reports and the separate operator key. A new model context with browsing/simulation disabled and documented provenance is necessary. Local hashes detect accidental changes; they do not prove that the model was blind or provide a trusted timestamp. Do not call existing development-dialog answers or feedback-corrected answers blind predictions.
