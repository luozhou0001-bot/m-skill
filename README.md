# M-Skill

**Red-team-gated workflow control for rigorous AI-assisted mathematical modeling.**

M-Skill is a tiny, dependency-free Python CLI that turns a modeling task into a process that an AI agent cannot casually skip:

`Architecture → Architecture Red Team → Execution → Final Red Team → Complete`

A failed review automatically sends the work back for revision. The state is persisted in `.mskill/state.json`, so the workflow is auditable and resumable across sessions and agents.

## Why this exists

AI-assisted modeling often fails because the model starts calculating before the problem is understood, silently changes data semantics, or treats its own result as validation. M-Skill makes the review gates explicit and machine-checkable.

It is designed for mathematical modeling competitions, research prototypes, simulation/optimization tasks, and any Codex/agent workflow where **problem interpretation is part of correctness**.

## Features

- Zero runtime dependencies; Python 3.10+
- Persistent workflow state and revision counters
- Architecture red-team gate before full execution
- Final adversarial audit before completion
- Stage-specific prompts for Codex/agent orchestration
- Explicit PASS/FAIL decisions with audit notes
- CI-tested transition rules

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

Record the architecture red-team verdict:

```bash
mskill gate fail --note "Boundary semantics are ambiguous; provide two interpretations"
# revise the architecture, then submit again
mskill advance
mskill gate pass --note "Ambiguity resolved and sensitivity plan added"
```

After the full modeling work is complete:

```bash
mskill advance --note "Execution package ready for independent audit"
mskill gate pass --note "No unresolved blockers"
mskill status
```

## State machine

```text
architecture
    │ advance
    ▼
architecture_red_team ── fail ──► architecture
    │ pass
    ▼
execution
    │ advance
    ▼
final_red_team ─────── fail ─────► execution
    │ pass
    ▼
complete
```

The CLI deliberately has no command that jumps directly from architecture to execution or from execution to complete.

## Commands

| Command | Purpose |
|---|---|
| `mskill init NAME` | Initialize `.mskill/state.json` |
| `mskill status` | Show stage and revision counters |
| `mskill advance` | Submit architecture/execution to the next red-team gate |
| `mskill gate pass\|fail` | Record a red-team verdict |
| `mskill prompt` | Print a stage-specific agent prompt |
| `mskill validate` | Validate stored workflow state |

Use `--root PATH` to operate on another project directory.

## Design principles

1. **Interpretation before computation.** A numerically correct answer to the wrong problem is still wrong.
2. **Red team is a gate, not decoration.** A FAIL changes the workflow state and forces revision.
3. **Traceability over persuasion.** Facts, assumptions, calculations, and conclusions should remain distinguishable.
4. **The orchestrator prevents drift.** It should coordinate execution, preserve scope, and integrate evidence.
5. **Completion requires adversarial review.** Final review should challenge critical claims, not merely proofread them.

## Development

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

## Roadmap

- [ ] Configurable workflow policies (`mskill.toml`)
- [ ] Machine-readable red-team findings (Blocker/Major/Minor)
- [ ] Artifact manifest and reproducibility checks
- [ ] GitHub PR/check integration
- [ ] Optional multi-agent adapters for Codex and other agent runtimes

## License

MIT
