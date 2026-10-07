# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest published release | Report vulnerabilities here |
| Older releases | Upgrade to the latest release before reproducing an issue |

See the [latest release](https://github.com/theaiagent/SynthEd/releases/latest) for the current version. The `main` branch may contain unreleased fixes. This project does not publish a separate long-term-support schedule.

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

SynthEd's default generator produces **fictional synthetic personas**. The project also includes:

- A CLI and Python library that read configurations and write output files
- An optional Shiny web dashboard, bound to `127.0.0.1` by default, without built-in authentication
- Optional LLM calls to a configured provider, using persona attributes in prompts
- OULAD/institutional data readers used by standalone calibration and validation utilities

Keep the dashboard on a trusted local interface unless authentication and access controls are provided externally. Custom data and LLM outputs require their own handling policy; fictional persona generation is not a guarantee about arbitrary inputs or model-generated text.

Security concerns most relevant to SynthEd:
- **Dependencies and source code** -- dependency update PRs from Dependabot; Python source analysis with CodeQL
- **LLM API key exposure** -- keys are read from environment variables, never hardcoded
- **Tempfile cleanup** -- simulation runners clean up temporary directories in `finally` blocks
- **Input validation** -- supported numeric ranges and probability distributions are checked; dashboard imports and output paths have additional limits

## Security Measures in Place

- **CodeQL**: Automated analysis on pushes and pull requests to `main`, plus the configured schedule
- **Dependabot**: Automatic dependency update PRs
- **Merge checks**: Required checks are configured in GitHub branch protection; see [CONTRIBUTING.md](../CONTRIBUTING.md) for the review process
- **Secrets**: LLM credentials are supplied through configuration/environment variables; use HTTPS for remote providers
- **Dashboard limits**: JSON imports are capped at 512 KiB and population at 10,000. User-specified output paths must remain within the working directory. An empty output field uses an operating-system temporary directory, which may be outside that directory and is not automatically removed by the dashboard
- **Validation limits**: These checks reduce specific risks; passing CI or the synthetic-data validator is not proof that every input or deployment is secure
