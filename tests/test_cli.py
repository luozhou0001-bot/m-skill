import io
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


if __name__ == "__main__":
    unittest.main()
