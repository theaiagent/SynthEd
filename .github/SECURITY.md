# Security Policy for SynthEd

## Reporting Security Vulnerabilities

SynthEd prioritizes security and user privacy. If you discover a security vulnerability, please report it responsibly by emailing h.aykut.cosgun@gmail.com instead of opening a public GitHub issue.

### Reporting Requirements

When reporting a security vulnerability, include the following information:

1. Title and description of the vulnerability
2. Steps to reproduce the issue
3. Potential impact and severity assessment
4. Suggested fix or remediation (if available)
5. Your contact information

### Response Timeline

The SynthEd team commits to the following response timeline for security reports:

- Acknowledgment: Within 48 hours of initial report
- Assessment: Within 5 business days
- Fix or mitigation plan: Within 10 business days
- Public disclosure: Coordinated timing (typically 90 days after fix availability)

### Scope of Vulnerability Reports

Report all vulnerabilities related to:

- LLM API key handling and exposure prevention
- Calibration data protection against reverse engineering
- Synthetic data output privacy guarantees
- Input validation and sanitization
- Dependency vulnerabilities
- Access control in multi-user deployments

### Out of Scope

The following are generally out of scope for security reports:

- Vulnerabilities in third-party dependencies (report directly to maintainers)
- Documentation improvements or typos
- UI/UX issues
- Performance concerns
- Theoretical modelling accuracies not related to security

## Security Considerations for End Users

### LLM API Integration

If using LLM enrichment features:

1. Never hardcode API keys in configuration files
2. Use environment variables exclusively: OPENAI_API_KEY
3. For local providers (Ollama), ensure base-url points to localhost only
4. LLM cost estimates are provided; review before confirming execution
5. Cached responses are stored locally with 7-day TTL; clear cache if needed

### Synthetic Data Privacy

SynthEd generates entirely fictional synthetic data derived from statistical patterns. However, users should:

1. Verify synthetic data does not reproduce patterns that could re-identify individuals
2. Apply k-anonymity validation tests before publishing datasets
3. Understand that calibration parameters are derived from OULAD (published research data)
4. Document data generation parameters and seeds for reproducibility

### Credential Management

Avoid committing any of the following to version control:

- API keys or tokens
- Database credentials
- Personal access tokens
- SSH keys
- OAuth secrets
- Custom calibration data containing real student identifiers

Use .env files or environment variables exclusively:

```
# .env (add to .gitignore)
OPENAI_API_KEY=sk-...
OLLAMA_BASE_URL=http://localhost:11434/v1
```

## Dependency Security

SynthEd uses the following key dependencies:

- numpy >= 1.24.0 (numerical computing)
- scipy >= 1.10.0 (scientific computing)
- openai >= 1.0.0 (LLM integration, optional)
- SALib >= 1.4.0 (sensitivity analysis)
- optuna >= 3.0.0 (hyperparameter optimization)

Dependency security is managed through:

- GitHub Dependabot for automated vulnerability scanning
- Regular manual audits of critical dependencies
- Documented minimum versions to avoid EOL packages
- Automated CI/CD tests on Python 3.10, 3.11, 3.12

## Supported Versions

Security updates are provided for:

| Version | Status | Notes |
| --- | --- | --- |
| 0.x (current) | Actively Supported | Latest development version |
| Older releases | Best Effort | Community contributions welcome |

## Security Best Practices for Contributors

All code contributors must follow these security practices:

1. Input Validation: Always validate external inputs (files, API responses, user config)
2. Secrets: Never commit secrets; use environment variables only
3. Dependencies: Verify new dependencies do not introduce known vulnerabilities
4. Testing: Add tests for any security-related changes
5. Documentation: Document security implications of new features
6. Code Review: Security changes require review before merge

## Contact Information

Lead maintainer: Halis Aykut Cosgun (h.aykut.cosgun@gmail.com)

For general security inquiries or policy feedback, please contact the maintainer directly.

## Security Updates

Security updates are announced via:

- GitHub Security Advisories
- Release notes with SECURITY tag
- Email notification to registered stakeholders (opt-in)

## Disclaimer

SynthEd is provided AS IS for educational and research purposes. While security measures are implemented to the best of our ability, users accept responsibility for validating data appropriateness before deployment in production systems.

For sensitive research deployments, conduct independent security audits and data validation tests.
