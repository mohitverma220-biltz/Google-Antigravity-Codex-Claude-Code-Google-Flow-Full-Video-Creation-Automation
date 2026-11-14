"""Local Flow production journal. No SDKs, no API keys, no generation on import.

MCP is called by Codex between prepare and record. CLI is an explicit fallback.
The connector has no idempotency key: uncertain submissions MUST stay pending.
"""
import argparse
import contextlib
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parent
IMAGE_MODELS = {"nano-banana-pro", "nano-banana-2", "nano-banana-2-lite"}
VIDEO_MODELS = {"omni-flash", "veo-3.1-lite", "veo-3.1-fast", "veo-3.1-quality"}
MODES = {"flow-text-to-image": 0, "flow-image-to-image": 10,
         "flow-text-to-video": 0, "flow-frame-to-video": 2,
         "flow-ingredients-to-video": 7}
TERMINAL = {"done", "failed", "cancelled"}
MANUAL_TRANSPORTS = {"manual_recovery", "manual_recovery_existing_flow_asset"}
PREFLIGHT_SECONDS = 900
RENEWAL_MARGIN_SECONDS = 120


class Blocked(ValueError):
    pass


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8-sig"))


def save(p, value):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)


def project_path(name):
    p = Path(name)
    return p.resolve() if p.is_dir() or p.is_absolute() else (ROOT / "projects" / p).resolve()


@contextlib.contextmanager
def locked(p):
    lock = p / ".flow.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise Blocked(f"Project locked: {lock}. Verify no runner is active before removing a stale lock.")
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        lock.unlink(missing_ok=True)


def unit_by_id(m, uid):
    return next(u for u in m["units"] if u["id"] == uid)


def take_by_id(m, tid):
    return next(t for t in m["takes"] if t["id"] == tid)


def kind(u):
    return "image" if u["settings"]["mode"].endswith("image") else "video"


def dependencies(u):
    return set(u.get("depends_on", [])) | {r["unit"] for r in u.get("references", []) if "unit" in r}


def descendants(m, uid):
    affected = {uid}
    while True:
        found = {u["id"] for u in m["units"] if dependencies(u) & affected}
        if found <= affected:
            return sorted(affected - {uid})
        affected |= found


def generation_take(t):
    """Recovered existing assets neither spend outputs nor acknowledge other jobs."""
    return t.get("transport") not in MANUAL_TRANSPORTS


def pending_submissions(m):
    return [t for t in m["takes"] if generation_take(t) and
            (not t.get("job_id") or t.get("connector_status") not in TERMINAL)]


def first_spoken_word(text):
    # Split on whitespace, not \w: Devanagari combining marks belong to the word.
    for token in text.split():
        word = token.strip('"\'“”‘’.,!?…:;—–-।')
        if word:
            return word
    raise Blocked("Dialogue needs an audible word.")


def clean_text(value):
    if isinstance(value, str) and "\ufffd" in value:
        raise Blocked("Replacement character U+FFFD found. Read UTF-8 files and export ASCII-escaped JSON; do not dispatch corrupted text.")
    if isinstance(value, dict):
        for v in value.values():
            clean_text(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            clean_text(v)


def dialogue_config(u):
    d = u.get("dialogue")
    if d is None:
        return None
    if not isinstance(d, dict) or kind(u) != "video":
        raise Blocked("dialogue must be an object on a video unit, or null.")
    for key in ("speaker", "speaker_visual", "text"):
        if not isinstance(d.get(key), str) or not d[key].strip():
            raise Blocked(f"Dialogue needs a nonempty {key}.")
    listeners = d.get("listener_visuals")
    if not isinstance(listeners, list) or any(not isinstance(v, str) or not v.strip() for v in listeners):
        raise Blocked("listener_visuals must list each visible listener, or be [] for a speaker-only shot.")
    visual_ids = [d["speaker_visual"].strip().casefold()] + [v.strip().casefold() for v in listeners]
    if len(visual_ids) != len(set(visual_ids)):
        raise Blocked("Speaker and listener visual identities must be distinct.")
    for key, low, high, default in (("pre_roll_seconds", .25, 1., .4), ("end_hold_seconds", .4, 1.5, .6)):
        n = d.get(key, default)
        if isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n) or not low <= n <= high:
            raise Blocked(f"Dialogue {key} must be {low}-{high} seconds.")
    edit = u.get("edit", {"in": 0, "out": u["settings"]["duration"]})
    if d.get("pre_roll_seconds", .4) + d.get("end_hold_seconds", .6) >= edit["out"] - edit["in"]:
        raise Blocked("Opening silence and ending hold must leave a speech window.")
    if re.search(r"(?<!\w)" + re.escape(d["text"]) + r"(?!\w)", u["prompt"]):
        raise Blocked("Put spoken text only in dialogue.text; keep the base prompt visual/performance-only.")
    first_spoken_word(d["text"])
    clean_text(d)
    return d


def generation_prompt(u):
    d = dialogue_config(u)
    if not d:
        return u["prompt"]
    lead = d.get("pre_roll_seconds", .4)
    hold = d.get("end_hold_seconds", .6)
    edit = u.get("edit", {"in": 0, "out": u["settings"]["duration"]})
    start = edit["in"] + lead
    stop = edit["out"] - hold
    listeners = "; ".join(d["listener_visuals"]) or "No visible listener"
    return (f"{u['prompt'].strip()}\n\n"
            f"Single speaking turn. Sole active speaker: {d['speaker']} — {d['speaker_visual']}.\n"
            f"Silent listeners: {listeners}.\n"
            f"From 0.00 to {start:.2f} seconds, only the planned scene ambience: all visible mouths neutral/closed, no words or lip sync. "
            "The active speaker establishes gaze and takes a small preparatory breath.\n"
            f"From about {start:.2f} seconds, ONLY the active speaker starts mouth movement and delivers the entire line, "
            "including its very first audible word. No listener speaks the first word, syllable, echo, interjection or agreement. "
            "Listeners keep mouths neutral/closed and react only through eyes, posture or restrained nods.\n"
            f"Exact dialogue, spoken once by the active speaker: \"{d['text']}\"\n"
            f"Finish every syllable and reach the supplied end composition by about {stop:.2f} seconds. "
            f"Keep the final {hold:.2f} seconds before the planned cut at {edit['out']:.2f} seconds quiet, "
            "then remain settled until the end of the generated clip: all visible mouths closed, heads and hands still, "
            "no listener reply or late head turn. "
            "The next speaker begins only in the next clip. No extra dialogue, narration, captions or unspecified music; follow the planned scene audio. "
            "Timing is approximate; do not rush, truncate or transfer a word to the listener.")


