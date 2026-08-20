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

    def write_policy(self, root: Path, text: str) -> None:
        (root / "mskill.toml").write_text(text, encoding="utf-8")

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

    def test_status_reports_open_findings_blockers_and_policy(self):
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
            self.assertIn("policy: source=defaults; fail_on=blocker; require_complete=false", stdout)

    def test_policy_command_works_without_initialized_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, stdout, stderr = self.run_cli(root, "policy")
            self.assertEqual(code, 0)
            self.assertEqual(stderr, "")
            self.assertIn("source: defaults", stdout)
            self.assertIn("fail_on: blocker", stdout)
            self.assertIn("require_complete: false", stdout)

    def test_policy_command_reports_configured_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_policy(
                root,
                '[policy]\nfail_on = ["major", "blocker", "major"]\nrequire_complete = true\n',
            )
            code, stdout, stderr = self.run_cli(root, "policy")
            self.assertEqual(code, 0)
            self.assertEqual(stderr, "")
            self.assertIn("source: mskill.toml", stdout)
            self.assertIn("fail_on: blocker,major", stdout)
            self.assertIn("require_complete: true", stdout)

    def test_check_text_passes_without_blockers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_cli(root, "init", "demo")

            code, stdout, stderr = self.run_cli(root, "check")
            self.assertEqual(code, 0)
            self.assertEqual(stderr, "")
            self.assertIn("stage: architecture", stdout)
            self.assertIn("open_blockers: 0", stdout)
            self.assertIn("policy_failures: 0", stdout)
            self.assertTrue(stdout.rstrip().endswith("PASS"))

    def test_configured_major_can_fail_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_cli(root, "init", "demo")
            self.run_cli(root, "advance")
            self.run_cli(root, "finding", "add", "major", "limited validation")
            self.write_policy(root, '[policy]\nfail_on = ["blocker", "major"]\n')

            code, stdout, stderr = self.run_cli(root, "check")
            self.assertEqual(code, 1)
            self.assertEqual(stderr, "")
            self.assertIn("policy_failures: 1", stdout)
            self.assertIn("MAJOR #1: limited validation [FAIL]", stdout)
            self.assertTrue(stdout.rstrip().endswith("FAIL"))

    def test_configured_require_complete_is_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_cli(root, "init", "demo")
            self.write_policy(root, '[policy]\nrequire_complete = true\n')

            code, stdout, _ = self.run_cli(root, "check")
            self.assertEqual(code, 1)
            self.assertIn("requires 'complete'", stdout)

            self.run_cli(root, "advance")
            self.run_cli(root, "gate", "pass")
            self.run_cli(root, "advance")
            self.run_cli(root, "gate", "pass")

            code, stdout, _ = self.run_cli(root, "check")
            self.assertEqual(code, 0)
            self.assertIn("stage: complete", stdout)
            self.assertTrue(stdout.rstrip().endswith("PASS"))

    def test_check_github_blocker_fails_and_escapes_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_cli(root, "init", "demo")
            self.run_cli(root, "advance")
            self.run_cli(
                root,
                "finding",
                "add",
                "blocker",
                "100% coverage gap\n::error::fake",
            )

            code, stdout, stderr = self.run_cli(root, "check", "--format", "github")
            self.assertEqual(code, 1)
            self.assertEqual(stderr, "")
            self.assertIn("::error title=M-Skill Blocker #1::", stdout)
            self.assertIn("100%25 coverage gap%0A::error::fake", stdout)
            self.assertNotIn("coverage gap\n::error::fake", stdout)
            self.assertIn("M-Skill check: FAIL", stdout)

    def test_check_require_complete_cli_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_cli(root, "init", "demo")

            code, stdout, _ = self.run_cli(root, "check", "--require-complete")
            self.assertEqual(code, 1)
            self.assertIn("--require-complete", stdout)

            self.run_cli(root, "advance")
            self.run_cli(root, "gate", "pass")
            self.run_cli(root, "advance")
            self.run_cli(root, "gate", "pass")

            code, stdout, _ = self.run_cli(root, "check", "--require-complete")
            self.assertEqual(code, 0)
            self.assertIn("stage: complete", stdout)
            self.assertTrue(stdout.rstrip().endswith("PASS"))

    def test_check_github_reports_load_error_as_annotation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_cli(root, "init", "demo")
            data = self.read_state_json(root)
            data["findings"] = {"id": 1}
            self.write_state_json(root, data)

            code, stdout, stderr = self.run_cli(root, "check", "--format", "github")
            self.assertEqual(code, 2)
            self.assertEqual(stderr, "")
            self.assertIn("::error title=M-Skill state::workflow findings must be a list", stdout)
            self.assertNotIn("Traceback", stdout)

    def test_invalid_policy_is_controlled_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_cli(root, "init", "demo")
            self.write_policy(root, '[policy]\nfail_on = ["critical"]\n')

            code, stdout, stderr = self.run_cli(root, "check")
            self.assertEqual(code, 2)
            self.assertEqual(stdout, "")
            self.assertIn("invalid policy.fail_on severity", stderr)
            self.assertNotIn("Traceback", stderr)

    def test_invalid_policy_github_mode_is_annotation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_cli(root, "init", "demo")
            self.write_policy(root, '[policy]\nunknown = true\n')

            code, stdout, stderr = self.run_cli(root, "check", "--format", "github")
            self.assertEqual(code, 2)
            self.assertEqual(stderr, "")
            self.assertIn("::error title=M-Skill policy::unknown policy key", stdout)
            self.assertNotIn("Traceback", stdout)

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
