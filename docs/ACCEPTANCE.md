# Workflow acceptance

## Workflow update — 12 November 2026

**PASS: 48 tests, 0 failures, 0 errors, 0 skips. No real Flow submissions.** The final run completed in 11.583 seconds. Real Flow CLI/bridge access was blocked by the test harness; temporary fixtures stayed under `tests/.tmp`. Synthetic local FFmpeg fixtures are used only for media-tool checks.

- Full transcript: [workflow-update-tests.txt](discovery/workflow-update-tests.txt).
- Machine-readable result: [workflow-update-result.json](discovery/workflow-update-result.json).
- New regressions: [test_lessons.py](../tests/test_lessons.py), alongside the 14 original tests.

Checks cover exact Unicode/quoted/multiline dialogue through the actual ASCII stdout payload command; immutable request/ledger/hash and U+FFFD rejection; sole-speaker compilation inside real edit boundaries; wrong-first-word and missing-playback rejection; recovery without invented IDs, output spending or pending-state bypass; duplicate/path escape protection; small end-duration fits and fresh review requirements; unchanged preflight expiry with early warning; and named Unicode workspace directories. Legacy non-dialogue and the completed film's recovery transport remain readable.

These tests validate local workflow behavior. The 0.4-second lead-in, listener-silence cues and 0.6-second hold are proposed mitigations from user feedback, **not live-tested guarantees** that Flow will assign the first word correctly. The next authorized production must check the first speaking take of each character and the opening word of every dialogue take. See [LESSONS_LEARNED.md](LESSONS_LEARNED.md).

## Original scaffold report — 11 November 2026 (historical)

The remainder preserves the original pre-production acceptance record. Its planning-only statements describe that earlier run, not the present state of live project folders. Tests now use the frozen fixture and must never reset completed production state from this report.

**PASS: 14 tests, 0 failures, 0 skips. Zero real Google Flow generation submissions.**

Command: `python -m unittest discover -s tests -v` — 14 tests passed in 4.001 seconds in the final recorded run. Full output: [acceptance-tests.txt](discovery/acceptance-tests.txt). Machine-readable result: [acceptance-result.json](discovery/acceptance-result.json).

The existing two workspace folders were preserved. The connector's final read-only snapshot reported browser **Edge**, `usedToday:0`, image/video usage 0, active jobs 0. Its recent-job result was **“no jobs yet”**. See [status](discovery/final-status.json) and [jobs](discovery/final-jobs.json). No `flow_generate` or CLI `generate create` call was made during the build or tests.

## Dry-run fixture verification

- Frozen test baseline: [ceramicist-plan.json](../tests/fixtures/ceramicist-plan.json) — one A01 reusable identity reference, S01 ingredients shot using A01, and S02 frame-driven shot using **selected S01 at 7.000 seconds**.
- Exact draft payloads / CLI argument arrays: explicit Flow mode, model, ratio, output count and duration; CLI video resolution 720p; MCP resolution requires visible Edge verification. The live runner binds actual reviewed selected filenames and a unique submission token immediately before generation. Dry-run paths are predictions, not existing media.
- Estimate: 1 image, 2 videos, 0 planned variants; 8 + 8 = **16 generated seconds**, edited as S01 [0,7) + S02 [0,8) = **15 seconds**. Proposed production cap 1 image / 3 videos leaves one video revision in reserve. Credit price is unverified.
- Fixture remains planning only: authorization false, no Flow project ID, no selected media and no real output links.

## Interrupted submission test

The in-memory fake connector accepts the journaled **A01_T01** request as **mock-job-001**. The test simulates a crash before recording that acknowledgement. Reloaded disk state has `submission_pending` and a null job ID.

Resume identifies the exact full job through its mode, prompt, model/ratio/output settings and unique download-folder token. Three further preparation attempts are blocked while the accepted job remains running, with reconciliation repeated after each. **Total fake generate calls: 1. Total takes: 1.**

A separate crash-before-send test presents an empty recent-job list. The intent stays pending and cannot be submitted again. Other tests cover multiple matching jobs, MCP prompt truncation, completed paths with a unique token, responses that omit a job ID, missing downloads, cap/authorization/preflight/cooldown gates, mandatory reference review, fixed Veo durations, unsupported Quality ingredients and project locking.

Revision tests preserve the previous selected take and mark downstream frame-dependent S02 stale when S01 is replaced. Switching the chosen output within one take also invalidates downstream shots. Native argument tests preserve spaces, apostrophes, Unicode, literal shell metacharacters and multiline dialogue.

## Local media check

An integration test creates **synthetic color clips only**, in a temporary directory. It verifies full decoding, 720×1280 video, opening/action/ending previews, extraction of S01's frame at 7.000 seconds, then a local FFmpeg assembly trimmed to 7 + 8 seconds. The assembled file is probed and fully decoded with runtime within 0.15 seconds of 15 seconds. All synthetic files are temporary and removed by the test.

These checks establish local state/recovery and media-tool behavior. Actual cup identity, hand motion, lighting continuity, dialogue/sound and the live generation path must be inspected during real production. MCP cannot verify the active project URL or set resolution; the workflow explicitly requires those visible Edge observations before submission.

The tests use a frozen fixture under `tests/fixtures/`, so producing or revising the example project does not change the test baseline.

## First production instruction

> Produce this video using the ceramicist-blue-cup plan: a 15-second vertical film revealing the finished blue cup. Cap production at 1 image output and 3 video outputs including revisions. Use my signed-in Google Flow session in Microsoft Edge and my available allowance; spend no additional money. Deliver reviewed clips and the edit list.
