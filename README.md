# M-Skill

**Red-team-gated workflow control for rigorous AI-assisted mathematical modeling.**

M-Skill is a tiny Python CLI that turns a modeling task into a process that an AI agent cannot casually skip:

`Architecture → Architecture Red Team → Execution → Final Red Team → Complete`

A failed review automatically sends the work back for revision. The state is persisted in `.mskill/state.json`, so the workflow is auditable and resumable across sessions and agents.

## Why this exists

AI-assisted modeling often fails because the model starts calculating before the problem is understood, silently changes data semantics, or treats its own result as validation. M-Skill makes the review gates explicit and machine-checkable.

It is designed for mathematical modeling competitions, research prototypes, simulation/optimization tasks, and any Codex/agent workflow where **problem interpretation is part of correctness**.

## Features

- Python 3.10+; standard-library TOML parsing on Python 3.11+, `tomli` compatibility on Python 3.10
- Persistent workflow state and revision counters
- Architecture red-team gate before full execution
- Final adversarial audit before completion
- Structured Blocker/Major/Minor findings with resolution tracking
- PASS decisions mechanically blocked by unresolved Blockers
- Project-level CI policy configuration through `mskill.toml`
- GitHub Actions / PR check output with native annotations
- CI-friendly exit codes and optional completion enforcement
- Stage-specific prompts for Codex/agent orchestration
- Explicit PASS/FAIL decisions with audit notes
- CI-tested transition, policy, and review invariants

## Quick start

```bash
python -m pip install -e .
mskill init "Microstructure conductivity optimization"
mskill status
```

When the architecture is ready for attack:

```bash
mskill advance --note "Problem interpretation and validation plan are frozen"
mskill prompt
```

Record structured architecture-review findings:

```bash
mskill finding add blocker "Boundary semantics are ambiguous"
mskill finding add major "Sensitivity analysis is underspecified"
mskill finding list
```

An unresolved Blocker prevents a workflow gate PASS:

```bash
mskill gate pass
# mskill: cannot pass gate with unresolved Blocker findings: #1
```

Resolve the Blocker explicitly, then pass the gate:

```bash
mskill finding resolve 1 --note "Two interpretations documented and tested"
mskill gate pass --note "Architecture accepted after blocker resolution"
```

After the full modeling work is complete:

```bash
mskill advance --note "Execution package ready for independent audit"
mskill finding add minor "Clarify one limitation in the handoff"
mskill gate pass --note "No unresolved blockers"
mskill status
```

Use `mskill finding list --all` to inspect both open and resolved review findings.

## State machine

```text
architecture
    │ advance
    ▼
architecture_red_team ── fail ──► architecture
    │ pass*                         │
    ▼                               └─ resolve findings / revise
execution
    │ advance
    ▼
final_red_team ─────── fail ─────► execution
    │ pass*
    ▼
complete

* Workflow gate PASS is rejected while any Blocker finding remains open.
```

The CLI deliberately has no command that jumps directly from architecture to execution or from execution to complete.

## Commands

| Command | Purpose |
|---|---|
| `mskill init NAME` | Initialize `.mskill/state.json` |
| `mskill status` | Show state, finding counts, and active policy summary |
| `mskill policy` | Show the effective policy and its source |
| `mskill advance` | Submit architecture/execution to the next red-team gate |
| `mskill gate pass\|fail` | Record a red-team verdict |
| `mskill finding add SEVERITY MESSAGE` | Add a Blocker/Major/Minor review finding |
| `mskill finding list [--all]` | List open findings, or all findings |
| `mskill finding resolve ID` | Resolve a tracked finding |
| `mskill check [--format text\|github]` | Evaluate state using the active CI policy |
| `mskill check --require-complete` | Force completion for this invocation even if policy does not |
| `mskill prompt` | Print a stage-specific agent prompt |
| `mskill validate` | Validate stored workflow state |

Use `--root PATH` to operate on another project directory.

## Finding model

Each finding is stored in workflow state with:

- sequential ID
- severity: `blocker`, `major`, or `minor`
- review stage where it was discovered
- message
- status: `open` or `resolved`
- creation and resolution timestamps
- optional resolution note

Findings may only be created during `architecture_red_team` or `final_red_team`. They may be resolved after the workflow returns to architecture/execution for rework. This creates an explicit defect trail instead of losing review objections inside free-text notes.

## Configurable policy (`mskill.toml`)

Without `mskill.toml`, M-Skill preserves its original CI defaults:

- fail `mskill check` on open Blockers
- allow open Major/Minor findings while still surfacing them
- do not require the workflow to be `complete`

Create `mskill.toml` in the project root to change the CI threshold:

```toml
[policy]
fail_on = ["blocker", "major"]
require_complete = true
```

`fail_on` accepts `blocker`, `major`, and `minor`. Duplicates are normalized in deterministic severity order. An empty array is allowed if a repository wants findings to remain informational for CI:

```toml
[policy]
fail_on = []
require_complete = false
```

Inspect the effective configuration with:

```bash
mskill policy
```

Example output:

```text
source: mskill.toml
fail_on: blocker,major
require_complete: true
```

Unknown keys, invalid severities, invalid types, and malformed TOML are controlled configuration errors (exit `2`) and never produce a traceback. See [`examples/mskill.toml`](examples/mskill.toml) for a copyable strict policy.

`mskill.toml` configures **`mskill check` / CI policy**. It does not weaken the core red-team state-machine invariant: `mskill gate pass` still refuses an unresolved Blocker.

## GitHub Actions / PR checks

`mskill check` converts the persisted workflow state and active policy into deterministic CI behavior:

- exit `0`: state/config are valid and policy passes
- exit `1`: the check was evaluated but policy failed
- exit `2`: workflow state or policy configuration could not be loaded safely

Normal text output is useful locally:

```bash
mskill check
```

GitHub mode emits native workflow annotations. Annotation severity is stable even when pass/fail policy changes:

- Blocker → `::error`
- Major → `::warning`
- Minor → `::notice`

```bash
mskill check --format github
```

If a repository needs a one-off stricter invocation, `--require-complete` is additive: CLI `true` OR configured `require_complete = true` requires the `complete` stage.

Finding text and annotation properties are escaped before being emitted as GitHub workflow commands.

To use M-Skill as a pull-request gate in another repository, commit that project's `.mskill/state.json` and optional `mskill.toml`, then copy [`examples/github-actions/mskill-check.yml`](examples/github-actions/mskill-check.yml) into `.github/workflows/mskill-check.yml`.

Once the workflow check is required in GitHub branch protection, a PR cannot merge while the configured M-Skill gate is failing.

## Design principles

1. **Interpretation before computation.** A numerically correct answer to the wrong problem is still wrong.
2. **Red team is a gate, not decoration.** A FAIL changes the workflow state and forces revision.
3. **Blockers are enforceable defects.** A workflow gate PASS cannot override an unresolved Blocker.
4. **Policy is explicit.** Repository-specific CI strictness belongs in versioned configuration, not hidden conventions.
5. **Traceability over persuasion.** Facts, assumptions, calculations, findings, and conclusions should remain distinguishable.
6. **The orchestrator prevents drift.** It should coordinate execution, preserve scope, and integrate evidence.
7. **Completion requires adversarial review.** Final review should challenge critical claims, not merely proofread them.

## Development

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

## Roadmap

- [x] Configurable workflow policies (`mskill.toml`)
- [x] Machine-readable red-team findings (Blocker/Major/Minor)
- [ ] Artifact manifest and reproducibility checks
- [x] GitHub PR/check integration
- [ ] Optional multi-agent adapters for Codex and other agent runtimes

## License

MIT
