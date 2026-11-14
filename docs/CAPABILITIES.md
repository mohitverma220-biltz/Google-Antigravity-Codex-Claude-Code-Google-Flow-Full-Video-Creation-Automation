# Installed connector capability map

Observed on **11 November 2026**. Source of truth is this installation, not remembered provider documentation. See [CLI help](discovery/cli-help.txt), [registered MCP declarations](discovery/mcp-tools.json), and the saved status snapshots. Refresh discovery if the connector changes.

CLI 1.0.14 / extension 1.3.6 reported bridge up, logged in, browser `edge`, Flow access `ok`. The initial snapshot reported connector usage 0/70 total, image 0/40 and video 0/30. These are connector plan limits; they do not establish Google credit prices, balances or account-level quotas. The free-plan message requires the Flow Connector side panel to stay open.

## Verified operations

| Production operation | MCP | Installed CLI |
|---|---|---|
| Status | `flow_status({site:"flow"})` | `flow-auto status --site flow --json` |
| Reusable new image | `flow_generate`, mode `flow-text-to-image` | `generate create flow-text-to-image` |
| Reference-derived image variation | `flow_generate`, mode `flow-image-to-image`, `image_paths` | `generate create flow-image-to-image --image ...` |
| Describe a scene without exact identity | `flow-text-to-video` | Same explicit mode |
| Exact start/end boundary | `flow-frame-to-video`, ordered `image_paths` | Same mode; `--image START END`, maximum 2 |
| Recurring product/character/location | `flow-ingredients-to-video`, `image_paths` | Same mode; `--image ...` or named `--asset ...` |
| Poll an accepted job | `flow_get_job({job_id:ID})`, repeat while nonterminal | `generate get ID --json`; `generate wait ID --timeout 1 --json` is supported, but short `get` polls keep chats responsive |
| Recent jobs / recovery | `flow_list_jobs({})` | `generate list --limit 200 --json` |
| Extract selected source frame | No exposed MCP frame tool | Local `ffmpeg -i INPUT -ss SECONDS -frames:v 1 OUTPUT.png` |
| Probe/decode/assemble | No exposed Flow edit-timeline/export tools | Installed FFprobe/FFmpeg, implemented by `probe` and `assemble` |
| Recover a manually downloaded existing Flow asset | No existing-asset download tool exposed | Local `recover`, then probe/review/select; zero new generation outputs and no invented job ID |
| Flow project selection | No project parameter | `--new-project` exists; runner intentionally reuses the recorded visible project and never silently creates one |

The local runner automates the five core image/video modes. The following advanced operations have a verified command but require a deliberate, target-specific plan and a separately saved intent/result before invocation; they are not silently substituted by the core runner:

| Advanced operation | Verified support / boundary |
|---|---|
| Extend a genuinely continuous shot | MCP `flow-extend-video` / CLI same mode; **Veo only**, acts on the clip open at `/project/<id>/edit/<clip>`. Inspect the actual project and clip before invoking. CLI offers `--extend`, `--extend-prompt`, `--step`. Extension length is not the core 8-second-shot assumption; verify actual resulting footage. |
| Edit existing video | CLI `flow-video-to-video --video FILE --model omni-flash`, source 3–10 seconds, one clip. MCP's mode enum includes it but its schema lacks `video_paths`; the intended video-edit input is not available through that schema. |
| Create reusable Flow character | CLI `flow-create-character --name NAME`, optional `--character-info`, `--voice`, `--body`; later cast with `--character NAME`. No portrait-file result promised. Reference-image create path is explicitly unverified by this installed connector. MCP lacks the character/name fields. |
| Set/revise voice | CLI `flow-set-voice --voice NAME --voice-style TEXT`, acts on the **currently open character**. Verify target. Connector describes this as no generation/no credits; no voice cloning/upload is exposed. MCP lacks these fields. |
| Upload supplied references | MCP `flow-upload-assets` with `image_paths` / CLI `--image ...`; setup action, not a planned image generation. Persist actual Flow labels and project ID. |
| Rename named asset | CLI `flow-rename-asset --asset CURRENT --name NEW`; no generation. MCP lacks name/asset arguments. |
| Scenebuilder timeline / export | No registered tool/command for clip order, trims or export. Provide exact selected clip labels/order/trims for a manual Flow edit, or use local FFmpeg when an assembly is requested. |

Prefer a sufficient registered tool. If its schema cannot represent an advanced operation, explain the missing fields and use the installed approved host CLI for that operation. Continue in the same Edge session. Do not invent MCP fields or switch to another provider.

## Actual settings and limits

