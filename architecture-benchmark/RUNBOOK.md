# Runbook

The manual protocol for executing the benchmark. Follow it exactly — every deviation is a
confound, because the whole experiment rests on the architecture being the *only* thing that
differs between runs.

---

## 0. Before you start — fix your variables

Decide these once and do not change them mid-experiment. Write them down.

| Variable | Choose | Notes |
|---|---|---|
| **Model** | one model, e.g. `GPT-5` | Must be identical for every run. |
| **Agent permission level** | `Default` / `Bypass Approvals` / `Autopilot` | Must be identical for every run. `Default` will prompt for approvals; expect longer runs and more human involvement. |
| **Repeats** | ≥ 3 per architecture | Single runs cannot separate a real effect from run-to-run variance. 5+ if you plan to report standard deviations. |
| **VS Code + Copilot version** | pinned | Note it in `run_meta.json`'s `notes` field. |

Two setup steps follow from the model choice:

1. The agent files under `architectures/**/*.agent.md` carry a `model:` field in their
   frontmatter. **Set every one of them to the model you fixed above** before provisioning, or
   variants 06–09 will silently run on a different model than 00–05:

   ```bash
   grep -rn '^model:' architectures/
   ```

2. Confirm the fixtures exist and are current:

   ```bash
   python task/data/generate_dataset.py     # -> task/data/loan_applications.csv (1000 rows)
   python gold/generate_gold_standard.py    # -> gold/gold_cleaned.csv (974 rows)
   ```

   Both scripts are deterministic (`seed=42`). Re-running them is safe and reproduces identical
   files. If you change the generator you **must** re-run both, in that order.

### Ground rules for the whole session

- **Never** open `task/data/defect_manifest.json`, `gold/gold_findings.csv`,
  `gold/gold_cleaned.csv`, or `gold/gold_report.md` in a run window. They are the answer key.
- Send `/task0` and nothing else. No follow-ups, no clarifications, no "you missed a step",
  no accepting a suggestion the agent did not ask for.
- If the agent asks a question, answer with the minimum that unblocks it and record what you
  said in that run's `run_meta.json` `notes` field. A run you had to coach is still data — it
  just needs to be labelled.
- If a run fails outright (crash, timeout, agent refuses), keep the folder, note the reason, and
  provision a replacement repeat rather than retrying in the same window.

---

## 1. Provision the run folders

```bash
pwsh ./scripts/provision_runs.ps1 -Repeats 3
```

Or a subset:

```bash
pwsh ./scripts/provision_runs.ps1 -Architectures 00-baseline,06-custom-agent,09-agent-hooks -Repeats 5
```

Each `runs/<architecture>-run<NN>/` gets the source CSV (never the defect manifest), the docs,
the tests, `.github/prompts/task0.prompt.md`, that architecture's own files, an empty `output/`,
and a `run_meta.json`. The script refuses to overwrite an existing run folder unless you pass
`-Force`, and it hard-fails if the answer key ever reaches a run folder.

**Then fill in provenance.** For every `runs/*/run_meta.json`, set `model` and
`permission_level` to the values you fixed in step 0. These fields are intentionally blank —
they are your record of what the run actually used, not what you intended.

---

## 2. Open a batch of run windows

```bash
pwsh ./scripts/open_run_windows.ps1 -BatchSize 4
```

Small batches. Four windows is a reasonable ceiling for one person — more than that and you
will lose track of which window finished, which is how transcripts end up in the wrong folder.
The script opens the next runs that have no `output/chat_session.json` yet, so re-running it
picks up where you left off.

---

## 3. Per window

1. Confirm the window's title bar shows the expected run folder.
2. Open Copilot Chat and **type `/task0`**. Send it unmodified.
   - For **08-agent-handoffs**, you will be prompted to approve each handoff
     (planner → implementer → reviewer). Click through them promptly. Do not add instructions
     at the gate — clicking is the only intervention allowed.
   - For **07-agent-subagents**, let the orchestrator delegate. Do not redirect it.
3. Wait for the agent to finish. Do not intervene.
4. Export the transcript: Command Palette → **`Chat: Export Session...`** → save into that
   run's folder as `output/chat_session.json`. This is what lets the scorer cross-check whether
   pytest was really run.
5. Close the window.
6. Repeat for the rest of the batch, then go back to step 2 for the next batch.

---

## 4. Score every run

Once **all** runs are complete:

```bash
for run in runs/*/; do python scripts/score_run.py "$run" gold; done
```

PowerShell equivalent:

```powershell
Get-ChildItem ./runs -Directory | ForEach-Object { python ./scripts/score_run.py $_.FullName ./gold }
```

Each call appends one row to `results/results.csv`. Re-scoring a run replaces its row rather
than duplicating it, so it is safe to re-run after fixing a mis-filed transcript.

---

## 5. Summarize and read

```bash
python scripts/summarize_results.py
```

Then read **`results/results_summary.md`**: a leaderboard across architectures, followed by one
table per architecture with pass rate, precision and recall (mean ± sd), exact-match rate, and
the most common failure-mode tags.

### Reading it honestly

- **Pass rate** is strict: exact CSV match **and** full template adherence **and** pytest green
  **and** zero scope creep. Most runs will fail on one axis. That is the point — look at
  *which* axis.
- The **failure-mode tags** carry more signal than the aggregate scores. `fabricated_control_findings`,
  `truncated_id_list`, and `hallucinated_ids` are qualitatively different problems and call for
  different fixes.
- Compare **neighbouring** variants, not the whole table at once: 03 vs 04 vs 05 isolates what
  bundling a script or a template buys; 06 vs 09 isolates the hook; 06 vs 07 vs 08 isolates
  delegation from gated sequencing.
- With 3 repeats, a difference of one run is noise. Do not rank architectures on it.

---

## 6. Preserve the evidence

`runs/` and `results/results.csv` are git-ignored — they are the experiment's output, not its
source. If you want to keep a completed campaign, archive the `runs/` tree and `results/`
together with the commit SHA of the repository state you ran against. Without the SHA the
numbers are not reproducible.