def dialogue_review(u, evidence):
    d = dialogue_config(u)
    if not d:
        return
    c = evidence.get("dialogue_checks", {})
    if (c.get("applicable") is not True or c.get("expected_speaker") != d["speaker"] or
            c.get("actual_first_word_speaker") != d["speaker"] or
            c.get("expected_first_word") != first_spoken_word(d["text"]) or
            c.get("listener_silent") is not True or c.get("exact_text") is not True):
        raise Blocked("Playback must confirm the intended speaker owns the first word and complete line, with every listener silent.")
    for key, minimum in (("opening_seconds_reviewed", max(1., d.get("pre_roll_seconds", .4) + .5)), ("ending_seconds_reviewed", .5)):
        value = c.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= u["settings"]["duration"]:
            raise Blocked(f"Dialogue playback needs {key} >= {minimum}.")
    if c.get("evidence_source") not in {"agent_playback", "user_playback"} or not isinstance(c.get("notes"), str) or not c["notes"].strip():
        raise Blocked("Record concrete agent_playback or user_playback evidence; stills/audio presence cannot verify first-word ownership.")


def validate(m):
    if m.get("schema_version") != 1 or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", m["slug"]):
        raise Blocked("Expected schema_version 1 and a lowercase slug containing letters, digits and hyphens.")
    ids = [u["id"] for u in m["units"]]
    if len(ids) != len(set(ids)) or not ids:
        raise Blocked("Unit IDs must be unique and nonempty.")
    for u in m["units"]:
        if not re.fullmatch(r"[AS]\d{2,}", u["id"]):
            raise Blocked("Use stable unit IDs such as A01 or S03.")
        s = u["settings"]
        mode, model = s["mode"], s["model"]
        if mode not in MODES or not u["prompt"].strip():
            raise Blocked("Use a supported explicit flow-* core mode and a nonempty prompt.")
        clean_text(u["prompt"])
        if not isinstance(s["outputs"], int) or not 1 <= s["outputs"] <= 4:
            raise Blocked("This installed connector supports 1-4 outputs per core Flow request.")
        video = kind(u) == "video"
        if model not in (VIDEO_MODELS if video else IMAGE_MODELS):
            raise Blocked(f"Unsupported model for {mode}: {model}")
        if s["aspect_ratio"] not in ({"9:16", "16:9"} if video else {"9:16", "16:9", "1:1", "2:3", "3:2", "4:3", "3:4"}):
            raise Blocked("Unsupported aspect ratio.")
        if video:
            duration = s["duration"]
            if duration not in ([4, 6, 8, 10] if model == "omni-flash" else [8]):
                raise Blocked("Veo is fixed at 8 seconds; Omni Flash supports 4/6/8/10.")
            if s["resolution"] not in {"360p", "720p"}:
                raise Blocked("Flow video resolution must be explicit: 360p or 720p.")
            a, b = u["edit"]["in"], u["edit"]["out"]
            if not 0 <= a < b <= duration or abs(b - a - u["screen_seconds"]) > .001:
                raise Blocked("Edit trim must fit the generation duration and equal screen_seconds.")
            if s["aspect_ratio"] != m["delivery"]["aspect_ratio"]:
                raise Blocked("Shot ratio must match delivery ratio; plan explicit crops separately.")
        dialogue_config(u)
        refs = u.get("references", [])
        limit = MODES[mode]
        if mode == "flow-ingredients-to-video":
            limit = 7 if model == "omni-flash" else (0 if model == "veo-3.1-quality" else 3)
        if len(refs) > limit or (mode in {"flow-frame-to-video", "flow-image-to-image", "flow-ingredients-to-video"} and not refs):
            raise Blocked(f"Invalid reference count for {mode}/{model}: {len(refs)} (max {limit}).")
        for r in refs:
            if not r.get("role") or ("unit" in r) == ("path" in r):
                raise Blocked("Each reference needs a role and exactly one of unit/path.")
            if r.get("kind") == "frame" and "seconds" not in r:
                raise Blocked("Frame references need a source timestamp.")
            if "unit" in r and r["unit"] in ids:
                source_kind = kind(unit_by_id(m, r["unit"]))
                if source_kind != ("video" if r.get("kind") == "frame" else "image"):
                    raise Blocked("Image references need image units; extracted frames need video units.")
        if dependencies(u) - set(ids) or u["id"] in dependencies(u):
            raise Blocked("Unknown or self dependency.")
    visited, active = set(), set()
    def visit(uid):
        if uid in active:
            raise Blocked("Dependency cycle.")
        if uid not in visited:
            active.add(uid)
            for dep in dependencies(unit_by_id(m, uid)):
                visit(dep)
            active.remove(uid)
            visited.add(uid)
    for uid in ids:
        visit(uid)
    total = sum(u.get("screen_seconds", 0) for u in m["units"])
    if abs(total - m["delivery"]["runtime_seconds"]) > .001:
        raise Blocked("Shot screen durations must sum to delivery runtime.")
    for k in ("image", "video"):
        n = sum(u["settings"]["outputs"] for u in m["units"] if kind(u) == k)
        if n > m["authorization"]["caps"][k]:
            raise Blocked(f"Planned {k} outputs exceed cap.")
    planned = {k: sum(u["settings"]["outputs"] for u in m["units"] if kind(u) == k) for k in ("image", "video")}
    base = {k: sum(kind(u) == k for u in m["units"]) for k in ("image", "video")}
    spent = {k: sum(t["settings"]["outputs"] for t in m["takes"] if generation_take(t) and t["kind"] == k) for k in base}
    return {"edit_seconds": total,
            "generated_video_seconds": sum(u["settings"]["duration"] * u["settings"]["outputs"] for u in m["units"] if kind(u) == "video"),
            "base_outputs": base, "planned_outputs": planned,
            "planned_variants": {k: planned[k] - base[k] for k in base},
            "revision_reserve": {k: m["authorization"]["caps"][k] - planned[k] for k in base},
            "committed_outputs": spent,
            "remaining_output_allowance": {k: max(0, m["authorization"]["caps"][k] - spent[k]) for k in base},
            "caps": m["authorization"]["caps"], "verified_credit_cost": None}


