import unittest

from mskill.checks import (
    escape_github_data,
    evaluate_check,
    github_annotation,
    render_github,
)
from mskill.workflow import Finding, WorkflowState


class CheckTests(unittest.TestCase):
    def test_open_blocker_fails_but_major_and_minor_do_not(self):
        state = WorkflowState(
            project="demo",
            stage="architecture_red_team",
            findings=[
                Finding(1, "major", "architecture_red_team", "limited validation"),
                Finding(2, "minor", "architecture_red_team", "wording"),
            ],
        )
        report = evaluate_check(state)
        self.assertTrue(report.passed)
        self.assertEqual(len(report.open_blockers), 0)

        state.findings.append(
            Finding(3, "blocker", "architecture_red_team", "metric mismatch")
        )
        report = evaluate_check(state)
        self.assertFalse(report.passed)
        self.assertEqual([finding.id for finding in report.open_blockers], [3])

    def test_require_complete_fails_until_complete(self):
        state = WorkflowState(project="demo", stage="execution")
        report = evaluate_check(state, require_complete=True)
        self.assertFalse(report.passed)
        self.assertIn("--require-complete", report.completion_error or "")

        state.stage = "complete"
        report = evaluate_check(state, require_complete=True)
        self.assertTrue(report.passed)
        self.assertIsNone(report.completion_error)

    def test_github_annotation_levels_follow_severity(self):
        state = WorkflowState(
            project="demo",
            stage="architecture_red_team",
            findings=[
                Finding(1, "blocker", "architecture_red_team", "stop"),
                Finding(2, "major", "architecture_red_team", "review"),
                Finding(3, "minor", "architecture_red_team", "note"),
            ],
        )
        lines = render_github(state, evaluate_check(state))
        self.assertTrue(any(line.startswith("::error title=M-Skill Blocker #1::") for line in lines))
        self.assertTrue(any(line.startswith("::warning title=M-Skill Major #2::") for line in lines))
        self.assertTrue(any(line.startswith("::notice title=M-Skill Minor #3::") for line in lines))

    def test_github_data_escaping_blocks_workflow_command_injection(self):
        raw = "100%\r\n::error::injected"
        escaped = escape_github_data(raw)
        self.assertEqual(escaped, "100%25%0D%0A::error::injected")
        self.assertNotIn("\n", escaped)
        self.assertNotIn("\r", escaped)
        self.assertEqual(
            github_annotation("error", "M-Skill", raw),
            "::error title=M-Skill::100%25%0D%0A::error::injected",
        )

    def test_validation_errors_fail_check(self):
        state = WorkflowState(project="", stage="architecture")
        report = evaluate_check(state)
        self.assertFalse(report.passed)
        self.assertTrue(report.validation_errors)


if __name__ == "__main__":
    unittest.main()
