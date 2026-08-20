from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .checks import evaluate_check, github_annotation, render_check
from .policy import PolicyError, load_policy
from .workflow import (
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


def _root(value: str) -> Path:
    return Path(value).expanduser().resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mskill",
        description="Red-team-gated workflow control for rigorous AI-assisted modeling.",
    )
    parser.add_argument("--root", default=".", help="project root (default: current directory)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="initialize a workflow")
    p_init.add_argument("project", help="human-readable project name")
    p_init.add_argument("--force", action="store_true", help="replace existing workflow state")

    sub.add_parser("status", help="show current workflow state")
    sub.add_parser("policy", help="show the effective workflow policy")

    p_advance = sub.add_parser("advance", help="move work into the next red-team review")
    p_advance.add_argument("--note", default="")

    p_gate = sub.add_parser("gate", help="record a red-team PASS/FAIL decision")
    p_gate.add_argument("decision", choices=["pass", "fail"])
    p_gate.add_argument("--note", default="")

    p_finding = sub.add_parser("finding", help="manage structured red-team findings")
    finding_sub = p_finding.add_subparsers(dest="finding_command", required=True)

    p_finding_add = finding_sub.add_parser("add", help="record a new finding")
    p_finding_add.add_argument("severity", choices=["blocker", "major", "minor"])
    p_finding_add.add_argument("message", help="finding description")

    p_finding_list = finding_sub.add_parser("list", help="list findings")
    p_finding_list.add_argument(
        "--all",
        action="store_true",
        help="include resolved findings (default: open only)",
    )

    p_finding_resolve = finding_sub.add_parser("resolve", help="resolve a finding")
    p_finding_resolve.add_argument("id", type=int, help="finding ID")
    p_finding_resolve.add_argument("--note", default="", help="resolution note")

    p_check = sub.add_parser("check", help="evaluate workflow state for CI/PR gating")
    p_check.add_argument(
        "--format",
        dest="output_format",
        choices=["text", "github"],
        default="text",
        help="output format (default: text)",
    )
    p_check.add_argument(
        "--require-complete",
        action="store_true",
        help="require complete even if mskill.toml does not",
    )

    sub.add_parser("prompt", help="print the stage-specific orchestrator prompt")
    sub.add_parser("validate", help="validate workflow state")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = _root(args.root)
    try:
        if args.command == "init":
            state = init_workflow(root, args.project, force=args.force)
            print(f"Initialized '{state.project}' at stage: {state.stage}")
            return 0

        if args.command == "policy":
            policy = load_policy(root)
            print(f"source: {policy.source}")
            print(f"fail_on: {','.join(policy.fail_on) if policy.fail_on else 'none'}")
            print(f"require_complete: {str(policy.require_complete).lower()}")
            return 0

        state = load_state(root)

        if args.command == "status":
            policy = load_policy(root)
            open_findings = sum(1 for finding in state.findings if finding.status == "open")
            open_blockers = sum(
                1
                for finding in state.findings
                if finding.status == "open" and finding.severity == "blocker"
            )
            print(f"project: {state.project}")
            print(f"stage: {state.stage}")
            print(f"architecture_revisions: {state.architecture_revision}")
            print(f"execution_revisions: {state.execution_revision}")
            print(f"open_findings: {open_findings}")
            print(f"open_blockers: {open_blockers}")
            print(f"policy: {policy.summary()}")
            print(f"updated_at: {state.updated_at}")
            return 0

        if args.command == "advance":
            advance(state, args.note)
            save_state(root, state)
            print(f"stage: {state.stage}")
            return 0

        if args.command == "gate":
            gate(state, args.decision, args.note)
            save_state(root, state)
            print(f"stage: {state.stage}")
            return 0

        if args.command == "finding":
            if args.finding_command == "add":
                finding = add_finding(state, args.severity, args.message)
                save_state(root, state)
                print(f"added finding #{finding.id} [{finding.severity.upper()}]")
                return 0

            if args.finding_command == "list":
                findings = state.findings if args.all else [
                    finding for finding in state.findings if finding.status == "open"
                ]
                if not findings:
                    print("No findings.")
                    return 0
                for finding in findings:
                    print(
                        f"#{finding.id} [{finding.severity.upper()}] "
                        f"[{finding.status}] {finding.stage}: {finding.message}"
                    )
                    if finding.status == "resolved" and finding.resolution_note:
                        print(f"  resolution: {finding.resolution_note}")
                return 0

            if args.finding_command == "resolve":
                finding = resolve_finding(state, args.id, args.note)
                save_state(root, state)
                print(f"resolved finding #{finding.id}")
                return 0

        if args.command == "check":
            policy = load_policy(root)
            report = evaluate_check(
                state,
                policy=policy,
                require_complete=args.require_complete,
            )
            for line in render_check(state, report, args.output_format):
                print(line)
            return 0 if report.passed else 1

        if args.command == "prompt":
            print(stage_prompt(state), end="")
            return 0

        if args.command == "validate":
            errors = validate(state)
            if errors:
                for error in errors:
                    print(f"ERROR: {error}", file=sys.stderr)
                return 1
            print("OK")
            return 0

    except PolicyError as exc:
        if args.command == "check" and getattr(args, "output_format", "text") == "github":
            print(github_annotation("error", "M-Skill policy", exc))
        else:
            print(f"mskill: {exc}", file=sys.stderr)
        return 2
    except (WorkflowError, OSError, ValueError) as exc:
        if args.command == "check" and getattr(args, "output_format", "text") == "github":
            print(github_annotation("error", "M-Skill state", exc))
        else:
            print(f"mskill: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
