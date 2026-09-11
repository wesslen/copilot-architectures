Using data/loan_applications.csv, docs/validation_rules.md, docs/remediation_rules.md, 
and docs/report_template.md in this workspace:
1. Profile the dataset for data-quality issues.
2. Apply all 8 rules in validation_rules.md exactly and record row-level findings 
   (rule ID and affected application_id for every violation).
3. Produce a cleaned CSV at output/cleaned_loan_applications.csv following 
   remediation_rules.md only — do not apply remediation not documented there.
4. Write output/report.md matching report_template.md's exact section headers and 
   table structure.
5. Write output/commit_message.txt as a single line in the format `type(scope): summary`.
6. Run `pytest tests/test_validation.py` and write output/test_result.txt with the result.
Do not modify any file outside the output/ directory.
