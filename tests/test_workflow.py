"""Acceptance tests use an in-memory connector and temporary local files only."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import shutil
from unittest.mock import patch

import flow


STATUS = {"bridge": "up", "extensionConnected": True, "loggedIn": True,
          "browser": "edge", "flowAccess": "ok", "activeJobs": 0,
          "cooldownUntil": None, "usedToday": 0, "dailyLimit": 70,
          "usage": {"image": 0, "video": 0}, "limits": {"image": 40, "video": 30}}
EVIDENCE = {"passed": True, **{k: "Synthetic test evidence only" for k in
            ("opening", "action", "ending", "identity", "motion", "continuity", "audio")}}


class FakeConnector:
    def __init__(self):
        self.calls = []
        self.jobs = []

    def generate(self, payload):
        self.calls.append(copy.deepcopy(payload))
        params = {"downloadSubfolder": payload["folder"], "aspectRatio": payload["aspect_ratio"],
                  "imageModel": payload["image_model"], "outputsPerPrompt": payload["outputs"]}
        if "duration" in payload:
            params["videoOption"] = payload["duration"] + "s"
        job = {"id": "mock-job-001", "status": "running", "mode": payload["mode"],
               "prompt": payload["prompt"], "params": params, "files": [], "createdAt": int(time.time() * 1000)}
        self.jobs.append(job)
        return {"jobId": job["id"]}


class WorkflowAcceptance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="flow acceptance café ")
        self.addCleanup(self.tmp.cleanup)
        self.p = Path(self.tmp.name)
        self.m = flow.load(Path(__file__).parent / "fixtures/ceramicist-plan.json")
        self.m["authorization"].update(produce=True, request="Synthetic test, never call real connector")
        self.m["flow_project"].update(url="https://labs.google/fx/tools/flow/project/MOCK", id="MOCK")
        self.m["preflight"] = {"at": time.time(), "url": self.m["flow_project"]["url"]}
        flow.save(self.p / "manifest.json", self.m)

    def test_15_second_dry_run_has_exact_payloads_and_zero_calls(self):
        # Any accidental attempt to execute a real connector fails the test immediately.
        with patch.object(flow, "native", side_effect=AssertionError("Dry run attempted an external command")):
            r = flow.dry_run(self.p, self.m)
        self.assertEqual(r["generation_calls"], 0)
        self.assertEqual(r["estimate"]["edit_seconds"], 15)
        self.assertEqual(r["estimate"]["generated_video_seconds"], 16)
        self.assertEqual(r["estimate"]["base_outputs"], {"image": 1, "video": 2})
        self.assertEqual(r["estimate"]["planned_variants"], {"image": 0, "video": 0})
        self.assertEqual(r["estimate"]["revision_reserve"], {"image": 0, "video": 1})
        requests = flow.load(self.p / "dry-run-requests.json")
        self.assertEqual([r["mcp_payload"]["mode"] for r in requests],
                         ["flow-text-to-image", "flow-ingredients-to-video", "flow-frame-to-video"])
        self.assertTrue(requests[1]["mcp_payload"]["image_paths"][0].endswith("A01_T01_01.png"))
        self.assertTrue(requests[2]["mcp_payload"]["image_paths"][0].endswith("S01_T01_7.000.png"))
        self.assertEqual(requests[2]["references"][0]["source_take"], "S01_T01")
        self.assertEqual(self.m["takes"], [])

    def test_crash_after_first_acceptance_before_id_never_submits_twice(self):
        backend = FakeConnector()
        t = flow.prepare(self.p, self.m, "A01", "mcp", STATUS)
        accepted = backend.generate(t["request"]["mcp_payload"])
        self.assertEqual(accepted["jobId"], "mock-job-001")
        # Simulated process interruption: do not record the returned acknowledgement.
        restarted = flow.load(self.p / "manifest.json")
        self.assertIsNone(restarted["takes"][0]["job_id"])
        self.assertEqual(restarted["takes"][0]["state"], "submission_pending")
        flow.reconcile(self.p, restarted, backend.jobs)
        self.assertEqual(restarted["takes"][0]["job_id"], "mock-job-001")
        for _ in range(3):
            with self.assertRaises(flow.Blocked):
                flow.prepare(self.p, restarted, "A01", "mcp", STATUS)
            flow.reconcile(self.p, restarted, backend.jobs)
        self.assertEqual(len(backend.calls), 1)
        self.assertEqual(len(restarted["takes"]), 1)

    def test_crash_before_send_empty_list_keeps_pending(self):
        flow.prepare(self.p, self.m, "A01", "mcp", STATUS)
        restarted = flow.load(self.p / "manifest.json")
        flow.reconcile(self.p, restarted, [])
        with self.assertRaises(flow.Blocked):
            flow.prepare(self.p, restarted, "A01", "mcp", STATUS)
        self.assertEqual(restarted["takes"][0]["state"], "submission_pending")

    def test_mcp_truncated_prompt_is_not_identity_but_folder_token_is(self):
        t = flow.prepare(self.p, self.m, "A01", "mcp", STATUS)
        q = t["request"]["mcp_payload"]
        prefix = q["prompt"][:60]
        raw = {"content": [{"type": "text", "text": f'mock-job-001 running {q["mode"]} "{prefix}" '}]}
        flow.reconcile(self.p, self.m, raw)
        self.assertIsNone(t["job_id"])
        path = "C:/Downloads/" + q["folder"] + "/cup.png"
        raw["content"][0]["text"] = f'mock-job-001 done {q["mode"]} "{prefix}" {path}'
        flow.reconcile(self.p, self.m, raw)
        self.assertEqual(t["job_id"], "mock-job-001")
        # Text list alone never pretends that a file has been ingested.
        self.assertEqual(t["state"], "submitted")

    def test_multiple_matches_leave_ambiguous_pending(self):
        t = flow.prepare(self.p, self.m, "A01", "mcp", STATUS)
        backend = FakeConnector()
        backend.generate(t["request"]["mcp_payload"])
        other = copy.deepcopy(backend.jobs[0]); other["id"] = "mock-job-002"
        flow.reconcile(self.p, self.m, backend.jobs + [other])
        self.assertIsNone(t["job_id"])
        self.assertEqual(t["reconciliation"], "ambiguous")

    def test_response_forms_and_missing_download_not_success(self):
        t = flow.prepare(self.p, self.m, "A01", "mcp", STATUS)
        raw = {"content": [{"type": "text", "text": "Still generating — normal. Job id: mock-job-001\nCall flow_get_job"}]}
        flow.record(self.p, self.m, t["id"], raw)
        self.assertEqual(t["job_id"], "mock-job-001")
        flow.record(self.p, self.m, t["id"], {"id": "mock-job-001", "status": "done", "files": [{"path": str(self.p / "absent.png")}]})
        self.assertEqual(t["state"], "missing_download")
        with self.assertRaises(flow.Blocked):
            flow.probe(self.p, self.m, t["id"])

    def test_complete_mcp_download_copies_original_without_inventing_job_id(self):
        t = flow.prepare(self.p, self.m, "A01", "mcp", STATUS)
        src = self.p / "download café's cup.png"; src.write_bytes(b"synthetic non-media fixture")
        raw = {"content": [{"type": "text", "text": f"Generation complete. Files:\n{src}\nWarning: test fixture only"}]}
        flow.record(self.p, self.m, t["id"], raw)
        self.assertEqual(t["state"], "downloaded")
        self.assertIsNone(t["job_id"])
        self.assertEqual(Path(t["files"][0]["local"]).read_bytes(), src.read_bytes())
        with self.assertRaises(flow.Blocked):
            flow.prepare(self.p, self.m, "S01", "mcp", STATUS)

    def test_unicode_multiline_prompt_and_windows_paths_are_exact_native_arguments(self):
        u = flow.unit_by_id(self.m, "A01")
        u["prompt"] = 'Ceramicist’s “नीला कप” — café\nDialogue: "It\'s ready."\nLiteral $() & ` and spaces.'
        r = flow.request(self.p, self.m, u, "A01_T01", "test", preview=True)
        args = r["cli_arguments"]
        self.assertEqual(args[args.index("--prompt") + 1], u["prompt"])
        winpath = "C:\\Users\\Mohit Verma\\Café's cups\\नीला.png"
        echoed = subprocess.run([sys.executable, "-c", "import sys,json; print(json.dumps(sys.argv[1:],ensure_ascii=True))", u["prompt"], winpath],
                                shell=False, capture_output=True, check=True, encoding="utf-8")
        self.assertEqual(json.loads(echoed.stdout), [u["prompt"], winpath])

    def test_limits_durations_and_quality_ingredients_are_enforced(self):
        u = flow.unit_by_id(self.m, "S01")
        u["settings"]["duration"] = 6
        with self.assertRaises(flow.Blocked): flow.validate(self.m)
        u["settings"]["duration"] = 8
        u["settings"]["model"] = "veo-3.1-quality"
        with self.assertRaises(flow.Blocked): flow.validate(self.m)

    def test_authorization_preflight_cooldown_and_cap_stop_submission(self):
        self.m["authorization"]["produce"] = False
        with self.assertRaises(flow.Blocked): flow.prepare(self.p, self.m, "A01", "mcp", STATUS)
        self.m["authorization"]["produce"] = True
        self.m["preflight"]["at"] = 0
        with self.assertRaises(flow.Blocked): flow.prepare(self.p, self.m, "A01", "mcp", STATUS)
        self.m["preflight"]["at"] = time.time()
        with self.assertRaises(flow.Blocked): flow.prepare(self.p, self.m, "A01", "mcp", {**STATUS, "cooldownUntil": 9999999999999})
        t = flow.prepare(self.p, self.m, "A01", "mcp", STATUS)
        flow.record(self.p, self.m, t["id"], {"id": "mock-job-001", "status": "failed", "files": []})
        flow.revise(self.p, self.m, "A01", "Simpler rim and handle.")
        with self.assertRaises(flow.Blocked): flow.prepare(self.p, self.m, "A01", "mcp", STATUS)

    def selected_fixture(self, uid, tid):
        file = self.p / (tid + ".png"); file.write_bytes(tid.encode())
        t = {"id": tid, "unit": uid, "kind": flow.kind(flow.unit_by_id(self.m, uid)),
             "settings": copy.deepcopy(flow.unit_by_id(self.m, uid)["settings"]),
             "state": "reviewed", "job_id": "mock-" + tid, "connector_status": "done",
             "request": {"references": []}, "review": EVIDENCE.copy(), "probe": [True],
             "files": [{"local": str(file), "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}]}
        self.m["takes"].append(t)
        flow.unit_by_id(self.m, uid)["selected_take"] = tid
        return t

    def test_revision_keeps_takes_and_invalidates_frame_dependent_shot(self):
        self.selected_fixture("A01", "A01_T01")
        self.selected_fixture("S01", "S01_T01")
        downstream = self.selected_fixture("S02", "S02_T01")
        downstream["request"]["references"] = [{"unit": "S01", "source_take": "S01_T01", "kind": "frame", "seconds": 7}]
        affected = flow.revise(self.p, self.m, "S01", "Simplify the turn and hold still sooner.")
        self.assertEqual(affected, ["S02"])
        newer = self.selected_fixture("S01", "S01_T02")
        flow.unit_by_id(self.m, "S01")["selected_take"] = "S01_T01"
        flow.review(self.p, self.m, newer["id"], EVIDENCE, select=True)
        self.assertTrue(flow.unit_by_id(self.m, "S02")["stale"])
        self.assertEqual(flow.unit_by_id(self.m, "S02")["selected_take"], "S02_T01")
        self.assertIn("S01_T01", [t["id"] for t in self.m["takes"]])
        with self.assertRaises(flow.Blocked): flow.selected_file(self.m, "S02")
        with self.assertRaises(flow.Blocked): flow.review(self.p, self.m, downstream["id"], EVIDENCE, select=True)

    def test_reference_review_required_and_project_lock_serializes_writers(self):
        with self.assertRaises(flow.Blocked): flow.prepare(self.p, self.m, "S01", "mcp", STATUS)
        with flow.locked(self.p):
            with self.assertRaises(flow.Blocked):
                with flow.locked(self.p): pass

    def test_switching_output_within_one_take_invalidates_downstream(self):
        asset = self.selected_fixture("A01", "A01_T01")
        self.selected_fixture("S01", "S01_T01")
        file = self.p / "second-output.png"; file.write_bytes(b"second synthetic output")
        asset["files"].append({"local": str(file), "sha256": hashlib.sha256(file.read_bytes()).hexdigest()})
        flow.review(self.p, self.m, asset["id"], EVIDENCE, select=True, index=1)
        self.assertTrue(flow.unit_by_id(self.m, "S01")["stale"])
        self.assertTrue(flow.unit_by_id(self.m, "S02")["stale"])

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "Existing local FFmpeg/FFprobe required")
    def test_local_media_probe_frame_extraction_and_15_second_assembly(self):
        # Purely synthetic local test footage; no Flow call and no production cup media.
        for uid, color in (("S01", "blue"), ("S02", "cyan")):
            t = self.selected_fixture(uid, uid + "_T01")
            video = self.p / (uid + "-synthetic.mp4")
            flow.native(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color=c={color}:s=720x1280:r=10:d=8",
                         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(video)])
            t["files"] = [{"local": str(video), "sha256": hashlib.sha256(video.read_bytes()).hexdigest()}]
            t["state"] = "downloaded"
            reports = flow.probe(self.p, self.m, t["id"])
            self.assertTrue(reports[0]["full_decode"])
            self.assertEqual(len(reports[0]["previews"]), 3)
        paths, provenance = flow.references(self.p, self.m, flow.unit_by_id(self.m, "S02"))
        self.assertTrue(Path(paths[0]).is_file())
        self.assertEqual(provenance[0]["source_take"], "S01_T01")
        self.assertEqual(provenance[0]["seconds"], 7)
        result = flow.assemble(self.p, self.m)
        self.assertTrue(Path(result["output"]).is_file())
        self.assertLess(abs(result["duration"] - 15), .15)
        self.assertEqual([row["take"] for row in result["edit_list"]], ["S01_T01", "S02_T01"])


if __name__ == "__main__":
    unittest.main()
