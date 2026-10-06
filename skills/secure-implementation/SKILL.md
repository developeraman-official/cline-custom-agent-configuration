---
name: secure-implementation
description: "Apply to every code implementation, review, or fix. Check authentication and authorization boundaries, secret and internal-data exposure, unsafe logging, hardcoded credentials, API validation, database access, and run project-appropriate security and build verification."
---

# Secure Implementation And Verification

Use this checklist for implementation, review, and fixes. Keep investigation scoped to the affected path; widen only when evidence points to shared risk.

## Security Review And Fixes

- Trace authentication and authorization on every affected path, including ownership/tenant checks and privilege boundaries. Authentication alone does not authorize access.
- Search the scoped files for hardcoded credentials, API keys, tokens, passwords, private keys, and connection strings. Treat regex hits as candidates; inspect surrounding code without copying secret values into reports or chat. Use the project's secret scanner when configured.
- Trace data returned to clients and errors: never send secrets, session/cookie data, internal records, stack traces, SQL, raw provider responses, or private diagnostics to clients. Return a generic public error and keep useful detail server-side.
- Use the existing structured logger where available. Avoid `console.log`/`console.error` for production diagnostics; never log credentials, tokens, cookies, personal data, request bodies, or raw errors that may contain them. Redact sensitive fields.
- Validate and bound untrusted inputs. For APIs, inspect auth, schema validation, rate limits, timeouts, retries, URL/SSRF risk, and safe error mapping as relevant. For databases, inspect parameterization, tenant scoping, transaction boundaries, and resource limits as relevant.
- Fix confirmed issues in scope. Do not claim a regex scan alone proves security; report unverified concerns and residual risks.

## Project-Aware Verification

1. Detect the actual package manager, project scripts, and configured test/type/lint/build tooling from manifests and lockfiles. Do not assume commands from another stack.
2. Run focused tests/diagnostics first, then applicable project gates. Run `nox` only when a Nox configuration exists; run TypeScript `tsc --noEmit` only when TypeScript is configured; run the repository's build/test/lint scripts when relevant. Use the repository's package-manager executable (`pnpm`, `npm`, or `yarn`) rather than mixing lockfiles.
3. Run a read-only dependency audit for dependency/security tasks or when dependency files change. If remediation is requested and compatible automatic fixes are available, use the package manager's documented fix command. For npm the command is `npm audit fix`, not `npx audit fix`. Never add `--force` by default; major-version changes or lockfile-wide churn require review. Re-run focused checks and build after any dependency fix.
4. Report the exact checks run and their results. If a tool is unavailable or not configured, say so; do not imply it passed.
