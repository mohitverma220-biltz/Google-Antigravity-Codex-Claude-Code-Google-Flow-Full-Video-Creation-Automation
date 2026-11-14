# Google Flow video recipe: idea to a reviewed scene

Use this recipe for dialogue or narration videos made in the user's signed-in Microsoft Edge Google Flow session. Codex plans and reviews; Flow generates. This document is a reusable procedure, not authorization to generate a particular film.

The sequence is: **collect inputs → time the script → lock continuity → create individual images → animate with start/end frames → review each clip → assemble when requested → verify delivery**.

## Step 1 — Collect the creative brief

Use [the intake form](../templates/video-intake.md). Reuse information the user has already given. Ask for missing essentials together; ask a focused follow-up only when the answer materially changes the film or the spending required.

| Input | What to record |
|---|---|
| Raw idea | The user's idea in their own words, required story beats, ending and any exact wording. |
| Audience and purpose | Who should watch, what they should feel or understand, and any call to action. |
| Video type | Hyper-realistic, real-life-like, 3D animation, 2D animation or another specified style. |
| Final duration | The finished edit length, such as 6, 8, 10, 15, 20, 30, 40 or 60 seconds. This is separate from generated footage length. |
| Posting destination | Platform **and format**, for example Instagram Reel, YouTube Short or YouTube landscape video. Record aspect ratio, resolution and room for interface overlays/captions. |
| Characters | Existing saved Flow characters, the user's own saved avatar, supplied references, or AI-selected characters. Record the number of speaking characters. |
| Speech | Character dialogue, narration, mixed or silent; language, accent, voice qualities, pronunciation and any exact lines. |
| Visual planning option | One foundation image, or a storyboard of separate images. For the storyboard, ask whether 5–6 dialogue turns is a preference or a firm requirement. |
| Setting and sound | Location, time of day, ambience and required sound effects. **No instrumental background music unless requested.** |
| Supplied assets | Actual files, existing Flow assets, brand material and their distinct reference roles. |
| Limits and delivery | Image-output cap, video-output cap, revisions included, no additional spending unless explicitly authorized, and clips only versus an assembled film. |

Suggest 9:16 for a vertical short and 16:9 for a landscape video when the format makes that choice clear. Record the assumption. Check current platform requirements during a real production if exact upload limits or interface safe areas matter.

Inventory supplied assets before planning new ones. Verify saved characters in the actual Flow project rather than assuming a name is available or recreating an existing character.

**Output:** a brief with resolved essentials, recorded assumptions, asset inventory and production limits. A request to prepare a recipe or plan leaves production authorization false.

## Step 2 — Write and time the script

Choose character dialogue or narration from the brief. Structure a short film around an opening, development and payoff, with complexity suited to the requested runtime.

For dialogue, make each numbered entry **one uninterrupted speaking turn by one character**. Put the next speaker in the next entry. Split a long turn before creating its storyboard frames. For narration, use numbered narration segments instead. A silent film uses numbered action beats.

Do not force 5–6 dialogue turns into every runtime. A six-second film may need only one short turn and a reaction. A longer film can support more turns. If a fixed frame count conflicts with natural delivery, resolve that conflict before image generation.

Use this script table. Each row must describe both the speaker and any visible listeners.

| ID | Edit window / seconds | Speaker | Exact spoken words | Speaker performance | Listener performance | Action and sound |
|---|---|---|---|---|---|---|
| D01 | Start–end / budget | Character or narrator | Dialogue/narration in the chosen language | Mood, tone, energy, pace, expression, gaze, posture and gesture | Mood, gaze, expression and body language; silent unless scripted | One readable action, ambience, pause/reaction time |

For a narrator, record voice performance in the speaker column and the on-screen characters' reactions in the listener/action columns.

Time the words aloud at the intended delivery pace. Include breaths, pauses, turn-taking, reactions and the ending hold. Word counts are only a drafting aid: language, emotion and pronunciation change delivery time. Shorten an overfull line rather than instructing unnaturally fast speech.

Record a stable voice description per character. Give each character a distinct voice where requested; listeners must not speak the active character's line. Reserve enough time to finish the sentence before the cut.

### Assign every word to one speaker

