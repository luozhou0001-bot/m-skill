import io
import json
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import unittest

from mskill.cli import main


class CliTests(unittest.TestCase):
    def run_cli(self, root: Path, *args: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(["--root", str(root), *args])
        return code, stdout.getvalue(), stderr.getvalue()

    def state_path(self, root: Path) -> Path:
        return root / ".mskill" / "state.json"

    def read_state_json(self, root: Path) -> dict:
        return json.loads(self.state_path(root).read_text(encoding="utf-8"))

    def write_state_json(self, root: Path, data: dict) -> None:
        self.state_path(root).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_finding_cli_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "demo")[0], 0)
            self.assertEqual(self.run_cli(root, "advance")[0], 0)

            code, stdout, _ = self.run_cli(
                root,
                "finding",
                "add",
                "blocker",
                "boundary semantics are ambiguous",
            )
            self.assertEqual(code, 0)
            self.assertIn("added finding #1 [BLOCKER]", stdout)

            code, stdout, _ = self.run_cli(root, "finding", "list")
            self.assertEqual(code, 0)
            self.assertIn("#1 [BLOCKER] [open]", stdout)

            code, _, stderr = self.run_cli(root, "gate", "pass")
            self.assertEqual(code, 2)
            self.assertIn("unresolved Blocker", stderr)

            code, stdout, _ = self.run_cli(
                root,
                "finding",
                "resolve",
                "1",
                "--note",
                "interpretation frozen and tested",
            )
            self.assertEqual(code, 0)
            self.assertIn("resolved finding #1", stdout)

            code, stdout, _ = self.run_cli(root, "gate", "pass")
            self.assertEqual(code, 0)
            self.assertIn("stage: execution", stdout)

            code, stdout, _ = self.run_cli(root, "finding", "list", "--all")
            self.assertEqual(code, 0)
            self.assertIn("[resolved]", stdout)
            self.assertIn("resolution: interpretation frozen and tested", stdout)

    def test_status_reports_open_findings_and_blockers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_cli(root, "init", "demo")
            self.run_cli(root, "advance")
            self.run_cli(root, "finding", "add", "major", "limited validation")
            self.run_cli(root, "finding", "add", "blocker", "metric mismatch")

            code, stdout, _ = self.run_cli(root, "status")
            self.assertEqual(code, 0)
            self.assertIn("open_findings: 2", stdout)
            self.assertIn("open_blockers: 1", stdout)

    def test_validate_reports_missing_finding_fields_without_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_cli(root, "init", "demo")
            data = self.read_state_json(root)
            data["findings"] = [
                {
                    "id": 1,
                    "severity": "blocker",
                    "stage": "architecture_red_team",
                }
            ]
            self.write_state_json(root, data)

            code, stdout, stderr = self.run_cli(root, "validate")
            self.assertEqual(code, 2)
            self.assertEqual(stdout, "")
            self.assertIn("invalid finding at index 0", stderr)
            self.assertIn("missing", stderr)
            self.assertNotIn("Traceback", stderr)

    def test_validate_reports_bad_finding_types_without_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_cli(root, "init", "demo")
            data = self.read_state_json(root)
            data["findings"] = [
                {
                    "id": "one",
                    "severity": ["blocker"],
                    "stage": "architecture_red_team",
                    "message": 123,
                    "status": "open",
                    "created_at": "2026-08-16T00:00:00+00:00",
                    "resolved_at": None,
                    "resolution_note": 99,
                }
            ]
            self.write_state_json(root, data)

            code, stdout, stderr = self.run_cli(root, "validate")
            self.assertEqual(code, 1)
            self.assertEqual(stdout, "")
            self.assertIn("invalid finding id at index 0", stderr)
            self.assertIn("invalid severity for finding at index 0", stderr)
            self.assertIn("finding at index 0 message must be a string", stderr)
            self.assertIn("finding at index 0 resolution_note must be a string", stderr)
            self.assertNotIn("Traceback", stderr)

    def test_validate_reports_non_list_findings_without_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_cli(root, "init", "demo")
            data = self.read_state_json(root)
            data["findings"] = {"id": 1}
            self.write_state_json(root, data)

            code, stdout, stderr = self.run_cli(root, "validate")
            self.assertEqual(code, 2)
            self.assertEqual(stdout, "")
            self.assertIn("workflow findings must be a list", stderr)
            self.assertNotIn("Traceback", stderr)


if __name__ == "__main__":
    unittest.main()
