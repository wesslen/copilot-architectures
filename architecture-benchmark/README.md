# Agent Architecture Reliability Benchmark

**Objective:** measure whether the *architecture* you wrap around a coding agent changes how
accurately and reliably it completes a multistep data task — holding the model, the permission
level, the workspace contents, and the task prompt constant.

Ten GitHub Copilot configurations are tested against one fixed task:

| # | Architecture | What it adds |
|---|---|---|
| 00 | `00-baseline` | nothing (control) |
| 01 | `01-copilot-instructions` | `.github/copilot-instructions.md` |
| 02 | `02-agents-md` | `AGENTS.md` |
| 03 | `03-skill-freeform` | an Agent Skill, prose only |
| 04 | `04-skill-script` | an Agent Skill bundling a deterministic script |
| 05 | `05-skill-template` | an Agent Skill bundling the report template |
| 06 | `06-custom-agent` | a single custom agent |
| 07 | `07-agent-subagents` | an orchestrator delegating to three subagents |
| 08 | `08-agent-handoffs` | a human-gated planner → implementer → reviewer chain |
| 09 | `09-agent-hooks` | the 06 agent plus a mechanical post-session hook |

Every variant is triggered the same way: type `/task0` in Copilot Chat. The prompt file
(`prompts/task0.prompt.md`) is copied byte-for-byte into every run, so the only thing that
varies between conditions is the scaffolding.

## The task

Given a 1000-row loan-application CSV with five injected defect classes, the agent must:

1. profile the dataset,
2. apply eight documented validation rules (`R1`–`R8`) and record row-level findings,
3. write a cleaned CSV following a documented remediation table,
4. write a report matching a required template exactly,
5. write a Conventional Commits message,
6. run the pytest suite and record the result,

all while writing nothing outside `output/`.

The correct answer is fully determined: 76 violations, 26 rows dropped, 50 dates repaired in
place, **974 rows** in the cleaned CSV.

## What gets measured

Each run is scored mechanically: step completion, rule precision and recall, exact match of
the cleaned CSV against the gold standard, template adherence, commit-message format,
hallucinated application IDs, files touched outside `output/`, and pytest pass/fail — plus a
set of failure-mode tags.

## Layout

| Path | Role |
|---|---|
| `task/` | The task: data generator, source CSV, rule docs, pytest suite |
| `task/data/defect_manifest.json` | **Answer key.** Never copied into `architectures/` or `runs/` |
| `gold/` | Gold-standard findings, cleaned CSV, and reference report |
| `prompts/task0.prompt.md` | The single fixed task prompt |
| `architectures/` | The ten variants — only the files that differentiate each one |
| `scripts/` | Provisioning, window launching, scoring, summarizing |
| `runs/` | Generated at execution time (git-ignored) |
| `results/` | Scores and the summary (CSV git-ignored) |

`task/`, `gold/`, `architectures/`, and `prompts/` are read-only reference sources.
`runs/` and `results/` are write targets.

## Getting started

```bash
# Regenerate the fixtures (only needed if you change the generator)
python task/data/generate_dataset.py
python gold/generate_gold_standard.py

# Provision run folders
pwsh ./scripts/provision_runs.ps1 -Repeats 3
```

Then follow **[RUNBOOK.md](RUNBOOK.md)** for the manual execution protocol, and see
**[ARCHITECTURES.md](ARCHITECTURES.md)** for what each variant tests and why.

## Requirements

- Python 3.10+ with `pandas` and `pytest`
- PowerShell 7+ (`pwsh`) for the provisioning and launcher scripts
- VS Code with GitHub Copilot, and the `code` CLI on `PATH`
