# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.6.x   | Yes       |
| < 0.6   | No        |

## Reporting a Vulnerability

If you discover a security vulnerability in SynthEd, please report it responsibly:

1. **Do NOT open a public issue**
2. Email: **h.aykut.cosgun@gmail.com** with subject line `[SynthEd Security]`
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

You will receive a response within 72 hours.

## Scope

SynthEd is a research tool that generates **fictional synthetic data**. It does not:
- Handle real student data
- Provide authentication or access control
- Run as a web service (CLI and library only)

Security concerns most relevant to SynthEd:
- **Dependency vulnerabilities** -- monitored by Dependabot and CodeQL
- **LLM API key exposure** -- keys are read from environment variables, never hardcoded
- **Tempfile cleanup** -- simulation runners clean up temporary directories in `finally` blocks
- **Input validation** -- all `PersonaConfig` inputs are validated at construction time

## Security Measures in Place

- **CodeQL**: Automated security scanning on every push and PR
- **Dependabot**: Automatic dependency update PRs
- **Branch protection**: 4 required CI checks before merge
- **No hardcoded secrets**: Verified by grep + CodeQL
- **Input validation**: `validate_range()` and `validate_probability_distribution()` on all config inputs