def cli_prefix():
    # Execute the JS entry with node.exe directly. Never pass prompts/paths to cmd.exe or PowerShell.
    shim = shutil.which("flow-auto.cmd") or shutil.which("flow-auto")
    entry = Path(shim).parent / "node_modules/flow-connector-cli/bin/flow-auto.mjs" if shim else Path("")
    node = shutil.which("node")
    if not node or not entry.is_file():
        raise Blocked("Installed flow-auto Node entry not found. Use registered MCP tools; do not install another connector.")
    return [node, str(entry)]


def native(argv):
    r = subprocess.run(argv, shell=False, capture_output=True, encoding="utf-8", errors="replace", timeout=55)
    if r.returncode:
        raise Blocked(f"Command failed ({r.returncode}): {r.stderr or r.stdout}")
    return r.stdout


def unpack(raw):
    if isinstance(raw, dict) and "content" in raw:
        raw = "\n".join(b.get("text", "") for b in raw["content"] if b.get("type") == "text")
    if isinstance(raw, str):
        try:
            return json.JSONDecoder().raw_decode(raw.lstrip())[0]
        except json.JSONDecodeError:
            return raw
    return raw


def status_check(raw, u=None):
    s = unpack(raw)
    if not isinstance(s, dict):
        raise Blocked("Unrecognized status response; preserve it and inspect the connector.")
    if s.get("bridge") != "up" or not s.get("extensionConnected") or not s.get("loggedIn") or s.get("browser") != "edge":
        raise Blocked("Open Flow in Edge, sign in, enable Flow Connector and keep its tab/window and side panel visible. Confirm before rechecking. " + json.dumps(s, ensure_ascii=False))
    if s.get("flowAccess") != "ok" or s.get("cooldownUntil"):
        raise Blocked("Flow access/cooldown requires attention; relay the returned instructions: " + json.dumps(s, ensure_ascii=False))
    if s.get("activeJobs", 0):
        raise Blocked("Connector has active jobs. Reconcile and poll them before submitting more.")
    if s.get("usedToday", 0) >= s.get("dailyLimit", float("inf")):
        raise Blocked("Daily connector allowance reached. " + json.dumps(s, ensure_ascii=False))
    if u:
        k = kind(u)
        remaining = s.get("limits", {}).get(k)
        used = s.get("usage", {}).get(k, 0)
        if remaining is None:
            raise Blocked("Status does not report a per-kind allowance. Verify remaining account capacity before submission.")
        if used + u["settings"]["outputs"] > remaining or s.get("usedToday", 0) + u["settings"]["outputs"] > s.get("dailyLimit", float("inf")):
            raise Blocked("Requested outputs exceed reported connector allowance. " + json.dumps(s, ensure_ascii=False))
    return s


def preflight_info(m, now=None):
    now = time.time() if now is None else now
    pf = m.get("preflight", {})
    age = now - pf.get("at", 0)
    remaining = PREFLIGHT_SECONDS - age
    valid = bool(pf.get("url")) and pf.get("url") == m["flow_project"].get("url") and 0 <= age <= PREFLIGHT_SECONDS
    return {"valid": valid, "expires_in_seconds": round(max(0, remaining), 1),
            "renew_before_next_submission": not valid or remaining <= RENEWAL_MARGIN_SECONDS,
            "source": pf.get("source", "unspecified"), "status_alone_can_renew": False,
            "action": "Inspect the actual visible Edge project/model/resolution/panel; use fresh user confirmation only if UI access is unavailable."}


def preflight(p, m, url, evidence, raw, source="unspecified"):
    if not re.fullmatch(r"https://(?:labs\.google|flow\.google\.com)/[^\s]*project/([^/\s?#]+)(?:[^\s]*)?", url):
        raise Blocked("Save the actual visible Flow project URL, including /project/<id>.")
    url = re.match(r"(https://[^\s]+/project/[^/?#]+)", url)[1]
    old = m["flow_project"].get("url")
    if old and old != url:
        raise Blocked("This film already owns a different Flow project. Return to that project.")
    status_check(raw)
    if source not in {"unspecified", "agent_ui", "user_confirmation"} or not evidence.strip():
        raise Blocked("Preflight needs actual UI evidence and its agent_ui or user_confirmation source.")
    m["flow_project"].update(url=url, id=re.search(r"/project/([^/?#]+)", url)[1])
    m["preflight"] = {"at": time.time(), "url": url, "evidence": evidence, "source": source,
                      "checks": ["Edge", "signed in", "project visible", "resolution set", "Flow Connector panel open"],
                      "status": raw}
    save(p / "manifest.json", m)


def selected_file(m, uid):
    u = unit_by_id(m, uid)
    if not u.get("selected_take") or u.get("stale") or u.get("needs_take"):
        raise Blocked(f"Review and select the current {uid} take first.")
    t = take_by_id(m, u["selected_take"])
    if not t.get("review", {}).get("passed"):
        raise Blocked(f"{uid} reference is not reviewed.")
    if u.get("dialogue") and generation_take(t) and t.get("dialogue") != u["dialogue"]:
        raise Blocked("Selected take used a different dialogue contract; revise and review the intended line.")
    dialogue_review(u, t["review"])
    f = t["files"][t.get("selected_file_index", 0)]
    file = Path(f["local"])
    if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != f["sha256"]:
        raise Blocked("Selected output is missing or changed: " + str(file))
    return t, file


def references(p, m, u, preview=False):
    paths, provenance = [], []
    for r in u.get("references", []):
        r = copy.deepcopy(r)
        if "path" in r:
            file = Path(r["path"])
            if not file.is_absolute():
                file = p / file
            if not preview and (not file.is_file() or not r.get("review", {}).get("passed")):
                raise Blocked("Supplied reference needs an existing file and recorded visual review: " + str(file))
        else:
            if preview and not unit_by_id(m, r["unit"]).get("selected_take"):
                tid = r["unit"] + "_T01"
                output_index = 0
                ext = ".png" if kind(unit_by_id(m, r["unit"])) == "image" else ".mp4"
                file = p / "takes" / tid / (tid + "_01" + ext)
            else:
                t, file = selected_file(m, r["unit"])
                tid = t["id"]
                output_index = t.get("selected_file_index", 0)
                r["source_sha256"] = t["files"][output_index]["sha256"]
            r["source_take"] = tid
            r["source_file_index"] = output_index
            if r.get("kind") == "frame":
                source_name = tid + (f"_O{output_index + 1:02d}" if output_index else "")
                frame = p / "assets/frames" / f'{source_name}_{r["seconds"]:.3f}.png'
                if not preview and not frame.exists():
                    meta = probe_file(file)
                    if not 0 <= r["seconds"] < meta["duration"]:
                        raise Blocked("Source frame timestamp is outside the selected clip.")
                    frame.parent.mkdir(parents=True, exist_ok=True)
                    native(["ffmpeg", "-v", "error", "-i", str(file), "-ss", str(r["seconds"]), "-frames:v", "1", str(frame)])
                    if not frame.is_file():
                        raise Blocked("Frame extraction did not create a file.")
                file = frame
        paths.append(str(file.resolve()))
        r["resolved_path"] = paths[-1]
        provenance.append(r)
    return paths, provenance


