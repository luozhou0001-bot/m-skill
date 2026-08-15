from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Literal

Stage = Literal[
    "architecture",
    "architecture_red_team",
    "execution",
    "final_red_team",
    "complete",
]
Decision = Literal["pass", "fail"]

STATE_DIR = ".mskill"
STATE_FILE = "state.json"


class WorkflowError(ValueError):
    """Raised when a workflow transition would violate the process."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Event:
    at: str
    action: str
    stage: Stage
    note: str = ""


@dataclass
class WorkflowState:
    project: str
    stage: Stage = "architecture"
    architecture_revision: int = 0
    execution_revision: int = 0
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    history: list[Event] = field(default_factory=list)

    def record(self, action: str, note: str = "") -> None:
        self.updated_at = _now()
        self.history.append(Event(self.updated_at, action, self.stage, note))

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowState":
        payload = dict(data)
        history = [Event(**event) for event in payload.pop("history", [])]
        return cls(**payload, history=history)


def state_path(root: Path) -> Path:
    return root / STATE_DIR / STATE_FILE


def init_workflow(root: Path, project: str, *, force: bool = False) -> WorkflowState:
    path = state_path(root)
    if path.exists() and not force:
        raise WorkflowError(f"workflow already exists at {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    state = WorkflowState(project=project)
    state.record("init", "Architecture phase started")
    save_state(root, state)
    return state


def load_state(root: Path) -> WorkflowState:
    path = state_path(root)
    if not path.exists():
        raise WorkflowError(f"no workflow found at {path}; run 'mskill init' first")
    data = json.loads(path.read_text(encoding="utf-8"))
    return WorkflowState.from_dict(data)


def save_state(root: Path, state: WorkflowState) -> None:
    path = state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def advance(state: WorkflowState, note: str = "") -> WorkflowState:
    transitions: dict[Stage, Stage] = {
        "architecture": "architecture_red_team",
        "execution": "final_red_team",
    }
    if state.stage not in transitions:
        raise WorkflowError(
            f"cannot advance from '{state.stage}'; red-team stages require 'mskill gate'"
        )
    previous = state.stage
    state.stage = transitions[state.stage]
    state.record("advance", note or f"Advanced from {previous}")
    return state


def gate(state: WorkflowState, decision: Decision, note: str = "") -> WorkflowState:
    if state.stage == "architecture_red_team":
        previous = state.stage
        if decision == "pass":
            state.stage = "execution"
        else:
            state.architecture_revision += 1
            state.stage = "architecture"
        state.record(f"gate:{decision}", note or f"Decision on {previous}")
        return state

    if state.stage == "final_red_team":
        previous = state.stage
        if decision == "pass":
            state.stage = "complete"
        else:
            state.execution_revision += 1
            state.stage = "execution"
        state.record(f"gate:{decision}", note or f"Decision on {previous}")
        return state

    raise WorkflowError(f"'{state.stage}' is not a red-team gate")


def stage_prompt(state: WorkflowState) -> str:
    common = (
        f"Project: {state.project}\n"
        f"Current stage: {state.stage}\n"
        "Never silently change the problem statement, data semantics, units, or evaluation metric.\n"
        "Make assumptions explicit and separate facts, assumptions, calculations, and conclusions.\n"
    )
    prompts = {
        "architecture": (
            "Build the modeling architecture only. Establish the problem interpretation, objective, "
            "variables, constraints, data semantics, validation plan, and major failure modes. "
            "Do not execute the full model yet. End with a concise architecture ready for hostile review."
        ),
        "architecture_red_team": (
            "Act as the only architecture red-team reviewer. Attack the interpretation, calculation "
            "scope, hidden assumptions, data handling, identifiability, leakage, and evaluation design. "
            "Also review from the problem setter/judge perspective. Return PASS or FAIL with blockers."
        ),
        "execution": (
            "Execute the approved architecture. The main orchestrator should decompose work, delegate "
            "specialized tasks when useful, integrate results, preserve traceability, and prevent drift. "
            "Do not bypass the final red-team gate."
        ),
        "final_red_team": (
            "Audit the completed work adversarially. Recompute or independently challenge critical "
            "claims, test edge cases, verify consistency with the original problem and data, and classify "
            "findings as Blocker/Major/Minor. Return PASS only when no unresolved Blocker remains."
        ),
        "complete": (
            "The workflow has passed final red-team review. Produce a clean handoff containing the "
            "final conclusions, reproducibility instructions, residual limitations, and artifact map."
        ),
    }
    return common + "\nInstruction:\n" + prompts[state.stage] + "\n"


def validate(state: WorkflowState) -> list[str]:
    errors: list[str] = []
    if not state.project.strip():
        errors.append("project name is empty")
    if state.architecture_revision < 0 or state.execution_revision < 0:
        errors.append("revision counters must be non-negative")
    valid_stages = {
        "architecture",
        "architecture_red_team",
        "execution",
        "final_red_team",
        "complete",
    }
    if state.stage not in valid_stages:
        errors.append(f"invalid stage: {state.stage}")
    return errors
