## Summary

[Provide a brief description of the changes in this pull request. Keep to 1-3 sentences explaining the main purpose.]

## Type of Change

Select all that apply:

- [ ] Bug fix (addresses a reported issue; does not break existing tests)
- [ ] New feature (new functionality; backward compatible)
- [ ] Breaking change (API modification; requires version bump and deprecation notice)
- [ ] Documentation update (README, GUIDE.md, THEORY.md, docstrings)
- [ ] Test addition or modification (new test coverage or bug reproduction tests)
- [ ] Refactoring (code improvement without behavior change)
- [ ] Performance optimization

## Related Issues

If this PR closes or relates to any existing GitHub issues, link them here:

- Closes #[issue_number]
- Relates to #[issue_number]

(Leave blank if this is a standalone PR)

## Description of Changes

Provide a detailed description of what was changed and why. List key modifications:

- Change 1: [description]
- Change 2: [description]
- Change 3: [description]

## Testing

Verification that the implementation works as intended.

### Local Testing
- [ ] All tests pass locally: `pytest tests/ -v`
- [ ] Code coverage maintained or improved
- [ ] Tested with Python 3.10, 3.11, 3.12

### Test Coverage
- [ ] Added new unit tests for this change
- [ ] Added integration tests if applicable
- [ ] Updated existing tests that are affected

### Reproduction (for bug fixes only)
- [ ] Provided test case that reproduces the issue
- [ ] Verified fix resolves the issue

## Documentation

Documentation updates are required for user-facing changes.

- [ ] Updated GUIDE.md if feature or API changed
- [ ] Updated THEORY.md if theoretical model changed
- [ ] Updated README.md if this affects overview or quick start
- [ ] Added or updated docstrings for new functions
- [ ] Added type hints to function signatures
- [ ] Documented any new configuration parameters

## Code Quality

Adherence to project standards is required before approval.

- [ ] Code passes ruff style check: `ruff check synthed/ tests/ --select E,F,W`
- [ ] No new linting warnings introduced
- [ ] No hardcoded secrets, API keys, or credentials
- [ ] Commit messages are clear and descriptive
- [ ] Commits are logically organized (not squashed into one if multiple changes)

## Breaking Changes

If this PR introduces breaking changes, describe impact and migration path:

- [ ] No breaking changes (uncheck if there are any)

If breaking changes exist, document:

1. What changed?
2. How should users migrate their code?
3. Deprecation period (if applicable)?
4. Version bump required (major, minor, patch)?

## Additional Notes

Include any additional context, caveats, or information for reviewers:

- Known limitations or edge cases handled
- Dependencies added or updated (list them)
- Files affected summary
- Performance implications
- Related discussions or decisions

## Reviewer Checklist

Reviewers must verify before approval:

- [ ] Changes align with project scope and architecture
- [ ] All tests pass on CI
- [ ] Code quality standards met
- [ ] Documentation is accurate and complete
- [ ] No security vulnerabilities introduced
- [ ] Backward compatibility maintained (or breaking change documented)
- [ ] Theory module changes validated against simulation behavior
- [ ] Calibration or experimental changes documented with reasoning

## Sign Off

By submitting this PR, I confirm that:

- I have read and understood the CONTRIBUTING guidelines
- My changes follow the project's code style and architecture
- I have tested my changes
- I have updated documentation as needed
- I have not introduced any security vulnerabilities
- I have not committed any secrets or credentials
