# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in OpenQuery, please report it responsibly.

**Do not open a public issue.** Instead, email **security@dacrypt.dev** with:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will acknowledge receipt within 48 hours and provide a timeline for a fix.

## Scope

Security issues in the following areas are in scope:

- Authentication bypass in the API server
- Injection vulnerabilities (command injection, XSS in API responses)
- Information disclosure through error messages or logs
- Insecure handling of API keys or credentials
- Dependency vulnerabilities

## Out of Scope

- Rate limiting bypass (this is a convenience feature, not a security boundary)
- CAPTCHA solving effectiveness
- Availability of external data sources
- Issues in external dependencies (report those upstream)

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x | Yes |
