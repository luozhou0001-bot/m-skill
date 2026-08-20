from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .policy import Policy
from .workflow import Finding, WorkflowState, validate

CheckFormat = Literal["text", "github"]


@dataclass(frozen=True)
class CheckReport:
    validation_errors: tuple[str, ...]
    open_findings: tuple[Finding, ...]
    blocking_findings: tuple[Finding, ...]
    completion_error: str | None = None

    @property
    def open_blockers(self) -> tuple[Finding, ...]:
        return tuple(
            finding
            for finding in self.open_findings
            if finding.severity == "blocker"
        )

    @property
    def passed(self) -> bool:
        return (
            not self.validation_errors
            and not self.blocking_findings
            and self.completion_error is None
        )


def evaluate_check(
    state: WorkflowState,
    *,
    policy: Policy | None = None,
    require_complete: bool = False,
) -> CheckReport:
    active_policy = policy or Policy()
    validation_errors = tuple(validate(state))
    open_findings = tuple(
        finding
        for finding in state.findings
        if finding.status == "open"
    )
    blocking_findings = tuple(
        finding
        for finding in open_findings
        if active_policy.blocks(finding.severity)
    )

    completion_error = None
    completion_required = active_policy.require_complete or require_complete
    if completion_required and state.stage != "complete":
        completion_error = (
            f"workflow stage is '{state.stage}', but active policy/--require-complete requires 'complete'"
        )

    return CheckReport(
        validation_errors=validation_errors,
        open_findings=open_findings,
        blocking_findings=blocking_findings,
        completion_error=completion_error,
    )


def escape_github_data(value: object) -> str:
    return (
        str(value)
        .replace("%", "%25")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
    )


def escape_github_property(value: object) -> str:
    return (
        escape_github_data(value)
        .replace(":", "%3A")
        .replace(",", "%2C")
    )


def github_annotation(level: Literal["error", "warning", "notice"], title: str, message: object) -> str:
    return f"::{level} title={escape_github_property(title)}::{escape_github_data(message)}"


def _finding_level(finding: Finding) -> Literal["error", "warning", "notice"] | None:
    if finding.severity == "blocker":
        return "error"
    if finding.severity == "major":
        return "warning"
    if finding.severity == "minor":
        return "notice"
    return None


def render_text(state: WorkflowState, report: CheckReport) -> list[str]:
    lines = [
        f"project: {state.project}",
        f"stage: {state.stage}",
        f"open_findings: {len(report.open_findings)}",
        f"open_blockers: {len(report.open_blockers)}",
        f"policy_failures: {len(report.blocking_findings)}",
    ]

    for error in report.validation_errors:
        lines.append(f"ERROR: {error}")

    for finding in report.open_findings:
        severity = str(finding.severity).upper()
        marker = " [FAIL]" if finding in report.blocking_findings else ""
        lines.append(f"{severity} #{finding.id}: {finding.message}{marker}")

    if report.completion_error:
        lines.append(f"ERROR: {report.completion_error}")

    lines.append("PASS" if report.passed else "FAIL")
    return lines


def render_github(state: WorkflowState, report: CheckReport) -> list[str]:
    lines: list[str] = []

    for error in report.validation_errors:
        lines.append(github_annotation("error", "M-Skill validation", error))

    for finding in report.open_findings:
        level = _finding_level(finding)
        if level is None:
            continue
        lines.append(
            github_annotation(
                level,
                f"M-Skill {str(finding.severity).capitalize()} #{finding.id}",
                finding.message,
            )
        )

    if report.completion_error:
        lines.append(github_annotation("error", "M-Skill stage", report.completion_error))

    result = "PASS" if report.passed else "FAIL"
    safe_stage = escape_github_data(state.stage)
    lines.append(
        "M-Skill check: "
        f"{result} (stage={safe_stage}, open_findings={len(report.open_findings)}, "
        f"open_blockers={len(report.open_blockers)}, policy_failures={len(report.blocking_findings)})"
    )
    return lines


def render_check(state: WorkflowState, report: CheckReport, output_format: CheckFormat) -> list[str]:
    if output_format == "github":
        return render_github(state, report)
    return render_text(state, report)
