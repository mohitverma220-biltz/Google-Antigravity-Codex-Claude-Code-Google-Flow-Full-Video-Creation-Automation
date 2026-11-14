# Continuity and asset plan

Inventory supplied files before planning new generations. Record only cut-critical details.

| Asset ID | Role | Supplied/generated/extracted | Stable details | Review / selected take |
|---|---|---|---|---|
| A01 | Product identity | Choose | Silhouette, rim, handle, markings, color | Pending |

Keep wardrobe, holding hand, screen direction and key light consistent where visible.
Product identity references: uncluttered background. Start frames: delivery ratio and action-ready composition.
Frame inputs: record source selected take, timestamp, extracted file and why that boundary fits the edit.

Each shot in manifest.json records story purpose, screen/generation duration, start/end state, framing, action, camera, audio, references and acceptance criteria. Keep one readable action per clip.

## Dialogue ownership and handoffs

| Character ID | Visual identifier | Screen position | Voice | Quiet listener behavior |
|---|---|---|---|---|
| C01 | Clothing + distinguishing features | Lock for scene | Stable description | Neutral/closed lips, eyes/posture only |
| C02 | Clothing + distinguishing features | Lock for scene | Stable description | Neutral/closed lips, eyes/posture only |

For each turn, name one sole speaker and every visible listener. Assign the complete line, including its first word, to that speaker. Names alone do not bind saved Flow characters/voices. Use the optional local `dialogue` object from `dialogue-shot.json`; do not invent MCP fields.

Default opening: 0.4 s silent lead-in. Both mouths start neutral/closed; the intended speaker establishes gaze or a preparatory breath and alone begins mouth movement after the lead-in. Listeners remain silent throughout: no opening word, echo, lip sync or interjection. Allow restrained closed-mouth reactions.

Default ending: finish the complete line, then hold the matched quiet pose for 0.6 s. Both mouths neutral/closed; no late head turn or next-speaker mouth opening. The shared boundary must support both the prior ending and the next silent lead-in. Reuse a suitable reviewed frame; extra boundary images/retries count against the cap.

The first-word mitigation needs actual playback validation; it is not a guaranteed model behavior. Review the first 1–2 s, whole line and last second of every dialogue take. Record the actual first-word speaker and reviewer. If a two-shot repeatedly confuses ownership, consider speaker-focused framing in the next authorized plan rather than repeating identical requests.
