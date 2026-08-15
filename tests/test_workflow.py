import tempfile
from pathlib import Path
import unittest

from mskill.workflow import WorkflowError, advance, gate, init_workflow, load_state, save_state, stage_prompt


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


if __name__ == "__main__":
    unittest.main()
