# Architectures Under Test

Ten conditions, one task, one prompt. Each section states what the variant adds, what it is
testing, and the hypothesis for how it should perform relative to its neighbours.

Read the hypotheses as pre-registration, not as findings. They exist so that a surprising
result is recognizable as a surprise.

---

## 00-baseline

**Adds:** nothing. The run folder contains the data, the docs, the tests, and
`.github/prompts/task0.prompt.md` — no instructions file, no agent, no skill.

**Tests:** how much of the task the model completes from the prompt alone, with the rule and
template documents merely *present* in the workspace rather than pointed at.

**Hypothesis:** the weakest condition, and the one that reveals what the other nine are
actually paying for. Expect the prompt's six numbered steps to be followed roughly, but with
the highest variance: the failure modes should cluster around *not reading the docs in full* —
paraphrased section headers, truncated ID lists ("APP-000003, APP-000005, … and 18 more"), and
control rules `R6`–`R8` either omitted from the table or filled with invented findings because
a zero row looks like an oversight. Recall on `R4` (50 non-ISO dates) is the most likely
casualty, since spotting it requires actually inspecting the date column rather than assuming
a single format.

---

## 01-copilot-instructions

**Adds:** `.github/copilot-instructions.md` — always-on repository house rules. General
guidance ("read the rule docs in full before changing anything", "match the template headers
exactly", "only write inside `output/`"), deliberately *not* the six steps, which come from the
prompt.

**Tests:** whether persistent, always-loaded context improves compliance without restating the
procedure.

**Hypothesis:** a clear improvement over baseline on the *constraint* metrics — scope creep and
template adherence — because those are exactly what the file asserts, and it is in context for
every turn. Little or no improvement on rule recall, since the file never tells the agent what
`R4` is. This is the cheapest intervention in the set, so it establishes the floor for
"instructions help at all".

---

## 02-agents-md

**Adds:** `AGENTS.md` containing the same six steps as the prompt, phrased as a linear
operational runbook with an explicit invariants section.

**Tests:** redundancy. The steps now appear twice — once in the prompt, once in an always-on
file — in two different registers.

**Hypothesis:** better than 01 on rule recall, because the runbook enumerates the remediation
actions per rule where 01 only gestures at the docs. The interesting risk is *conflict*: two
phrasings of the same procedure can be read as two procedures, and the agent may do the
profiling step twice or, worse, treat the runbook's summary of the remediation table as
authoritative and skip `docs/remediation_rules.md`. Expect strong step completion, with any
degradation showing up as subtle rule drift rather than missing outputs.

---

## 03-skill-freeform

**Adds:** `.github/skills/data-quality-report/SKILL.md` — YAML frontmatter plus a prose body
repeating the six steps, loaded on demand when the description matches the request.

**Tests:** whether *scoped* instructions beat *always-on* instructions. Unlike 02, the content
only enters context when the task matches.

**Hypothesis:** roughly equal to 02 on accuracy, with the real difference being that the skill
has to fire at all. The primary risk is a triggering miss — if the description does not match
the prompt's wording, this variant silently degrades to baseline, which would show up as
bimodal results rather than a lower mean. When it does fire, the explicit "zero violations is
the correct answer for R6–R8" line should largely eliminate fabricated control findings, which
is the cleanest single-metric prediction in the set.

---

## 04-skill-script

**Adds:** the same skill folder plus `scripts/validate_and_clean.py`, a deterministic
implementation of `R1`–`R8` and the full remediation table. `SKILL.md` instructs the agent to
run it and transcribe the output.

**Tests:** moving the rule logic out of the model entirely. The agent's remaining job is
orchestration and formatting.

**Hypothesis:** the strongest variant on every accuracy metric, and by a wide margin — rule
precision and recall should be 1.0 whenever the script is actually run, and the cleaned CSV
should match the gold standard byte-for-byte, because the script and the gold generator agree
by construction. The residual failure mode is transcription: an agent that re-counts by hand,
truncates the 50-ID `R4` list when copying it into the table, or "sanity checks" the script's
zero for `R6` and edits it. If 04 does not win outright, the reason will be interesting — it
means formatting and transcription, not rule logic, is where these tasks actually break.

---

## 05-skill-template

**Adds:** the same skill folder, but bundling `templates/report_template.md` instead of a
script.

**Tests:** proximity of a required artifact. The template ships *with* the skill, so it loads
with it, rather than sitting in `docs/` waiting to be found and read.

**Hypothesis:** near-perfect template adherence — the highest of any variant on that metric
alone — with accuracy comparable to 03, since nothing about the rule logic changed. The
comparison that matters is 05 vs 03: if template adherence jumps while precision and recall
stay flat, that isolates "the agent never opened the template" from "the agent could not follow
the template", which are very different problems with very different fixes. Compared to 04 it
should lose on accuracy, showing that bundling a *reference* is weaker than bundling an
*implementation*.

---

## 06-custom-agent

**Adds:** `.github/agents/data-quality.agent.md` — a named agent with frontmatter (`name`,
`description`, `tools`, `model`) and a persona body containing the six steps. Single agent, no
delegation.

**Tests:** whether a dedicated persona with a constrained tool list outperforms the same
instructions delivered as a skill or an instructions file.

**Hypothesis:** comparable to 02 and 03 on accuracy — the content is nearly identical, so a
large gap here would be evidence that *framing* matters independently of content. The tool
restriction should help on scope creep. This is the honest control for the three agentic
variants that follow: 07, 08, and 09 all have to beat 06 to justify their extra machinery, and
the null result — that they do not — is a real and useful outcome.

---

## 07-agent-subagents

**Adds:** four agents — `orchestrator` delegating to `profiler` (read-only, finds violations),
`cleaner` (writes the CSV), and `reporter` (writes report and commit message), with
independent subtasks run in parallel.

**Tests:** decomposition. Each subagent sees a narrower slice of the problem, and the profiler
is tool-restricted so it cannot accidentally write data.

**Hypothesis:** two forces pull in opposite directions. Specialization should raise precision —
a read-only profiler that does nothing but evaluate eight rules has no competing objective, and
forcing findings through `output/findings.json` gives the cleaner and reporter a single shared
source of numbers. Against that, every delegation boundary is a chance to lose information: the
classic failure is the reporter summarizing the profiler's 50 `R4` IDs instead of transcribing
them, or the orchestrator paraphrasing the findings into a subagent prompt rather than passing
the file. Expect higher precision than 06 but a wider spread, with `truncated_id_list` and
`count_id_mismatch` as the signature failures. Parallelism adds throughput but also a race: the
reporter may write the final row count before the cleaner has produced it.

---

## 08-agent-handoffs

**Adds:** a three-stage chain — `planner` (read-only, writes a violation plan) → `implementer`
(writes the outputs) → `reviewer` (verifies against the rules and template). Each handoff has
`send: false`, so a human clicks to advance.

**Tests:** human-gated sequencing, and an explicit verification stage, versus 07's more
autonomous delegation.

**Hypothesis:** the highest accuracy of the three agentic variants and the highest wall-clock
cost. Two mechanisms should help: writing the plan to a file before any data is touched
separates *deciding* from *doing*, and the reviewer is the only agent in the whole benchmark
whose job is to catch a hallucinated `application_id`. The gates also mean a visibly wrong plan
never reaches the implementer. The cost is that the reviewer only *reports* — it cannot fix —
so unless the protocol loops back, its findings land in `output/review.md` and the scored
artifacts stay wrong. Watch for the plan itself truncating ID lists: the implementer cannot
recover information the planner did not write down, so an error here is unrecoverable in a way
07's is not.

---

## 09-agent-hooks

**Adds:** the same persona as 06, plus `.github/hooks/validate_output.py` referenced from the
agent's frontmatter as a post-session hook. It checks that `output/report.md` contains all four
required headers and that the cleaned CSV has no duplicate `application_id`, and fails the
session otherwise.

**Tests:** mechanical enforcement versus trusted compliance. 09 minus 06 is precisely the value
of the hook.

**Hypothesis:** template adherence and `duplicates_remain` should go to zero, because those two
properties are checked by a program rather than promised by a model — this is the sharpest
prediction in the benchmark and the easiest to falsify. Everything the hook does not check
should be unchanged from 06: rule recall, the `R4` date normalization, control-rule
fabrication, and scope creep. If 09's *overall* pass rate rises much more than the hook's
narrow checks can explain, the likely cause is the agent running the hook itself before
finishing and self-correcting — which would be the most practically useful finding here, since
it suggests a cheap checker is worth more as a tool the agent can call than as a gate it cannot
see.