Post-project user feedback identified a recurring handoff risk: the listener may appear to deliver the first word before the intended speaker takes over. The cause has not been isolated or verified for a particular model. Treat **ownership of the first audible word** as a separate acceptance check. A correct remainder of the sentence does not make a misplaced opening word acceptable.

For every dialogue turn, record one stable character ID, an unambiguous visual description of its speaker, and the visual identities of all listeners. Use screen position, visible clothing and distinguishing features together, for example `C01, the woman on screen left in the black top` and `C02, the man on screen right wearing glasses and a navy shirt`. A name or a bare pronoun alone is insufficient. Keep these IDs and screen positions consistent across the script, continuity sheet and prompts; an ID is a local cue, not a verified saved-character binding in Flow.

Default to a **0.4-second silent lead-in** and a **0.6-second quiet ending hold**. A useful planning range is 0.35–0.6 seconds for the opening and 0.5–0.7 seconds for the ending. Include both in the existing clip duration, rather than adding extra outputs. Time the line within the remaining speech window; shorten an overfull line instead of speeding it up or cutting a word. Verify the actual downloaded endpoint, since nominal eight-second clips can be slightly shorter.

During the opening lead-in, both mouths stay neutral/closed while the intended speaker takes a small preparatory breath or establishes gaze. Only that speaker begins mouth movement and delivers the whole line after the lead-in, including its first word. Every listener stays silent for the entire clip: no first word, echoed syllable, lip sync, interjection, laugh or verbal agreement unless it is a separately scripted speaking turn. Listener reactions use eyes, posture, closed-mouth smiles or restrained nods.

The next speaker begins only in the next clip. Do not instruct the listener to be “ready to reply,” open their mouth or start an answer at the previous clip's endpoint. After the current speaker's final syllable, both people settle with mouths neutral/closed for the ending hold. Keep the same quiet pose at the shared boundary image.

These cues are a proposed mitigation, not a guarantee of correct voice assignment. They were added from the project's observed issue; no new Flow generation is part of this workflow update. Test the first speaking take for each character and enforce the opening-word check on every later take. If a shared two-shot keeps confusing ownership, prefer a speaker-focused medium close-up with the listener in profile, soft focus or outside the mouth-readable area. Plan that framing before image generation where possible; any extra frame or retry still needs room in the existing cap.

The optional per-unit planning fragment is [dialogue-shot.json](../templates/dialogue-shot.json):

```json
{
  "dialogue": {
    "speaker": "C01",
    "speaker_visual": "The woman on screen left in the black top",
    "listener_visuals": ["C02: the man on screen right wearing glasses and a navy shirt"],
    "text": "Yaar, pehle ek chhota tool test karte hain.",
    "pre_roll_seconds": 0.4,
    "end_hold_seconds": 0.6
  }
}
```

Keep the exact Hinglish words in `text`. With this object configured, put only visual, scene and performance directions in the unit's base `prompt`; do not paste the same spoken line there. The runner compiles the ownership/timing directions and one exact quoted line into the final request. Duplicating `dialogue.text` in the base prompt is rejected. These fields are local planning data, not additional Flow MCP parameters. Keep expected first-word/reviewer metadata outside the spoken line; do not quote the first word separately or insert stage directions into `text`.

The validated configuration ranges are 0.25–1.0 s for `pre_roll_seconds` and 0.4–1.5 s for `end_hold_seconds`; both must leave a positive speech window inside the **planned edit-in/out**, not just the longer generation duration. For example, an eight-second generation edited from 2–6 s uses a 2.4–5.4 s speech window with the default buffers. Reach the end composition before the hold and stay settled through the remaining generated time. Inspect the actual cut frames; a prompt does not prove the endpoint was reached on time. The narrower planning defaults above are recommendations, not evidence that a specific Flow take will obey them. Legacy non-dialogue plans without this optional object remain supported.

The saved request's local `dialogue_review_expectations` provides the expected speaker/first word and speech window without adding them to the spoken text or the MCP schema. Review the opening relative to the actual edit-in. A longer lead-in requires enough opening playback to include the first word, not just the silence.

**Timing rule:** the sum of all edit windows equals the final requested runtime. Each complete spoken turn and its reaction must fit its window without cutting a word.

