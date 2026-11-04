# Platform Administration Scripts

A Windows-first workspace for PowerShell automation, with room for Python utilities. Keep scripts small, repeatable, and safe to run across managed environments.

## Layout

- `scripts/powershell/` - operational scripts and task-specific automation
- `modules/powershell/` - reusable PowerShell functions and modules
- `scripts/python/` - optional Python helpers
- `tests/powershell/` - Pester tests
- `docs/runbooks/` - operator procedures, prerequisites, and rollback steps
- `examples/` - sanitized input and configuration examples

## Working Safely

- Start with read-only behavior where possible. For changes, support `-WhatIf` and `-Confirm` using `SupportsShouldProcess`.
- Validate inputs and required permissions before making changes; use least privilege.
- Never commit passwords, tokens, private keys, tenant-specific identifiers, or production data. Read secrets from an approved secret store at runtime.
- Log useful operational context without recording credentials or unnecessary personal data.
- Test against mocks, a lab, or a non-production environment before production use. Document prerequisites, impact, verification, and rollback in a runbook.

## PowerShell

Use PowerShell 7+ where supported by the target platform; document when Windows PowerShell 5.1 is required. Keep public functions approved-verb named and include comment-based help for reusable commands. Pester tests belong under `tests/powershell/` and should not require production access.

## Python

Use Python only where it materially improves the task or supports a platform without practical PowerShell tooling. Keep dependencies minimal and record them in a per-tool `requirements.txt` when needed.