def request(p, m, u, tid, token, preview=False):
    s = u["settings"]
    prompt = generation_prompt(u)
    images, refs = references(p, m, u, preview)
    payload = {"mode": s["mode"], "prompt": prompt, "image_model": s["model"],
               "aspect_ratio": s["aspect_ratio"], "outputs": s["outputs"],
               "folder": f'codex-flow/{m["slug"]}/{tid}/{token}'}
    if images:
        payload["image_paths"] = images
    if kind(u) == "video":
        payload["duration"] = str(s["duration"])
    args = ["generate", "create", s["mode"], "--prompt", prompt,
            "--model", s["model"], "--aspect-ratio", s["aspect_ratio"],
            "--outputs", str(s["outputs"]), "--folder", payload["folder"], "--json"]
    if images:
        args += ["--image", *images]
    if kind(u) == "video":
        args += ["--duration", str(s["duration"]), "--resolution", s["resolution"]]
    clean_text(payload)
    result = {"mcp_tool": "flow_generate", "mcp_payload": payload, "cli_arguments": args,
              "cli_shell": False, "references": refs,
              "mcp_manual_settings": {"resolution": s.get("resolution"), "flow_project_url": m["flow_project"].get("url")}}
    if u.get("dialogue"):
        d = u["dialogue"]
        result["dialogue_review_expectations"] = {
            "expected_speaker": d["speaker"], "expected_first_word": first_spoken_word(d["text"]),
            "speech_window": [u["edit"]["in"] + d.get("pre_roll_seconds", .4), u["edit"]["out"] - d.get("end_hold_seconds", .6)],
            "note": "Editor/reviewer metadata only; not an additional MCP parameter or a second spoken quote."}
    return result


def prepare(p, m, uid, transport, raw_status):
    validate(m)
    if transport not in {"mcp", "cli"}:
        raise Blocked("Choose MCP or CLI fallback explicitly.")
    if not m["authorization"].get("produce") or not m["authorization"].get("request"):
        raise Blocked("A user production request with stated limits must be recorded before generation.")
    # Global gate: changing the prompt or taking another shot cannot bypass a lost acknowledgement.
    if pending_submissions(m):
        raise Blocked("An existing submission is pending/running. Reconcile it; never send it again.")
    u = unit_by_id(m, uid)
    if u.get("selected_take") and not u.get("needs_take") and not u.get("stale"):
        raise Blocked("Unit already selected. Use revise for an intentional new take.")
    previous = [t for t in m["takes"] if t["unit"] == uid and generation_take(t)]
    if previous and not u.get("needs_take") and not u.get("stale"):
        raise Blocked("Review the existing take, or use revise with a targeted change.")
    for dep in dependencies(u):
        selected_file(m, dep)
    if not preflight_info(m)["valid"]:
        raise Blocked("Refresh visible Edge project/resolution/side-panel verification with preflight (15-minute expiry).")
    status_check(raw_status, u)
    k = kind(u)
    spent = sum(t["settings"]["outputs"] for t in m["takes"] if generation_take(t) and t["kind"] == k)
    if spent + u["settings"]["outputs"] > m["authorization"]["caps"][k]:
        raise Blocked(f"Project {k} cap reached. Failed and uncertain submissions count conservatively.")
    tid = f'{uid}_T{len(previous) + 1:02d}'
    req = request(p, m, u, tid, uuid.uuid4().hex)
    t = {"id": tid, "unit": uid, "kind": k, "created_at": time.time(), "transport": transport,
         "state": "submission_pending", "job_id": None, "connector_status": None,
         "prompt": req["mcp_payload"]["prompt"], "settings": copy.deepcopy(u["settings"]),
         "flow_project": copy.deepcopy(m["flow_project"]), "request": req, "files": []}
    t["payload_sha256"] = payload_hash(req["mcp_payload"])
    if u.get("dialogue"):
        t["dialogue"] = copy.deepcopy(u["dialogue"])
    m["takes"].append(t)
    u["needs_take"] = False
    save(p / "manifest.json", m)  # The write-ahead record is durable BEFORE any external call.
    save(p / "takes" / tid / "request.json", t)
    (p / "takes" / tid / "prompt.txt").write_text(t["prompt"], encoding="utf-8")
    return t