Finalize the exact words and performance directions before generating images. A production request authorizes work within its recorded limits; it does not require a second blanket confirmation after the script is prepared. Ask only about a material unresolved choice or a necessary change to those limits.

**Output:** the timed script, with D01…DN and a performance direction for every turn.

## Step 3 — Lock character, setting and audio continuity

Record the following in the project's continuity sheet and reuse the relevant details in every image and video prompt:

- **Identity:** reviewed source reference, face, hair, age appearance, build and distinguishing features for each character.
- **Clothing:** exact garments, colors, footwear, jewelry and accessories.
- **Scene:** set layout, character positions, screen direction, background people and their positions, furniture, props and who holds each object.
- **Light and style:** time of day, light direction and quality, color palette, weather, ambience and rendering style.
- **Performance:** the scene's emotional arc, each character's voice and energy, and the intentional mood change at each turn.
- **Sound:** a consistent environmental sound description, recurring sound sources and the absence of music unless requested.

Keep identities, wardrobe and the physical setting stable. Let expressions, gestures and emotion develop according to the script. Track intentional changes, such as moving a cup from the table to a character's hand, as explicit start/end states.

Give references distinct roles: character identity, wardrobe, setting, prop, composition, start boundary or end boundary. Review essential references visually before using them.

**Existing-character access:** the registered MCP generator accepts local image paths but has no named-character or voice-setting parameter. A character name in a prompt alone is not a verified binding to its saved Flow identity. Use reviewed references associated with the actual saved character. If named casting or saved-voice selection is essential, use a target-specific, journaled installed-CLI workflow with the supported fields and host approvals. The current core runner does not serialize named-character or voice fields; adding an arbitrary manifest key will not enable them. See [capabilities](CAPABILITIES.md).

**Output:** the continuity sheet and reviewed reference inventory.

## Step 4 — Plan the image boundaries

### Option A: individual storyboard images

For a dialogue film, keep **N dialogue entries = N storyboard images = N video clips**. Frame F01 opens D01, F02 opens D02, and so on. For narration or a silent film, substitute numbered narration segments or action beats.

Each frame is a separate image file, never a contact sheet, collage or grid. It depicts the composition and physical state at the **start** of its assigned turn. The clip carries the dialogue, movement and change into the next frame.

For dialogue boundaries, both characters' lips must be neutral/closed. The next turn's opening image must not show its listener mid-speech. A shared image that ends one clip and opens the next is a quiet handoff pose, not the first speaking pose. Reuse an already reviewed boundary that supports this state; do not silently add an extra “handoff image.” Generate a replacement only when the existing pose cannot support a clean handoff, with the affected image/video outputs counted against the cap.

There is one necessary endpoint decision: N storyboard frames provide only N−1 adjacent transitions. The final dialogue still needs a clip and an end state.

| Clip | Spoken entry | Start image | End image |
|---|---|---|---|
| S01 | D01 | F01 | F02 |
| S02 | D02 | F02 | F03 |
| … | … | … | … |
| SN | DN | FN | E01, the closing endpoint |

E01 is a **technical closing image**, not another dialogue or storyboard panel. Show the intended final reaction, pose or resolved action. It can be a reviewed supplied image, a suitable existing reviewed frame, or one additional generated image. Include any generated endpoint in the image cap and estimate.

If the final turn is a hold or a small motion that returns naturally to its opening pose, FN may also serve as its end image. Record that choice explicitly. Do not end the last clip at F01 unless the user wants a loop.

Plan neighboring frames so the same people, set and props can move plausibly between them. Favor small camera changes within a continuous scene. A large angle or location change can produce an unwanted transformation during interpolation; redesign that boundary before spending on a clip.

### Option B: one foundation image

Create or select one image F01 establishing the complete cast, wardrobe, scene and lighting.

For a strict one-image production, plan **F01 as both start and end** for each clip, and verify that the selected Flow mode accepts reusing that image in both slots. Design each dialogue turn around subtle gestures, facial expression and motion that can return naturally to that composition. Describe the emotional development in each clip prompt.

