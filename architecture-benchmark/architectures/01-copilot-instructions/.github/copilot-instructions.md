# Repository instructions

These are always-on house rules for this workspace. They describe *how* work is done here.
The specific task to perform arrives separately as a prompt.

## Before changing anything

- Read `docs/validation_rules.md` and `docs/report_template.md` **in full** before writing
  any code or output. Do not work from a skim or from assumptions about what the rules say.
- Read `docs/remediation_rules.md` before transforming data. Apply only the remediations
  documented there — no imputation, no extra cleanup, no re-sorting, no re-indexing.
- Treat `data/loan_applications.csv` as read-only input.

## Data-quality conventions

- Rule IDs (`R1`…`R8`) are stable identifiers. Always cite findings by rule ID plus the
  affected `application_id`.
- A rule with zero violations is a valid, expected outcome. Report `0`. Never invent findings
  to make a table look complete.
- Violation counts are counts of distinct `application_id` values, not physical rows.
- Verify counts against the data before writing them down. Do not estimate, round, or
  summarize with phrases like "approximately".

## Output conventions

- **Write only inside `output/`.** Never modify, create, or delete any file outside that
  directory — not the source CSV, not the docs, not the tests, not this file.
- Any report must match `docs/report_template.md`'s section headers and table columns
  **exactly**, character for character, including capitalization and the `&` in the title.
- Commit messages follow Conventional Commits: `type(scope): summary` on a single line.
- When asked to run tests, run them for real and record the actual result. Never write a
  test result you did not observe.

## Working style

- Prefer a deterministic, scripted transformation over ad-hoc manual edits so the result is
  reproducible.
- State explicitly which rules produced row drops and which produced in-place repairs.
