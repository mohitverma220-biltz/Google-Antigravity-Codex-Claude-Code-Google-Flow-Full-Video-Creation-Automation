"""Production lessons: local state/transport checks only; never call Flow."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import flow


STATUS = {
    "bridge": "up", "extensionConnected": True, "loggedIn": True,
    "browser": "edge", "flowAccess": "ok", "activeJobs": 0,
    "cooldownUntil": None, "usedToday": 0, "dailyLimit": 70,
    "usage": {"image": 0, "video": 0}, "limits": {"image": 40, "video": 30},
}
EVIDENCE = {
    "passed": True,
    **{key: "Synthetic review evidence only" for key in
       ("opening", "action", "ending", "identity", "motion", "continuity", "audio")},
}


class ProductionLessons(unittest.TestCase):
    def setUp(self):
        # Keep every test artifact inside this workspace, including Unicode paths.
        self.tmp = tempfile.TemporaryDirectory(prefix="lessons café नीला ", dir=flow.ROOT / "tests")
        self.addCleanup(self.tmp.cleanup)
        self.p = Path(self.tmp.name)
        self.m = flow.load(Path(__file__).parent / "fixtures/ceramicist-plan.json")
        self.m["authorization"].update(produce=True, request="Synthetic regression fixture; never call Flow")
        self.m["flow_project"].update(url="https://flow.google.com/project/LESSONS", id="LESSONS")
        self.m["preflight"] = {"at": time.time(), "url": self.m["flow_project"]["url"]}
        flow.save(self.p / "manifest.json", self.m)

    def dialogue_unit(self):
        u = flow.unit_by_id(self.m, "S01")
        u["settings"]["mode"] = "flow-text-to-video"
        u["references"] = []
        u["prompt"] = "Two fictional seated colleagues in a quiet reception. Locked camera and restrained gestures."
        u["dialogue"] = {
            "speaker": "C01",
            "speaker_visual": "woman on screen left in a black top",
            "listener_visuals": ["C02: man on screen right wearing glasses and a navy shirt"],
            "text": "Yaar, pehle ek chhota tool test karte hain.",
            "pre_roll_seconds": .4,
            "end_hold_seconds": .6,
        }
        return u

    def fake_download(self, uid, tid=None):
        u = flow.unit_by_id(self.m, uid)
        tid = tid or uid + "_T01"
        f = self.p / (tid + ".mp4")
        f.write_bytes(("Synthetic bytes for " + tid).encode("utf-8"))
        t = {
            "id": tid, "unit": uid, "kind": flow.kind(u), "transport": "mcp",
            "state": "downloaded", "job_id": "mock-" + tid, "connector_status": "done",
            "prompt": u["prompt"], "settings": copy.deepcopy(u["settings"]),
            "request": {"references": [], "mcp_payload": {"prompt": u["prompt"]}},
            "files": [{"original": str(f), "local": str(f),
                       "sha256": hashlib.sha256(f.read_bytes()).hexdigest()}],
            "probe": [True],
        }
        self.m["takes"].append(t)
        flow.save(self.p / "takes" / tid / "request.json", t)
        return t

    def dialogue_download(self):
        self.dialogue_unit()
        t = flow.prepare(self.p, self.m, "S01", "mcp", STATUS)
        f = self.p / "dialogue-test-fixture.mp4"
        f.write_bytes(b"Synthetic review fixture, not real media")
        t.update(state="downloaded", job_id="mock-dialogue", connector_status="done", probe=[True],
                 files=[{"local": str(f), "sha256": hashlib.sha256(f.read_bytes()).hexdigest()}])
        return t

    @staticmethod
    def dialogue_evidence():
        r = copy.deepcopy(EVIDENCE)
        r["dialogue_checks"] = {
            "applicable": True, "expected_speaker": "C01", "expected_first_word": "Yaar",
            "actual_first_word_speaker": "C01", "opening_seconds_reviewed": 1.5,
            "ending_seconds_reviewed": 1.0, "listener_silent": True, "exact_text": True,
            "evidence_source": "user_playback",
            "notes": "Synthetic user playback fixture: C01 owns the first word, C02 remains silent, final word finishes before the hold.",
        }
        return r

    def unicode_payload_take(self):
        u = flow.unit_by_id(self.m, "A01")
        source = self.p / "café's नीला reference.png"
        source.write_bytes(b"Synthetic reviewed reference fixture")
        u["settings"]["mode"] = "flow-image-to-image"
        u["prompt"] = 'Ceramicist’s “नीला कप” — café\nLiteral $() & ` and quotation marks.'
        u["references"] = [{"path": str(source), "role": "Synthetic identity fixture",
                            "review": {"passed": True}}]
        return flow.prepare(self.p, self.m, "A01", "mcp", STATUS)

    def test_dialogue_compiles_exact_line_once_into_both_transports(self):
        u = self.dialogue_unit()
        q = flow.request(self.p, self.m, u, "S01_T01", "mock", preview=True)
        prompt = q["mcp_payload"]["prompt"]
        self.assertEqual(prompt.count(u["dialogue"]["text"]), 1)
        self.assertIn(u["dialogue"]["speaker_visual"], prompt)
        self.assertIn(u["dialogue"]["listener_visuals"][0], prompt)
        self.assertIn("first", prompt.lower())
        self.assertIn("silent", prompt.lower())
        self.assertEqual(q["cli_arguments"][q["cli_arguments"].index("--prompt") + 1], prompt)

    def test_first_word_keeps_devanagari_combining_marks_and_speaker_only_shot(self):
        self.assertEqual(flow.first_spoken_word('“समझ रहा हूँ।”'), "समझ")
        u = self.dialogue_unit()
        u["dialogue"]["listener_visuals"] = []
        u["dialogue"]["text"] = "समझ रहा हूँ।"
        flow.validate(self.m)
        prompt = flow.request(self.p, self.m, u, "S01_T01", "mock", preview=True)["mcp_payload"]["prompt"]
        self.assertEqual(prompt.count("समझ रहा हूँ।"), 1)

    def test_dialogue_speech_window_tracks_actual_edit_in_and_out(self):
        u = self.dialogue_unit()
        u.update(edit={"in": 2, "out": 6}, screen_seconds=4)
        self.m["delivery"]["runtime_seconds"] = 12
        flow.validate(self.m)
        prompt = flow.generation_prompt(u)
        self.assertIn("2.40", prompt)  # First spoken word remains after the retained opening buffer.
        self.assertIn("5.40", prompt)  # Dialogue finishes before the retained ending hold.
        self.assertIn("6.00", prompt)
        self.assertEqual(prompt.count(u["dialogue"]["text"]), 1)
        u.update(edit={"in": 2, "out": 3}, screen_seconds=1)
        with self.assertRaises(flow.Blocked):
            flow.generation_prompt(u)

    def test_dialogue_quiet_boundaries_cover_all_visible_listeners(self):
        u = self.dialogue_unit()
        u["dialogue"]["listener_visuals"].append("C03: woman in the background wearing a gray jacket")
        prompt = flow.generation_prompt(u)
        self.assertIn("all visible mouths", prompt.lower())
        self.assertNotIn("both mouths", prompt.lower())
        for listener in u["dialogue"]["listener_visuals"]:
            self.assertIn(listener, prompt)
        self.assertEqual(prompt.count(u["dialogue"]["text"]), 1)

    def test_dialogue_quotes_newline_and_shell_characters_remain_exact_in_plain_prompt(self):
        u = self.dialogue_unit()
        text = 'Yaar, "AI tool" बनाते हैं।\nLiteral $() & ` and "drafts".'
        u["dialogue"]["text"] = text
        t = flow.prepare(self.p, self.m, "S01", "mcp", STATUS)
        q = flow.payload(self.p, self.m, t["id"])
        self.assertEqual(q["prompt"].count(text), 1)
        self.assertIn('"AI tool"', q["prompt"])
        self.assertIn('\nLiteral $() & ` and "drafts".', q["prompt"])
        args = t["request"]["cli_arguments"]
        self.assertEqual(args[args.index("--prompt") + 1], q["prompt"])
        result = subprocess.run(
            [sys.executable, "-B", str(flow.ROOT / "flow.py"), "payload", str(self.p), t["id"]],
            cwd=flow.ROOT, env={**os.environ, "PYTHONIOENCODING": "ascii"},
            capture_output=True, check=True,
        )
        roundtrip = json.loads(result.stdout.decode("ascii", errors="strict"))
        self.assertEqual(roundtrip, q)
        self.assertEqual(roundtrip["prompt"].count(text), 1)

    def test_dialogue_ambiguous_owner_and_duplicate_script_are_rejected(self):
        u = self.dialogue_unit()
        u["dialogue"]["listener_visuals"] = [u["dialogue"]["speaker_visual"]]
        with self.assertRaises(flow.Blocked):
            flow.validate(self.m)
        u = self.dialogue_unit()
        u["prompt"] += " " + u["dialogue"]["text"]
        with self.assertRaises(flow.Blocked):
            flow.validate(self.m)

    def test_short_dialogue_is_not_confused_with_a_visual_word_prefix(self):
        u = self.dialogue_unit()
        u["dialogue"]["text"] = "Hi"
        u["prompt"] = "High key lighting; the fictional colleagues remain seated."
        flow.validate(self.m)
        prompt = flow.generation_prompt(u)
        self.assertIn("High key lighting", prompt)
        self.assertEqual(prompt.count('"Hi"'), 1)
        u["prompt"] += ' The woman says "Hi".'
        with self.assertRaises(flow.Blocked):
            flow.validate(self.m)

    def test_speaker_guard_preserves_explicitly_requested_scene_music(self):
        u = self.dialogue_unit()
        requested_audio = "User-requested soft instrumental music bed beneath clear dialogue."
        u["prompt"] += " " + requested_audio
        prompt = flow.generation_prompt(u)
        self.assertIn(requested_audio, prompt)
        self.assertIn("unspecified music", prompt.lower())
        self.assertRegex(prompt.lower(), r"follow (?:the )?planned scene audio")
        self.assertNotIn("No extra dialogue, narration, captions or music.", prompt)

    def test_invalid_dialogue_timing_is_rejected(self):
        for field, values in (("pre_roll_seconds", [0, .1, 1.5, float("nan")]),
                              ("end_hold_seconds", [0, .2, 2, float("nan")])):
            for value in values:
                with self.subTest(field=field, value=value):
                    u = self.dialogue_unit()
                    u["dialogue"][field] = value
                    with self.assertRaises(flow.Blocked):
                        flow.validate(self.m)

    def test_replacement_characters_block_prompt_or_exact_dialogue(self):
        for dialogue in (False, True):
            with self.subTest(dialogue=dialogue):
                u = self.dialogue_unit()
                if dialogue:
                    u["dialogue"]["text"] = "Samajh raha hoon\ufffdjaise invoice generator."
                else:
                    u["prompt"] += " corrupted\ufffdtext"
                with self.assertRaises(flow.Blocked):
                    flow.validate(self.m)

    def test_wrong_first_word_speaker_cannot_be_selected(self):
        t = self.dialogue_download()
        r = self.dialogue_evidence()
        r["dialogue_checks"]["actual_first_word_speaker"] = "C02"
        with self.assertRaises(flow.Blocked):
            flow.review(self.p, self.m, t["id"], r, select=True)
        self.assertIsNone(flow.unit_by_id(self.m, "S01")["selected_take"])

    def test_dialogue_selection_requires_actual_playback_evidence(self):
        t = self.dialogue_download()
        bad_checks = [
            {"evidence_source": "still_frames"}, {"listener_silent": False},
            {"exact_text": False}, {"expected_first_word": "Different"},
            {"opening_seconds_reviewed": .2}, {"ending_seconds_reviewed": .1},
            {"notes": ""}, {"opening_seconds_reviewed": True},
        ]
        for updates in bad_checks:
            with self.subTest(updates=updates):
                r = self.dialogue_evidence()
                r["dialogue_checks"].update(updates)
                with self.assertRaises(flow.Blocked):
                    flow.review(self.p, self.m, t["id"], r, select=True)
        with self.assertRaises(flow.Blocked):
            flow.review(self.p, self.m, t["id"], EVIDENCE, select=True)

    def test_explicit_first_word_and_silent_listener_review_allows_selection(self):
        t = self.dialogue_download()
        flow.review(self.p, self.m, t["id"], self.dialogue_evidence(), select=True)
        self.assertEqual(flow.unit_by_id(self.m, "S01")["selected_take"], t["id"])

    def test_legacy_non_dialogue_review_still_selects(self):
        t = flow.prepare(self.p, self.m, "A01", "mcp", STATUS)
        f = self.p / "legacy-image.png"
        f.write_bytes(b"Synthetic image fixture")
        t.update(probe=[True], files=[{"local": str(f), "sha256": hashlib.sha256(f.read_bytes()).hexdigest()}])
        flow.review(self.p, self.m, t["id"], EVIDENCE, select=True)
        self.assertEqual(flow.unit_by_id(self.m, "A01")["selected_take"], t["id"])

    def test_payload_cli_roundtrips_unicode_through_ascii_stdout(self):
        t = self.unicode_payload_take()
        result = subprocess.run(
            [sys.executable, "-B", str(flow.ROOT / "flow.py"), "payload", str(self.p), t["id"]],
            cwd=flow.ROOT, env={**os.environ, "PYTHONIOENCODING": "ascii"},
            capture_output=True, check=True,
        )
        text = result.stdout.decode("ascii", errors="strict")
        exported = json.loads(text)
        self.assertEqual(exported, t["request"]["mcp_payload"])
        self.assertIn("—", exported["prompt"])
        self.assertIn("नीला", exported["image_paths"][0])

    def test_payload_rejects_corrupt_candidate_and_changed_immutable_request(self):
        t = self.unicode_payload_take()
        exported = flow.payload(self.p, self.m, t["id"])
        corrupt = copy.deepcopy(exported)
        corrupt["prompt"] = corrupt["prompt"].replace("—", "\ufffd")
        with self.assertRaises(flow.Blocked):
            flow.payload(self.p, self.m, t["id"], candidate=corrupt)
        immutable = self.p / "takes" / t["id"] / "request.json"
        changed = flow.load(immutable)
        changed["request"]["mcp_payload"]["prompt"] += " changed"
        flow.save(immutable, changed)
        with self.assertRaises(flow.Blocked):
            flow.payload(self.p, self.m, t["id"])

    def test_payload_hash_detects_matching_tampering_of_ledger_and_request(self):
        t = self.unicode_payload_take()
        immutable = self.p / "takes" / t["id"] / "request.json"
        changed = flow.load(immutable)
        changed["request"]["mcp_payload"]["prompt"] += " changed in both places"
        t["request"]["mcp_payload"] = copy.deepcopy(changed["request"]["mcp_payload"])
        flow.save(immutable, changed)
        with self.assertRaises(flow.Blocked):
            flow.payload(self.p, self.m, t["id"])

    def recovery_source(self, name="existing-closing.mp4", content=b"Synthetic existing Flow clip"):
        source = self.p / name
        source.write_bytes(content)
        provenance = {"source_project_url": self.m["flow_project"]["url"], "existing_asset": True,
                      "evidence": "Synthetic user confirms existing playable clip downloaded from the recorded project."}
        return source, provenance

    def test_recovery_preserves_failed_record_and_consumes_zero_outputs(self):
        failed = self.fake_download("S02")
        failed.update(state="failed", connector_status="failed", files=[])
        before = copy.deepcopy(failed)
        spent = sum(t["settings"]["outputs"] for t in self.m["takes"])
        source, provenance = self.recovery_source()
        t = flow.recover(self.p, self.m, "S02", source, provenance)
        self.assertEqual(t["id"], "S02_R01")
        self.assertEqual(t["transport"], "manual_recovery")
        self.assertEqual(t["settings"]["outputs"], 0)
        self.assertIsNone(t["job_id"])
        self.assertEqual(failed, before)
        self.assertEqual(sum(v["settings"]["outputs"] for v in self.m["takes"]), spent)
        self.assertEqual(Path(t["files"][0]["original"]), source)
        self.assertEqual(Path(t["files"][0]["local"]).read_bytes(), source.read_bytes())

    def test_recovery_rejects_duplicate_hash_and_wrong_project(self):
        source, provenance = self.recovery_source()
        flow.recover(self.p, self.m, "S02", source, provenance)
        duplicate, provenance = self.recovery_source("same-content-different-name.mp4")
        with self.assertRaises(flow.Blocked):
            flow.recover(self.p, self.m, "S02", duplicate, provenance)
        source, provenance = self.recovery_source("other.mp4", b"Other existing content")
        provenance["source_project_url"] = "https://flow.google.com/project/WRONG"
        with self.assertRaises(flow.Blocked):
            flow.recover(self.p, self.m, "S02", source, provenance)

    def test_recovery_rejects_path_like_unit_ids_before_any_write(self):
        source, provenance = self.recovery_source()
        for uid in ("../escape", "../../escape", "..\\escape", "S05/../../escape"):
            with self.subTest(uid=uid):
                malformed = copy.deepcopy(flow.unit_by_id(self.m, "S02"))
                malformed["id"] = uid
                self.m["units"].append(malformed)
                try:
                    with patch.object(Path, "mkdir", side_effect=AssertionError("Invalid unit must fail before mkdir")), \
                            patch.object(flow.shutil, "copy2", side_effect=AssertionError("Invalid unit must fail before copy")):
                        with self.assertRaises(flow.Blocked):
                            flow.recover(self.p, self.m, uid, source, provenance)
                finally:
                    self.m["units"].remove(malformed)
        self.assertEqual(self.m["takes"], [])
        self.assertFalse((self.p / "takes").exists())

    def test_manual_recovery_does_not_create_a_pending_generation(self):
        source, provenance = self.recovery_source()
        flow.recover(self.p, self.m, "S02", source, provenance)
        t = flow.prepare(self.p, self.m, "A01", "mcp", STATUS)
        self.assertEqual(t["id"], "A01_T01")

    def test_recovered_clip_can_be_selected_without_inventing_a_job_id(self):
        source, provenance = self.recovery_source()
        t = flow.recover(self.p, self.m, "S02", source, provenance)
        t["probe"] = [True]  # Synthetic selection fixture; no media quality claim.
        flow.review(self.p, self.m, t["id"], EVIDENCE, select=True)
        selected, file = flow.selected_file(self.m, "S02")
        self.assertEqual(selected["id"], t["id"])
        self.assertIsNone(selected["job_id"])
        self.assertEqual(selected["provenance"], provenance)
        self.assertTrue(file.is_relative_to(self.p))
        self.assertEqual(flow.pending_submissions(self.m), [])

    def test_recovered_clip_cannot_be_relabelled_as_a_connector_job(self):
        source, provenance = self.recovery_source()
        t = flow.recover(self.p, self.m, "S02", source, provenance)
        with self.assertRaises(flow.Blocked):
            flow.record(self.p, self.m, t["id"], {"id": "invented-job", "status": "done", "files": []})
        self.assertIsNone(t["job_id"])
        flow.reconcile(self.p, self.m, [])
        self.assertIsNone(t["job_id"])
        self.assertEqual(flow.pending_submissions(self.m), [])

    def test_legacy_manual_recovery_alias_remains_safe_to_reconcile(self):
        source, provenance = self.recovery_source()
        t = flow.recover(self.p, self.m, "S02", source, provenance)
        t["transport"] = "manual_recovery_existing_flow_asset"
        self.assertNotIn("mcp_payload", t["request"])
        self.assertFalse(flow.generation_take(t))
        self.assertEqual(flow.pending_submissions(self.m), [])
        flow.reconcile(self.p, self.m, [{"id": "other-job", "status": "running",
                                       "mode": "flow-text-to-image", "prompt": "Other project", "params": {}}])
        self.assertIsNone(t["job_id"])
        self.assertNotIn("reconciliation", t)
        prepared = flow.prepare(self.p, self.m, "A01", "mcp", STATUS)
        self.assertEqual(prepared["id"], "A01_T01")

    def test_recovery_cannot_clear_an_unrelated_ambiguous_submission(self):
        pending = flow.prepare(self.p, self.m, "A01", "mcp", STATUS)
        source, provenance = self.recovery_source()
        flow.recover(self.p, self.m, "S02", source, provenance)
        with self.assertRaises(flow.Blocked):
            flow.prepare(self.p, self.m, "S01", "mcp", STATUS)
        self.assertEqual(pending["state"], "submission_pending")
        self.assertIsNone(pending["job_id"])

    @staticmethod
    def measured_video(duration):
        return {"width": 720, "height": 1280, "duration": duration + .013333,
                "video_duration": duration, "has_audio": True,
                "raw": {"streams": [{"codec_type": "video", "duration": str(duration),
                                       "width": 720, "height": 1280}]}}

    def test_small_trim_fit_preserves_request_settings_and_file(self):
        t = self.fake_download("S02")
        request = self.p / "takes" / t["id"] / "request.json"
        request_before = request.read_bytes()
        settings_before = copy.deepcopy(t["settings"])
        file = Path(t["files"][0]["local"])
        bytes_before = file.read_bytes()
        with patch.object(flow, "probe_file", return_value=self.measured_video(7.916667)):
            flow.fit_trim(self.p, self.m, t["id"])
        self.assertAlmostEqual(flow.unit_by_id(self.m, "S02")["edit"]["out"], 7.916667)
        self.assertAlmostEqual(self.m["delivery"]["runtime_seconds"], 14.916667)
        self.assertEqual(request.read_bytes(), request_before)
        self.assertEqual(t["settings"], settings_before)
        self.assertEqual(file.read_bytes(), bytes_before)
        self.assertTrue(self.m["editorial_adjustments"])

    def test_large_shortfall_is_not_silently_fitted(self):
        t = self.fake_download("S02")
        before = copy.deepcopy(flow.unit_by_id(self.m, "S02")["edit"])
        with patch.object(flow, "probe_file", return_value=self.measured_video(6)):
            with self.assertRaises(flow.Blocked):
                flow.fit_trim(self.p, self.m, t["id"])
        self.assertEqual(flow.unit_by_id(self.m, "S02")["edit"], before)

    def test_trim_fit_cannot_mask_wrong_dimensions_or_missing_required_audio(self):
        t = self.fake_download("S02")
        self.m["delivery"]["audio_required"] = True
        for update in ({"width": 720, "height": 720}, {"width": 360, "height": 640}, {"has_audio": False}):
            with self.subTest(update=update):
                info = self.measured_video(7.916667)
                info.update(update)
                with patch.object(flow, "probe_file", return_value=info):
                    with self.assertRaises(flow.Blocked):
                        flow.fit_trim(self.p, self.m, t["id"])
                self.assertEqual(flow.unit_by_id(self.m, "S02")["edit"]["out"], 8)

    def test_trim_fit_requires_fresh_ending_review_and_preserves_old_review(self):
        t = self.fake_download("S02")
        t["review"] = copy.deepcopy(EVIDENCE)
        t["state"] = "reviewed"
        flow.unit_by_id(self.m, "S02")["selected_take"] = t["id"]
        with patch.object(flow, "probe_file", return_value=self.measured_video(7.916667)):
            flow.fit_trim(self.p, self.m, t["id"])
        self.assertFalse(t["review"]["passed"])
        self.assertEqual(t["review_history"][0], EVIDENCE)
        with self.assertRaises(flow.Blocked):
            flow.selected_file(self.m, "S02")

    def test_fitting_an_unselected_take_invalidates_current_selected_take_review(self):
        older = self.fake_download("S02", "S02_T01")
        selected = self.fake_download("S02", "S02_T02")
        for t in (older, selected):
            t["review"] = copy.deepcopy(EVIDENCE)
            t["state"] = "reviewed"
        unit = flow.unit_by_id(self.m, "S02")
        unit["selected_take"] = selected["id"]
        with patch.object(flow, "probe_file", return_value=self.measured_video(7.916667)):
            flow.fit_trim(self.p, self.m, older["id"])
        self.assertEqual(unit["selected_take"], selected["id"])
        self.assertAlmostEqual(unit["edit"]["out"], 7.916667)
        for t in (older, selected):
            self.assertFalse(t["review"]["passed"])
            self.assertEqual(t["review_history"][0], EVIDENCE)
        with self.assertRaises(flow.Blocked):
            flow.selected_file(self.m, "S02")

    def test_trim_fit_rejects_changed_source_hash(self):
        t = self.fake_download("S02")
        Path(t["files"][0]["local"]).write_bytes(b"Changed synthetic source")
        with patch.object(flow, "probe_file", side_effect=AssertionError("Changed source must fail before probing")):
            with self.assertRaises(flow.Blocked):
                flow.fit_trim(self.p, self.m, t["id"])

    def test_fit_does_not_lengthen_an_intentional_shorter_edit(self):
        t = self.fake_download("S02")
        u = flow.unit_by_id(self.m, "S02")
        u.update(edit={"in": 0, "out": 7}, screen_seconds=7)
        self.m["delivery"]["runtime_seconds"] = 14
        with patch.object(flow, "probe_file", return_value=self.measured_video(7.916667)):
            flow.fit_trim(self.p, self.m, t["id"])
        self.assertEqual(u["edit"], {"in": 0, "out": 7})

    def test_preflight_warning_is_read_only_and_never_renews_stale_evidence(self):
        self.m["preflight"]["at"] = 1000
        before = copy.deepcopy(self.m["preflight"])
        info = flow.preflight_info(self.m, now=1800)
        self.assertTrue(info["valid"])
        self.assertLessEqual(info["expires_in_seconds"], 100)
        self.assertTrue(info["renew_before_next_submission"])
        stale = flow.preflight_info(self.m, now=1901)
        self.assertFalse(stale["valid"])
        self.assertTrue(stale["renew_before_next_submission"])
        self.assertEqual(self.m["preflight"], before)

    def test_init_accepts_checked_workspace_directory_with_unicode_and_spaces(self):
        destination = self.p / "नया project folder"
        result = subprocess.run(
            [sys.executable, "-B", str(flow.ROOT / "flow.py"), "init", "lessons-init",
             "--title", "Unicode test film", "--directory", str(destination)],
            cwd=flow.ROOT, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
        m = flow.load(destination / "manifest.json")
        self.assertEqual(m["slug"], "lessons-init")
        self.assertEqual(m["title"], "Unicode test film")
        self.assertTrue(destination.resolve().is_relative_to(flow.ROOT))


if __name__ == "__main__":
    unittest.main()