This approach restricts cumulative movement and prop changes, and can look repetitive across several clips. If the mode requires distinct endpoint images, or the story requires changing positions, angles or object states, propose derived boundary images and include their outputs in the cap before generation. Selecting one foundation image does not silently authorize extra images.

**Output:** an image list, a start/end mapping for every clip, and an explicit final endpoint choice.

## Step 5 — Choose settings, estimate outputs and create the project plan

Verify the installed model/mode constraints before a real production. The [installation evidence](CAPABILITIES.md), captured on 11 November 2026, records:

| Setting | Recorded support |
|---|---|
| Image generation | `flow-text-to-image` or `flow-image-to-image`; Nano Banana models listed in the capability map. |
| Start/end animation | `flow-frame-to-video`; first input image is start, second is end. |
| Video aspect ratio | 9:16 or 16:9. |
| Veo duration | 8 seconds per generated clip. |
| Omni Flash duration | 4, 6, 8 or 10 seconds per generated clip. |
| Resolution | Explicit supported choice; MCP has no resolution field, so verify it in visible Edge. |
| Output count | Set explicitly; plan one output per request unless variants are authorized. |

An exposed duration enum does not mean every model supports every duration. Verify the chosen model supports the required start/end operation and speech/audio in the account; tool declarations alone do not demonstrate exact dialogue, lip sync or voice persistence. Review the first speaking clip before continuing.

Separate the estimates:

- **Edit seconds:** the runtime the viewer receives.
- **Generated seconds:** all footage generated, including discarded footage and revisions.
- **Image outputs:** storyboard/foundation images, any generated closing endpoint, extra references, variants and revision reserve.
- **Video outputs:** one per planned clip, plus authorized variants and revision reserve.

For example, five dialogue entries using five eight-second clips make a **40-second** edit with five storyboard images and one generated closing endpoint: **6 image outputs + 5 video outputs**, before reference creation or revisions. If the endpoint is a suitable existing image, it does not require another image generation.

For a 30-second edit, five six-second clips are an option only if the verified model supports the required operation and audio. Five eight-second clips generate 40 seconds and require ten seconds of trimming. **Trimming early can remove the planned end boundary.** Inspect the actual frames at every proposed edit in/out point. Replan the durations or revise the transition within the cap if matching boundaries and complete speech cannot both be preserved. Never assume that adjacent reference images guarantee a seamless cut after trimming.

Create `projects/<slug>/` with the existing runner. Fill the brief, continuity sheet, manifest, shot list, script, image plan and edit list. Use A01… for runner image units and S01… for video units; F01… and E01 are creative labels mapped to those A-units. Keep image units at zero screen seconds. In each video's ordered references, put the start A-unit first and the end A-unit second. Record image and clip dependencies so a revision can flag affected work.

Record the exact production request and output caps in the manifest; leave `produce:false` for planning. Run `validate` and `dry-run` before any submission. Show any unresolved decisions and the remaining revision reserve. Do not invent credit prices or equate connector limits with Google credit balances.

**Output:** a validated, dry-run plan with an affordable sequence of ready units. No generation is needed to complete this planning stage.

## Step 6 — Generate and review the images

Follow the [production procedure](PRODUCTION.md) for every submission. Use one recorded Flow project throughout the film.

Generate the foundation or first storyboard frame first. Inspect identities, clothing, set layout, light, hands, objects and composition; select the take only after review. Use its reviewed references to create the later images, keeping the continuity details explicit. Generate each remaining storyboard frame as its own image output, then review the closing endpoint.

Use this image-prompt structure:

```text
Create one individual [ratio] [visual style] image for frame [ID].
Reference roles: [reviewed identity / wardrobe / setting / prop sources].
Characters and wardrobe: [locked details].
Setting, background people, props and lighting: [locked details].
Opening state for dialogue [D-ID]: [positions, gaze, expressions, object states].
Speech boundary: both mouths neutral/closed; no one is already speaking or about to interject.
Composition and camera: [framing and screen direction].
Preserve the reference identities and scene layout.
No collage, panels, dialogue bubbles, captions or added text.
```

Review adjacent frames together. Correct an identity, costume, lighting or prop discontinuity before generating a clip that depends on it. Every essential start and end image must have a selected reviewed file.