- Images: `nano-banana-pro`, `nano-banana-2`, `nano-banana-2-lite`. Core image modes allow 1–4 outputs. Image-to-image accepts at most 10 input images. All seven image ratios in the MCP declaration are exposed; video ratios are only `16:9` and `9:16`.
- Videos: `omni-flash`, `veo-3.1-lite`, `veo-3.1-fast`, `veo-3.1-quality`. **Veo is fixed at 8 seconds** according to installed `generate create --help`. Omni Flash allows 4/6/8/10 seconds. The wider MCP duration enum does not make every duration valid for every model.
- Core Flow modes permit 1–4 outputs; default one. Ingredients: Omni Flash 7 refs, Veo Lite/Fast 3, **Veo Quality 0**. The latter was verified in installed `dist/mcp.js` `maxReferences()`; do not use Quality for referenced ingredients. Start/end frames: first=start, second=end.
- CLI resolution: `--resolution 360p|720p`. Internal job JSON maps the 360p UI choice to `videoResolution:"480p"`; do not interpret that wire value as a 480p Flow option. MCP exposes no resolution parameter, so verify the desired UI setting before every MCP video submission. Check downloaded dimensions for fallback.
- MCP parameter names are `mode`, `prompt`, `image_model` (also used for videos), `image_paths`, `aspect_ratio`, `duration` (string), `outputs`, `folder`. It exposes no project ID, named assets/characters, resolution, input video or voice settings.
- The optional local `dialogue` object is **not** an MCP parameter. The runner compiles it into the prompt: one active speaker, listener silence including the first word, a silent lead-in, and an end hold timed inside the edit window. This is a prompting mitigation and review contract, not a verified speech-assignment capability or guarantee. Exact line/lip sync/voice ownership still require playback.
- `folder` is a subfolder under the browser's configured Downloads location. Its description says Chrome but observed browser is Edge. Trust returned absolute paths; do not assume a different browser or a fixed download directory.
- Only modes explicitly labeled **[flow]** in `flow-auto modes` are used. Unprefixed modes target Grok.

## Result shapes and recovery limits

The installed CLI's JSON create result is `{"jobId":"..."}`. List/get expose full job objects: `id`, `status`, `mode`, `prompt`, `params` (including `downloadSubfolder`), `createdAt`, `files:[{path,kind,label?,note?}]`. Job states are queued, waiting_for_extension, running, downloading, done, failed, cancelled. These fields were verified in installed `dist/cli.js` JobSchema and command printers.

The installed MCP reporter returns **text** inside `content`:

- Pending: `Still generating … Job id: ID`; save ID, then call `flow_get_job`.
- Done: `Generation complete. Files:` followed by absolute paths; this message may omit the job ID. Recover it from `flow_list_jobs` using the unique download-folder token.
- Failure/cancel: `Generation failed: …` / `Generation cancelled: …`. Polling a known ID supplies the take association even when the message omits it.
- Recent jobs: at most 20 rows containing ID, status, mode, first 60 prompt characters and completed paths. **Not full specs**. With no completed path token, these rows cannot safely identify a lost-acknowledgement submission by prompt alone. Save candidates, poll them and wait for a token-bearing result; keep the take pending if identity remains ambiguous.

The runner preserves unrecognized responses and blocks. It never treats a truncated list, absent download or expired job history as evidence that a submission did not happen. Do not use the connector's generic `generate resume`: its retry policy differs from this workflow's conservative journal.

## Observed production limits and local improvements

Production runs showed that a connector-reported policy failure can coexist with a completed playable asset in the visible Flow project. A manually recovered clip can have verified source/download evidence, file hash and playback acceptance, but no verified queue-job association. Audit actual assets/downloads before retrying or shortening a film. The local `recover` command preserves that distinction and permits honest selection/assembly without relabelling original failures.

Nominal eight-second requests returned 7.916667-second video streams. `probe --fit-shortfall` can journal an end-only editorial fit of at most 0.15 s; it is not a new model duration option. Raw settings remain unchanged. Playback must still establish complete speech and the true cut boundary.

`payload PROJECT TAKE` exports the immutable MCP object as ASCII-escaped JSON with hash/equality checks. This fixes the observed Windows console path where an em dash became U+FFFD. The normal tool JSON parser restores the original Unicode; no prompt punctuation is deliberately simplified. A payload read is not another generation and never authorizes a duplicate submission.

`preflight-check` is a read-only expiry warning, not a browser observer. It cannot renew a project/resolution/panel check from daemon status. New extension-version notices alone do not establish new installed model support; refresh the actual schema/help before using any changed duration or operation.
