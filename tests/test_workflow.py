import tempfile
from pathlib import Path
import unittest

from mskill.workflow import (
    Finding,
    WorkflowError,
    add_finding,
    advance,
    gate,
    init_workflow,
    load_state,
    resolve_finding,
    save_state,
    stage_prompt,
    validate,
)


class WorkflowTests(unittest.TestCase):
    def test_happy_path_requires_both_red_team_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = init_workflow(root, "demo")
            self.assertEqual(state.stage, "architecture")
            advance(state)
            self.assertEqual(state.stage, "architecture_red_team")
            gate(state, "pass")
            self.assertEqual(state.stage, "execution")
            advance(state)
            self.assertEqual(state.stage, "final_red_team")
            gate(state, "pass")
            self.assertEqual(state.stage, "complete")

    def test_failed_architecture_gate_forces_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = init_workflow(Path(tmp), "demo")
            advance(state)
            gate(state, "fail", "ambiguous data semantics")
            self.assertEqual(state.stage, "architecture")
            self.assertEqual(state.architecture_revision, 1)

    def test_failed_final_gate_returns_to_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = init_workflow(Path(tmp), "demo")
            advance(state)
            gate(state, "pass")
            advance(state)
            gate(state, "fail", "critical result not reproducible")
            self.assertEqual(state.stage, "execution")
            self.assertEqual(state.execution_revision, 1)

    def test_cannot_bypass_red_team_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = init_workflow(Path(tmp), "demo")
            advance(state)
            with self.assertRaises(WorkflowError):
                advance(state)

    def test_state_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = init_workflow(root, "roundtrip")
            advance(state, "ready")
            save_state(root, state)
            loaded = load_state(root)
            self.assertEqual(loaded.project, "roundtrip")
            self.assertEqual(loaded.stage, "architecture_red_team")
            self.assertEqual(loaded.history[-1].note, "ready")

    def test_prompt_matches_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = init_workflow(Path(tmp), "prompt")
            self.assertIn("Build the modeling architecture only", stage_prompt(state))
            advance(state)
            self.assertIn("only architecture red-team reviewer", stage_prompt(state))
            self.assertIn("Blocker", stage_prompt(state))

    def test_findings_can_only_be_added_during_red_team_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = init_workflow(Path(tmp), "demo")
            with self.assertRaises(WorkflowError):
                add_finding(state, "blocker", "not in review")

            advance(state)
            finding = add_finding(state, "major", "validation plan is underspecified")
            self.assertEqual(finding.id, 1)
            self.assertEqual(finding.stage, "architecture_red_team")
            self.assertEqual(finding.status, "open")

    def test_unresolved_blocker_prevents_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = init_workflow(Path(tmp), "demo")
            advance(state)
            finding = add_finding(state, "blocker", "ambiguous boundary semantics")

            with self.assertRaises(WorkflowError):
                gate(state, "pass")

            self.assertEqual(state.stage, "architecture_red_team")
            resolve_finding(state, finding.id, "documented and tested both interpretations")
            gate(state, "pass")
            self.assertEqual(state.stage, "execution")

    def test_major_finding_does_not_mechanically_block_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = init_workflow(Path(tmp), "demo")
            advance(state)
            add_finding(state, "major", "limited sensitivity analysis")
            gate(state, "pass")
            self.assertEqual(state.stage, "execution")

    def test_findings_round_trip_with_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = init_workflow(root, "roundtrip-findings")
            advance(state)
            blocker = add_finding(state, "blocker", "data semantics ambiguous")
            add_finding(state, "minor", "wording can be clearer")
            resolve_finding(state, blocker.id, "semantics frozen in architecture")
            save_state(root, state)

            loaded = load_state(root)
            self.assertEqual(len(loaded.findings), 2)
            self.assertEqual(loaded.findings[0].status, "resolved")
            self.assertEqual(
                loaded.findings[0].resolution_note,
                "semantics frozen in architecture",
            )
            self.assertEqual(loaded.findings[1].id, 2)

    def test_validate_rejects_duplicate_and_malformed_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = init_workflow(Path(tmp), "validate-findings")
            state.findings = [
                Finding(
                    id=1,
                    severity="blocker",
                    stage="architecture_red_team",
                    message="first",
                ),
                Finding(
                    id=1,
                    severity="major",
                    stage="architecture_red_team",
                    message="second",
                ),
            ]
            errors = validate(state)
            self.assertIn("duplicate finding id: 1", errors)

            state.findings[1].status = "resolved"
            self.assertIn(
                "resolved finding #1 is missing resolved_at",
                validate(state),
            )


if __name__ == "__main__":
    unittest.main()