**Output:** separate reviewed image files and recorded selected take IDs.

## Step 7 — Animate one dialogue turn per clip

Always use the planned **start image → end image** mapping for this recipe. In `flow-frame-to-video`, provide exactly the two ordered image paths, even when both refer to the same foundation image. Set the explicit model, ratio, supported generation duration and output count. Verify resolution in Edge.

Use this final request structure. When `dialogue` is configured, the runner compiles the speaker, timing and exact-text parts; the base `prompt` supplies the scene, action and performance details without another copy of the dialogue:

```text
Only [stable speaker ID + unambiguous visual identification] speaks in this clip.
That character owns the whole line, including its first audible word.
All listeners: [stable IDs + visual descriptions]; silent for the entire clip.
Animate from the supplied start composition to the supplied end composition.
Scene and continuity: [locked identities, wardrobe, set, light and prop states].
Opening lead-in [0.4 s by default]: both mouths neutral/closed, no speech;
the intended speaker establishes gaze/takes a small preparatory breath.
After the lead-in only the intended speaker starts mouth movement and says,
once in [language/accent]: "[exact D-ID words]"
Speaker performance: [mood, tone, energy, pace, expression, gaze and gesture].
Listener performance: [eyes/posture/closed-mouth reaction]; no speech, lip sync,
opening word, echoed syllable or interjection, including before the speaker starts.
Action progression: [opening state → one readable action → end state].
Camera and movement: [small deliberate motion; boundary direction and pace].
Timing: [lead-in interval, complete line in speech window, ending hold].
After the final syllable, settle into the end image and hold quietly for
[0.6 s by default]. Both mouths neutral/closed; the listener does not begin
the next turn or make a late head turn just before the cut.
Audio: [stable voice description, ambient sound and required sound effects].
No extra speech, captions or instrumental background music.
```

For narration, identify an off-screen narrator and specify that visible characters do not deliver the narration with their mouths. Replace the exact-dialogue line with the exact narration segment.

For example, the compiled Hinglish request can identify `C02, the man on screen right wearing glasses and a navy shirt` as the sole speaker, identify the woman on screen left as a silent listener, then quote **once**: `"Samajh raha hoon. Pehle job ke saath ek tool test karo."` Keep the runner-derived expected first word in the script/review record, not as an additional utterance in the prompt. Do not append another character's line or a fragment such as an opening “Haan” to bridge clips.

The operational loop is mandatory:

1. Check fresh `flow_status({site:"flow"})` and separately verify the correct signed-in project, resolution and visible open Connector side panel in Edge. Save actual preflight evidence.
2. Choose one ready unit whose essential references are reviewed and selected.
3. Run `prepare --transport mcp` to journal its immutable request **before** sending.
4. Read that request's saved `mcp_payload` and call `flow_generate` exactly once. Immediately save the full response and `record` it.
5. Poll the known job with `flow_get_job`; save and record the responses. Polling never means another generation call.
6. `probe` the returned files, inspect the image boundaries, play the action and listen to all speech and sound. Replay the first 1–2 seconds with attention to each face and the first audible word; review the last second for a complete final syllable and a quiet hold. Record the actual first-word speaker and evidence source. A voice/lip-sync ownership mismatch fails the take even if the remaining words are correct. Select only an acceptable take.
7. Review the first speaking take for each character before committing later work that relies on that voice/performance. Every dialogue take still needs its own first-word ownership check. Continue ready independent work only within the recorded review and cap rules.

For CLI fallback, use the runner's journaled `run-cli` procedure for supported core fields. Target-specific advanced actions need their own saved intent/result. Remain in the same Edge Flow session.

**Output:** reviewed clips S01…SN, one exact scripted turn per clip, with complete request and result records.

## Step 8 — Check each cut, revise and assemble when requested

For each clip, check identity, wardrobe, anatomy, props, lighting, action, exact words, speaker assignment, language, pronunciation, voice, lip sync where applicable and completion of speech before the cut.