def payload_hash(q):
    return hashlib.sha256(json.dumps(q, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")).hexdigest()


def payload(p, m, tid, candidate=None):
    """Read, never reconstruct or send, the exact immutable MCP request."""
    t = take_by_id(m, tid)
    saved = load(p / "takes" / tid / "request.json")
    if t.get("transport") != "mcp" or saved.get("id") != tid:
        raise Blocked("Payload export needs a journaled MCP take.")
    q = saved["request"]["mcp_payload"]
    clean_text(q)
    digest = payload_hash(q)
    if q != t["request"]["mcp_payload"] or any(v and v != digest for v in (saved.get("payload_sha256"), t.get("payload_sha256"))):
        raise Blocked("Saved request and ledger differ or payload hash changed; preserve evidence and do not dispatch.")
    if candidate is not None and candidate != q:
        raise Blocked("Candidate payload differs from the immutable request; do not dispatch.")
    if json.loads(json.dumps(q, ensure_ascii=True)) != q:
        raise Blocked("Payload JSON round trip failed.")
    return q


def recover(p, m, uid, file, provenance):
    """Register an existing Flow asset without forging a queue-job association."""
    if not re.fullmatch(r"[AS]\d{2,}", uid):
        raise Blocked("Recovery needs a stable unit ID such as S05.")
    u = unit_by_id(m, uid)
    src = Path(file).resolve()
    if not src.is_file() or not src.stat().st_size or not src.is_relative_to(p.resolve()):
        raise Blocked("Download the existing asset inside this project before recovery.")
    if (not isinstance(provenance, dict) or provenance.get("existing_asset") is not True or not m["flow_project"].get("url") or
            provenance.get("source_project_url") != m["flow_project"]["url"] or
            not isinstance(provenance.get("evidence"), str) or not provenance["evidence"].strip()):
        raise Blocked("Recovery needs existing_asset:true, the recorded source_project_url and concrete download/source evidence.")
    clean_text(provenance)
    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    duplicates = [t["id"] for t in m["takes"] for f in t.get("files", []) if f.get("sha256") == digest]
    if duplicates:
        raise Blocked("Exact duplicate of existing take(s): " + ", ".join(duplicates))
    count = sum(t["unit"] == uid and not generation_take(t) for t in m["takes"])
    tid = f"{uid}_R{count + 1:02d}"
    dst = p / "takes" / tid / (tid + "_01" + src.suffix.lower())
    if not dst.resolve().is_relative_to(p.resolve()):
        raise Blocked("Recovered take destination must stay inside the project.")
    dst.parent.mkdir(parents=True, exist_ok=False)
    shutil.copy2(src, dst)
    if hashlib.sha256(dst.read_bytes()).hexdigest() != digest:
        raise Blocked("Source changed during recovery; preserve both files and inspect before continuing.")
    settings = copy.deepcopy(u["settings"])
    settings.update(outputs=0, model=None, requested_model_hint=u["settings"]["model"])
    t = {"id": tid, "unit": uid, "kind": kind(u), "created_at": time.time(), "transport": "manual_recovery",
         "state": "downloaded", "job_id": None, "connector_status": "not_applicable", "prompt": None,
         "settings": settings, "flow_project": copy.deepcopy(m["flow_project"]),
         "request": {"references": [], "origin": "existing_flow_asset", "generation_request": None},
         "provenance": copy.deepcopy(provenance), "additional_generation_outputs": 0,
         "files": [{"original": str(src), "local": str(dst), "sha256": digest}]}
    m["takes"].append(t)
    save(p / "takes" / tid / "recovery.json", t)
    save(p / "manifest.json", m)
    return t


def response(raw):
    r = unpack(raw)
    if isinstance(r, dict):
        return {"job_id": r.get("jobId", r.get("id")), "status": r.get("status"), "files": r.get("files", []), "warning": r.get("error")}
    if not isinstance(r, str):
        raise Blocked("Unrecognized response; keep submission pending and inspect the saved response.")
    jid = re.search(r"Job id: ([\w-]+)", r)
    if jid:
        return {"job_id": jid[1], "status": "running", "files": []}
    if r.startswith("Generation complete. Files:"):
        files = []
        for line in r.splitlines()[1:]:
            if re.match(r"^(?:[A-Za-z]:[\\/]|/|\\\\)", line):
                files.append({"path": line})
            elif line.strip():
                break
        return {"job_id": None, "status": "done", "files": files, "warning": r}
    for state in ("failed", "cancelled"):
        if r.startswith("Generation " + state + ":"):
            return {"job_id": None, "status": state, "files": [], "warning": r}
    raise Blocked("No accepted job ID or terminal result in response. Leave pending and reconcile. " + r)


def record(p, m, tid, raw, job_id=None):
    t = take_by_id(m, tid)
    save(p / "takes" / tid / "responses" / f'{time.time_ns()}.json', raw)
    if not generation_take(t):
        raise Blocked("Recovered assets retain manual provenance; do not invent or overwrite a connector-job association.")
    r = response(raw)
    jid = job_id or r["job_id"] or t.get("job_id")
    if t.get("job_id") and jid != t["job_id"]:
        raise Blocked("Response job ID differs from the saved take.")
    if r["job_id"] and job_id and r["job_id"] != job_id:
        raise Blocked("Explicit job ID conflicts with connector response.")
    t["job_id"] = jid
    if r.get("warning"):
        t["connector_message"] = r["warning"]
    if r["status"]:
        t["connector_status"] = r["status"]
    status = t.get("connector_status")
    if status == "done":
        if not r["files"] and t["files"]:
            return
        files = []
        for i, f in enumerate(r["files"], 1):
            src = Path(f["path"])
            if not src.is_absolute() or not src.is_file() or not src.stat().st_size:
                files.append({"original": f["path"], "missing": True})
                continue
            dst = p / "takes" / tid / f'{tid}_{i:02d}{src.suffix.lower()}'
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists():
                shutil.copy2(src, dst)
            elif hashlib.sha256(dst.read_bytes()).digest() != hashlib.sha256(src.read_bytes()).digest():
                raise Blocked("Existing take output differs; preserve both and investigate before overwriting.")
            files.append({"original": str(src), "local": str(dst), "sha256": hashlib.sha256(dst.read_bytes()).hexdigest(),
                          "label": f.get("label"), "note": f.get("note")})
        t["files"] = files
        t["state"] = "downloaded" if len(files) == t["settings"]["outputs"] and all("local" in f for f in files) else "missing_download"
        if t["state"] == "downloaded" and t.get("review"):
            t["state"] = "reviewed"
    elif status in {"failed", "cancelled"}:
        t["state"] = status
    else:
        t["state"] = "submitted" if jid else "submission_pending"
    save(p / "manifest.json", m)


def matches(t, j):
    q = t["request"]["mcp_payload"]
    if j.get("mode") != q["mode"]:
        return False
    # CLI exposes the full spec; MCP lists only 60 prompt characters, so match its
    # downloaded path's unique journal token instead. A prompt prefix is NEVER enough.
    if "params" in j:
        params = j["params"]
        return (j.get("prompt") == q["prompt"] and params.get("downloadSubfolder") == q["folder"]
                and params.get("aspectRatio") == q["aspect_ratio"] and params.get("imageModel") == q["image_model"]
                and params.get("outputsPerPrompt") == q["outputs"]
                and ("duration" not in q or params.get("videoOption") == q["duration"] + "s"))
    return q["folder"].replace("\\", "/") in j.get("line", "").replace("\\", "/")


def job_rows(raw):
    r = unpack(raw)
    if isinstance(r, list):
        return r
    if isinstance(r, str):
        result = []
        for line in r.splitlines():
            match = re.match(r"^([\w-]+) (queued|waiting_for_extension|running|downloading|done|failed|cancelled) (flow-[\w-]+) ", line)
            if match:
                result.append({"id": match[1], "status": match[2], "mode": match[3], "line": line})
        return result
    raise Blocked("Unrecognized recent-jobs snapshot.")


def reconcile(p, m, raw):
    save(p / "reconciliation" / f'{time.time_ns()}-jobs.json', raw)
    jobs = job_rows(raw)
    for t in m["takes"]:
        if not generation_take(t):
            continue
        if t.get("job_id"):
            found = [j for j in jobs if j["id"] == t["job_id"]]
        else:
            found = [j for j in jobs if matches(t, j)]
        if len(found) == 1:
            j = found[0]
            t["job_id"] = j["id"]
            # A text listing is abbreviated, not a full job result: poll it next.
            if "line" not in j:
                record(p, m, t["id"], j)
            else:
                t["connector_status"] = j["status"]
                if t["state"] == "submission_pending":
                    t["state"] = "submitted"
        elif not t.get("job_id"):
            t["reconciliation"] = "ambiguous" if len(found) > 1 else "unidentified; poll candidates / inspect downloads; never resubmit"
    save(p / "manifest.json", m)
    return [{"take": t["id"], "state": t["state"], "job_id": t.get("job_id"),
             "connector_status": t.get("connector_status"), "reconciliation": t.get("reconciliation")} for t in m["takes"]]


def probe_file(file):
    meta = json.loads(native(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(file)]))
    v = next((s for s in meta["streams"] if s["codec_type"] == "video"), None)
    if not v:
        raise Blocked("No readable visual stream: " + str(file))
    w, h = v["width"], v["height"]
    rotation = next((s.get("rotation", 0) for s in v.get("side_data_list", []) if "rotation" in s), 0)
    if abs(rotation) % 180 == 90:
        w, h = h, w
    duration = float(meta.get("format", {}).get("duration", v.get("duration", 0)))
    return {"width": w, "height": h, "duration": duration,
            "video_duration": float(v.get("duration", duration)),
            "has_audio": any(s["codec_type"] == "audio" for s in meta["streams"]), "raw": meta}


def fit_trim(p, m, tid, max_shortfall=.15):
    t = take_by_id(m, tid)
    u = unit_by_id(m, t["unit"])
    if t["kind"] != "video" or t["state"] not in {"downloaded", "reviewed"} or len(t["files"]) != 1:
        raise Blocked("Small-shortfall fitting needs one downloaded video output; review multiple variants explicitly.")
    if not 0 < max_shortfall <= .2:
        raise Blocked("Small-shortfall limit must be positive and at most 0.2 seconds.")
    f = t["files"][0]
    if hashlib.sha256(Path(f["local"]).read_bytes()).hexdigest() != f["sha256"]:
        raise Blocked("Source changed before fitting; preserve and inspect it.")
    info = probe_file(f["local"])
    available = info.get("video_duration", info["duration"])
    shortfall = u["edit"]["out"] - available
    if shortfall <= 0:
        return {"changed": False}
    if shortfall > max_shortfall or available <= u["edit"]["in"]:
        raise Blocked("Shortfall is too large to fit automatically; inspect speech and revise the edit deliberately.")
    a, b = map(int, u["settings"]["aspect_ratio"].split(":"))
    if (abs(info["width"] / info["height"] - a / b) > .025 or
            min(info["width"], info["height"]) < int(u["settings"]["resolution"][:-1]) or
            (m["delivery"].get("audio_required") and not info["has_audio"])):
        raise Blocked("Fitting cannot fix wrong ratio/resolution or missing required audio.")
    before = copy.deepcopy(u["edit"])
    u["edit"]["out"] = available
    u["screen_seconds"] = available - u["edit"]["in"]
    m["delivery"]["runtime_seconds"] = round(sum(v.get("screen_seconds", 0) for v in m["units"]), 6)
    adjustment = {"at": time.time(), "take": tid, "unit": u["id"], "before": before,
                  "after": copy.deepcopy(u["edit"]), "source_sha256": f["sha256"],
                  "reason": "Small nominal-duration shortfall only; raw file/request/settings unchanged. Speech and actual ending still need playback review."}
    m.setdefault("editorial_adjustments", []).append(adjustment)
    if t.get("review"):
        t.setdefault("review_history", []).append(copy.deepcopy(t["review"]))
        t["review"] = {**t["review"], "passed": False, "trim_changed_review_required": True}
    if u.get("selected_take") and u["selected_take"] != tid:
        selected = take_by_id(m, u["selected_take"])
        if selected.get("review"):
            selected.setdefault("review_history", []).append(copy.deepcopy(selected["review"]))
            selected["review"] = {**selected["review"], "passed": False, "trim_changed_review_required": True}
    # Raw source hashes/timestamps have not changed, so avoid unnecessary regeneration.
    # The changed editorial join still needs a fresh cut review.
    for uid in descendants(m, u["id"]):
        downstream = unit_by_id(m, uid)
        if downstream.get("selected_take"):
            downstream["cut_review_required"] = f"{tid} editorial endpoint changed; raw reference frames unchanged"
    save(p / "manifest.json", m)
    return {"changed": True, **adjustment}


def probe(p, m, tid):
    t = take_by_id(m, tid)
    u = unit_by_id(m, t["unit"])
    if t["state"] not in {"downloaded", "reviewed"}:
        raise Blocked("Wait for all outputs to be downloaded before probing.")
    reports = []
    for i, f in enumerate(t["files"], 1):
        file = Path(f["local"])
        info = probe_file(file)
        a, b = map(int, t["settings"]["aspect_ratio"].split(":"))
        if abs(info["width"] / info["height"] - a / b) > .025:
            raise Blocked("Downloaded orientation/ratio does not match the request.")
        if t["kind"] == "video":
            if info["video_duration"] + .05 < u["edit"]["out"]:
                raise Blocked("Clip is too short for the requested trim.")
            if min(info["width"], info["height"]) < int(t["settings"]["resolution"][:-1]):
                raise Blocked("Downloaded video is below the requested resolution; inspect connector fallback warnings.")
        native(["ffmpeg", "-v", "error", "-i", str(file), "-f", "null", "-"])
        previews = []
        if t["kind"] == "video":
            for label, sec in (("opening", u["edit"]["in"]), ("action", (u["edit"]["in"] + u["edit"]["out"]) / 2), ("ending", max(u["edit"]["in"], u["edit"]["out"] - .15))):
                dst = p / "takes" / tid / f'review-{i:02d}-{label}.jpg'
                dst.parent.mkdir(parents=True, exist_ok=True)
                native(["ffmpeg", "-v", "error", "-y", "-i", str(file), "-ss", str(sec), "-frames:v", "1", str(dst)])
                previews.append(str(dst))
            if u.get("dialogue"):
                sec = min(u["edit"]["out"] - .05, u["edit"]["in"] + u["dialogue"].get("pre_roll_seconds", .4) + .2)
                dst = p / "takes" / tid / f"review-{i:02d}-first-word.jpg"
                native(["ffmpeg", "-v", "error", "-y", "-i", str(file), "-ss", str(sec), "-frames:v", "1", str(dst)])
                previews.append(str(dst))
        reports.append({"file": str(file), "metadata": info, "full_decode": True, "previews": previews})
    t["probe"] = reports
    save(p / "takes" / tid / "probe.json", reports)
    save(p / "manifest.json", m)
    return reports


def review(p, m, tid, evidence, select=False, index=0):
    t = take_by_id(m, tid)
    if not t.get("probe"):
        raise Blocked("Run probe before recording a review.")
    required = {"opening", "action", "ending", "identity", "motion", "continuity", "audio"}
    if not required <= set(evidence) or any(not evidence[k] for k in required):
        raise Blocked("Review must describe opening/action/ending, identity, motion, continuity and audio (including unperformed checks).")
    if select and not evidence.get("passed"):
        raise Blocked("A rejected take cannot be selected.")
    if select:
        u = unit_by_id(m, t["unit"])
        if u.get("dialogue") and generation_take(t) and t.get("dialogue") != u["dialogue"]:
            raise Blocked("Take used a different dialogue contract; do not approve it as the new line.")
        dialogue_review(unit_by_id(m, t["unit"]), evidence)
    if not 0 <= index < len(t["files"]):
        raise Blocked("Output index is out of range.")
    t["review"] = evidence
    t["state"] = "reviewed"
    if select:
        u = unit_by_id(m, t["unit"])
        # Do not select a take that was made from an upstream take since replaced.
        for r in t["request"]["references"]:
            if "unit" in r:
                current = unit_by_id(m, r["unit"]).get("selected_take")
                if current != r["source_take"] or take_by_id(m, current).get("selected_file_index", 0) != r.get("source_file_index", 0):
                    raise Blocked("Take uses an obsolete upstream selection. Revise it before selecting.")
        old = u.get("selected_take")
        old_index = take_by_id(m, old).get("selected_file_index", 0) if old else None
        t["selected_file_index"] = index
        u.update(selected_take=tid, stale=False, needs_take=False)
        if old and (old != tid or old_index != index):
            for uid in descendants(m, u["id"]):
                unit_by_id(m, uid).update(stale=True, needs_take=True, stale_reason=f"{old} output {old_index + 1} replaced by {tid} output {index + 1}")
    save(p / "manifest.json", m)
    return descendants(m, t["unit"]) if select else []


def revise(p, m, uid, prompt):
    if pending_submissions(m):
        raise Blocked("Reconcile pending jobs before revising.")
    u = unit_by_id(m, uid)
    m.setdefault("revisions", []).append({"unit": uid, "at": time.time(), "old_prompt": u["prompt"], "new_prompt": prompt,
                                          "affected_downstream": descendants(m, uid)})
    u.update(prompt=prompt, needs_take=True)
    save(p / "manifest.json", m)
    return descendants(m, uid)


def dry_run(p, m):
    estimate = validate(m)
    drafts = []
    for u in m["units"]:
        n = 1 + sum(t["unit"] == u["id"] for t in m["takes"])
        drafts.append({"unit": u["id"], "not_submitted": True,
                       **request(p, m, u, f'{u["id"]}_T{n:02d}', "DRY-RUN", preview=True)})
    save(p / "dry-run-requests.json", drafts)
    save(p / "estimate.json", estimate)
    return {"generation_calls": 0, "estimate": estimate, "requests": str(p / "dry-run-requests.json")}


def assemble(p, m):
    units = [u for u in m["units"] if kind(u) == "video"]
    if not units:
        raise Blocked("No video shots.")
    outdir = p / "deliverables" / (time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6])
    outdir.mkdir(parents=True)
    ratio = m["delivery"]["aspect_ratio"]
    w, h = (720, 1280) if ratio == "9:16" else (1280, 720)
    chunks, edit_list = [], []
    for u in units:
        t, file = selected_file(m, u["id"])
        meta = probe_file(file)
        if m["delivery"].get("audio_required") and not meta["has_audio"]:
            raise Blocked("Required audio is absent. Supply an edit/audio plan before assembly.")
        chunk = outdir / (u["id"] + ".mp4")
        args = ["ffmpeg", "-v", "error", "-ss", str(u["edit"]["in"]), "-i", str(file)]
        if not meta["has_audio"]:
            args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        args += ["-t", str(u["screen_seconds"]), "-map", "0:v:0", "-map", "0:a:0" if meta["has_audio"] else "1:a:0",
                 "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-ac", "2", str(chunk)]
        native(args)
        chunks.append(chunk)
        edit_list.append({"shot": u["id"], "take": t["id"], "source": str(file), "trim": u["edit"],
                          "audio": "native" if meta["has_audio"] else "silence (no source audio)"})
    listing = outdir / "concat.txt"
    listing.write_text("".join(f"file '{c.name}'\n" for c in chunks), encoding="utf-8")
    output = outdir / (m["slug"] + ".mp4")
    native(["ffmpeg", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(output)])
    meta = probe_file(output)
    native(["ffmpeg", "-v", "error", "-i", str(output), "-f", "null", "-"])
    if abs(meta["duration"] - m["delivery"]["runtime_seconds"]) > .15:
        raise Blocked("Export duration differs from the edit plan. Inspect the saved export.")
    report = {"output": str(output), "duration": meta["duration"], "full_decode": True, "edit_list": edit_list,
              "remaining_review": "Play the assembled export to check cut continuity, sound and final pacing."}
    save(outdir / "delivery.json", report)
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    c = sub.add_parser("init", help="Create a project from the reusable manifest and planning templates")
    c.add_argument("slug"); c.add_argument("--title", default="Untitled film")
    c.add_argument("--directory", help="Optional project folder inside this workspace, separate from the lowercase slug")
    for name in ("validate", "dry-run", "assemble", "preflight-check"):
        c = sub.add_parser(name); c.add_argument("project")
    c = sub.add_parser("preflight"); c.add_argument("project"); c.add_argument("--url", required=True)
    c.add_argument("--evidence", required=True, help="Actual evidence: visible Edge project, resolution and side panel")
    c.add_argument("--status-file", required=True, help="Fresh saved MCP status (raw result or status JSON)")
    c.add_argument("--source", choices=["agent_ui", "user_confirmation", "unspecified"], default="unspecified")
    c = sub.add_parser("prepare"); c.add_argument("project"); c.add_argument("unit")
    c.add_argument("--transport", choices=["mcp", "cli"], default="mcp"); c.add_argument("--status-file", required=True)
    c = sub.add_parser("payload", help="Print the exact immutable MCP payload as ASCII-escaped JSON; never submits")
    c.add_argument("project"); c.add_argument("take"); c.add_argument("--verify-file", help="Optional candidate JSON to compare character-for-character")
    c = sub.add_parser("recover", help="Register an existing project-local Flow download; never generates or invents a job ID")
    c.add_argument("project"); c.add_argument("unit"); c.add_argument("--file", required=True); c.add_argument("--provenance-file", required=True)
    c = sub.add_parser("record"); c.add_argument("project"); c.add_argument("take"); c.add_argument("--response", required=True)
    c.add_argument("--job", help="Only an ID verified against real connector jobs; never guess")
    c = sub.add_parser("resume"); c.add_argument("project"); c.add_argument("--jobs-file")
    c.add_argument("--cli", action="store_true", help="MCP-unavailable fallback: list and get jobs, without generation")
    c = sub.add_parser("run-cli"); c.add_argument("project"); c.add_argument("unit")
    c = sub.add_parser("probe"); c.add_argument("project"); c.add_argument("take")
    c.add_argument("--fit-shortfall", action="store_true", help="Journal an end-trim reduction of at most 0.15 s to actual video duration; playback still required")
    c = sub.add_parser("review"); c.add_argument("project"); c.add_argument("take"); c.add_argument("--evidence-file", required=True)
    c.add_argument("--select", action="store_true"); c.add_argument("--file-index", type=int, default=0)
    c = sub.add_parser("revise"); c.add_argument("project"); c.add_argument("unit"); c.add_argument("--prompt-file", required=True)
    args = ap.parse_args()
    if args.command == "init":
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", args.slug):
            raise Blocked("Use a lowercase slug containing letters, digits and hyphens.")
        p = (Path(args.directory) if args.directory else Path("projects") / args.slug)
        p = (p if p.is_absolute() else ROOT / p).resolve()
        if p == ROOT or not p.is_relative_to(ROOT):
            raise Blocked("Project directory must be a new subfolder inside this workspace.")
        p.mkdir(parents=True, exist_ok=False)
        m = load(ROOT / "templates/manifest.json")
        m.update(slug=args.slug, title=args.title)
        save(p / "manifest.json", m)
        for file in (ROOT / "templates").iterdir():
            if file.name != "manifest.json":
                shutil.copy2(file, p / file.name)
        print(p)
        return
    p = project_path(args.project)
    with locked(p):
        m = load(p / "manifest.json")
        cmd = args.command
        result = None
        if cmd in {"prepare", "preflight"} and time.time() - Path(args.status_file).stat().st_mtime > 120:
            raise Blocked("Refresh and save flow_status now; the status snapshot is over two minutes old.")
        if cmd == "validate": result = validate(m)
        elif cmd == "dry-run": result = dry_run(p, m)
        elif cmd == "preflight-check": result = preflight_info(m)
        elif cmd == "preflight": preflight(p, m, args.url, args.evidence, load(args.status_file), args.source); result = m["preflight"]
        elif cmd == "prepare": result = prepare(p, m, args.unit, args.transport, load(args.status_file))
        elif cmd == "payload": result = payload(p, m, args.take, load(args.verify_file) if args.verify_file else None)
        elif cmd == "recover": result = recover(p, m, args.unit, args.file, load(args.provenance_file))
        elif cmd == "record": record(p, m, args.take, load(args.response), args.job); result = take_by_id(m, args.take)
        elif cmd == "resume":
            if args.cli:
                jobs = json.loads(native(cli_prefix() + ["generate", "list", "--limit", "200", "--json"]))
            elif args.jobs_file:
                jobs = load(args.jobs_file)
            else:
                raise Blocked("Save flow_list_jobs to --jobs-file, or use --cli only when MCP is unavailable.")
            result = reconcile(p, m, jobs)
            if args.cli:
                for t in m["takes"]:
                    if t.get("job_id"):
                        raw = json.loads(native(cli_prefix() + ["generate", "get", t["job_id"], "--json"]))
                        record(p, m, t["id"], raw)
                result = [{"take": t["id"], "state": t["state"], "job_id": t.get("job_id")} for t in m["takes"]]
        elif cmd == "run-cli":
            prefix = cli_prefix()
            raw = json.loads(native(prefix + ["status", "--site", "flow", "--json"]))
            t = prepare(p, m, args.unit, "cli", raw)
            # On failure/timeout the saved pending intent remains. NEVER retry automatically.
            raw = json.loads(native(prefix + t["request"]["cli_arguments"]))
            record(p, m, t["id"], raw)
            result = t
        elif cmd == "probe":
            if args.fit_shortfall:
                fit_trim(p, m, args.take)
            result = probe(p, m, args.take)
        elif cmd == "review": result = {"downstream": review(p, m, args.take, load(args.evidence_file), args.select, args.file_index)}
        elif cmd == "revise": result = {"affected_downstream": revise(p, m, args.unit, Path(args.prompt_file).read_text(encoding="utf-8-sig"))}
        elif cmd == "assemble": result = assemble(p, m)
        # Windows shells may decode non-ASCII stdout under a different code page.
        # JSON escapes survive that boundary; JSON.parse restores the exact text.
        print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        main()
    except (Blocked, StopIteration, KeyError, OSError, subprocess.TimeoutExpired) as e:
        print(f"BLOCKED: {e}", file=sys.stderr)
        sys.exit(2)
