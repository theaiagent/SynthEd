## Summary
<!-- What does this PR do? 1-3 bullet points -->

-
-

## Related Issue
<!-- Link to the issue this addresses: Fixes #123 -->

## Changes
<!-- List the key changes made -->

-
-

## Test Plan
<!-- How was this tested? -->

- [ ] All existing tests pass (`python -m pytest tests/ -q`)
- [ ] Lint passes (`ruff check synthed/ tests/ --select E,F,W --ignore E501`)
- [ ] New tests added for new functionality
- [ ] Multi-seed comparisons completed and reported (if simulation changes)
- [ ] Documentation consistency passes (`python -m synthed.doc_facts`)

## Checklist
- [ ] Code follows [CONTRIBUTING.md](../CONTRIBUTING.md) standards
- [ ] No hardcoded secrets or API keys
- [ ] Documentation updated (if applicable)
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] Independent Python and security reviews completed
- [ ] Statistical consistency review completed (if calibration/validation parameters change)
- [ ] CodeRabbit feedback reviewed and maintainer merge approval obtained
- [ ] Commit messages follow `type: description` convention