Use the dialogue checks in [the review template](../templates/review.json). Record the expected speaker/runner-derived first word, **actual observed first-word speaker**, opening and ending intervals played, whether every listener stayed silent, whether the exact line passed, and who performed the playback review. For a unit with `dialogue` configured, selection requires `applicable: true`, the correct expected first word, `actual_first_word_speaker` equal to the configured speaker ID, `listener_silent: true`, `exact_text: true`, at least 1.0 opening seconds (or lead-in + 0.5 s if greater) and 0.5 ending seconds reviewed, concrete nonempty notes, and `evidence_source` set to `agent_playback` or `user_playback`. Measure the opening from the actual edit-in and include the first word. Aim to play the full first 1–2 seconds and last second, not merely those minimum thresholds.

Watching a muted frame sequence or detecting a non-silent audio track does not establish word ownership. If playback/listening is unavailable, leave these checks pending and ask one focused playback question that names the intended first-word speaker; do not mark them passed from stills or a generic unscoped approval. A user confirmation counts only when its question explicitly covered these checks; record the actual response and reviewed intervals in the notes.

On a wrong-speaker opening, preserve the take. First tighten the ownership wording and quiet handoff timing for the next authorized take; avoid changing identity, scene, dialogue and camera at once. If repeated confusion requires speaker-focused framing or a changed boundary, plan the affected references before another submission. Never remove or dub a stray listener word and claim the original take passed. Any audio repair requires an explicit edit plan, review of the repaired result and no unrequested provider switch. Stop for a specific cap decision if the correction cannot fit the existing limit.

For every join, compare the outgoing and incoming frames at the **actual edit points**. Check pose, gaze, prop location, camera direction and motion. Listen across the join for voice changes, clipped syllables, duplicated speech, ambience jumps and unwanted music. Matching still images do not establish smooth movement or continuous sound.

Use targeted revisions for failed checks. Preserve previous takes and change the smallest relevant input. A changed storyboard frame affects clips that use it as either a start or an end. Record those dependencies; selecting a replacement flags downstream units stale. Include the affected work in the remaining cap before submitting anything else.

When an assembled film is requested, use the selected clips in script order and the recorded in/out points. The local `assemble` command trims and joins clips with FFmpeg. Native audio is concatenated; it does not automatically maintain a continuous ambience bed, match different voices or add sound crossfades. Plan and perform any necessary audio editing explicitly. Add captions, graphics or requested music according to the edit plan.

Flow timeline ordering/export is not exposed by the installed connector. Use local assembly or provide exact clip labels and trim points for a manual Flow edit.

**Output:** selected clips and an edit list; an assembled export only when requested and actually created.

## Step 9 — Verify and deliver

Probe and decode the actual export, then watch and listen to it from beginning to end. Check the final runtime, aspect ratio, resolution, dialogue, cuts, continuity and sound. Document any check that could not be performed; do not label it passed.

Deliver actual file links, selected take IDs, clip order, verified source durations, in/out points, final export if requested and the remaining image/video reserve. Preserve raw outputs, prompts, reference provenance, original download paths and earlier takes.

If interrupted, reconcile saved pending submissions with real jobs and downloads before continuing. Never resubmit an ambiguous take or use the connector's generic `generate resume`. At disconnection, preserve state and ask the user to open Flow in Edge, sign in, enable Flow Connector, keep the tab/window and side panel visible, then confirm before rechecking. Wait through cooldowns without duplicate submissions; stop at account or project caps without buying credits.

## Copyable request for a future film

```text
Plan a video about [raw idea].
Audience/purpose: [details]. Style: [video type].
Final duration: [seconds]. Destination: [platform + format], [ratio].
Characters: [saved names / supplied references / AI-selected], [number].
Speech: [dialogue/narration/silent], [language/accent], [voice guidance].
Visual plan: [one foundation / N separate dialogue frames].
Setting and mood: [details]. Audio: [ambience]; no instrumental music.
Supplied assets: [files or actual Flow asset labels].
Proposed caps: [images] image outputs and [videos] video outputs,
including revisions. No additional spending.
Use the start/end-frame recipe. Show timing, closing endpoint,
continuity, output estimate and edit plan. Validate and dry-run only.
```

To authorize execution later, use **“Produce this video…”** with the project and explicit caps; specify **“assemble and deliver the final film”** if an export is wanted. Revision and resume requests follow the workspace's existing entry points.
