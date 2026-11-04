# Workspace Guidance

- This is a Windows-first platform administration scripting workspace. Prefer PowerShell for Windows and Microsoft platform automation; use Python when it is a better fit for the task.
- Treat scripts as operational tooling: validate parameters and prerequisites, fail clearly, and avoid hidden side effects.
- Make mutating PowerShell commands support `-WhatIf` and `-Confirm` with `SupportsShouldProcess` whenever practical. Keep read-only discovery separate from changes.
- Follow least privilege. Never hard-code credentials, tokens, private keys, or environment-specific IDs. Use approved secret stores and avoid logging sensitive values.
- Include structured, actionable logging and meaningful exit behavior. Do not log secrets or unnecessary personal data.
- Add focused Pester tests for PowerShell behavior; isolate external services behind mocks or injectable commands so tests do not require production access.
- Document prerequisites, required permissions, expected impact, verification, and rollback in `docs/runbooks/` for operational changes.
- Keep dependencies minimal, preserve compatibility with the target platform, and state required PowerShell/Python versions.
- Do not perform destructive or production-facing actions without explicit user direction. Prefer examples and dry-run guidance when requirements are underspecified.
