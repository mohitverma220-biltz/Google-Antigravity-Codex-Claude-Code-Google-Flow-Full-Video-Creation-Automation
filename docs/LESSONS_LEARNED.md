# Production Lessons Learned

A multi-clip dialogue reel (vertical 720x1280, with native Hinglish dialogue and office ambience) surfaced key real-world behaviors of browser-bridged video generation. This update changes future workflows, templates and local runner checks only. No new live Flow generation tests were run for these prompting changes.

Workflow implementation and regression validation: 48 tests passed with no real Flow access.

## First word belongs to the intended speaker

After delivery, the user reported that a shot's first word often seems to come from the listener before the intended speaker takes over. The earlier generic speaker/lip-sync review did not isolate this. The precise model-level cause remains unknown. Equally prominent readable faces and a shared endpoint describing the next character as ready to answer are possible ambiguity sources, not proven causes.

For future dialogue shots:

1. Assign one stable speaker ID and visual identity; explicitly list every listener. Keep screen direction and clothing consistent. Put only one uninterrupted speaking turn in each clip.
2. Keep both mouths neutral/closed in shared boundary images. Do not make the next speaker appear to speak or prepare a reply during the current shot. Use a speaker-focused composition when a two-shot repeatedly confuses ownership; plan this before spending on frames where possible.
3. Include a 0.4 s silent lead-in and 0.6 s settling hold within the planned edit window. Only the intended speaker starts mouth movement and owns the entire exact line, including its first audible word. Every listener remains silent throughout. Finish the final syllable and reach the ending pose before the hold; no late head turn or reply.
4. Use `dialogue` in [dialogue-shot.json](../templates/dialogue-shot.json). The runner compiles the guard and quotes the line once; it keeps editor-only first-word metadata out of spoken text. Speech timing derives from edit-in/out, not merely nominal generated duration.
5. Watch and listen to the opening 1–2 seconds, entire line and last second. Record first-word speaker explicitly. Selection fails if the listener owns the opening word, even when all later words are correct. A still image or an audio track alone cannot verify this.
6. If a take fails, preserve it and use a targeted revision within the remaining cap. Do not hide the problem by clipping off the word or pretending the listener was meant to speak. These cues need a fresh live-project trial; they are not a guaranteed model fix.

## Exact text must survive the Windows stdout boundary

S02's saved script/request were correct, but a console transport replaced U+2014 with U+FFFD. Automatic approval review blocked that corrupted dispatch before Flow. A user-authorized corrected dispatch succeeded.

`flow.py payload PROJECT TAKE` now exports only the immutable MCP object as ASCII-escaped JSON, verifies the ledger/payload hash and rejects replacement characters. Parse JSON to restore the exact Unicode string. `--verify-file` compares a candidate without sending. Native-argument tests alone did not cover this boundary; a subprocess test now does. A rejected/ambiguous request is never silently reset or resent.

## A reported failure can coexist with a usable browser asset

The connector continued reporting both closing attempts as failed with no files. The user saw a fifth playable clip in Flow, downloaded it, and that distinct 7.93-second asset passed file and user playback review. Its exact queue-job association remains unknown.

Check visible project assets and actual downloads before recommending another attempt, a cap increase or a dropped shot. `recover` records an existing project-local asset, original path/hash/source evidence and an honest null job ID. It spends no generation outputs, preserves failed reports, does not clear other pending jobs, and can proceed through review/selection/assembly without another film manifest. A raw failure is evidence about the connector's state, not proof that a clip does not exist.

## Nominal time and actual cuts differ

Eight-second requests returned 7.916667-second video streams with roughly 7.918–7.93-second containers. The original strict eight-second trim blocked probing. `probe --fit-shortfall` now permits a logged end-only reduction of at most 0.15 s, updates edit totals and requires fresh ending review. It does not change raw media, settings or immutable requests. Larger shortages and incomplete speech remain failures requiring judgment.

Source trims totalled 39.583335 s; the final normalized 30 fps export was 39.688021 s. Report actual source/edit/export durations separately. End-of-shot head turns were visible at hard cuts despite matching planned frames; a quiet hold plus actual outgoing/incoming cut-frame and playback review is necessary.

## Less interruption without inventing evidence

- Record project folder, direct download location, caps and assembly intent during intake. Reuse valid authorization instead of asking again later. `init --directory` supports the user's exact workspace folder name independently of the lowercase slug.
- `preflight-check` warns two minutes before the existing 15-minute expiry. Reinspect the visible Edge project/model/resolution/panel autonomously when UI tools work. When they do not, combine the factual setup confirmation with an already-needed first-speaker playback review. Status alone never renews visibility evidence.
- Review the first speaking take of each character. Group independent remaining clips for human review only when playback is unavailable, while preserving per-clip evidence. Ask explicitly about the first word, not just whether the clip generally looks good.
- Diagnose unavailable desktop tooling or duplicate installs once per session. Do not retry a broken helper in a loop, update/reload extensions mid-job, change OS security settings, buy credits, or infer that a version notice changes installed model constraints.
- Preserve concrete raw results, requests, paths, hashes and selections. Keep failed-attempt accounting separate from recovered assets, and keep production media and checks inside the requested workspace/project.

## Verification for this update

Acceptance uses fake connectors and disposable synthetic local fixtures only. It exercises Unicode payload export, wrong-first-word rejection, actual playback evidence, recovery with zero output spending and no pending-state bypass, small trim fits, near-expiry warning and workspace-contained named directories. See [ACCEPTANCE.md](ACCEPTANCE.md) for the recorded run. These checks establish local behavior, not live generation quality.
