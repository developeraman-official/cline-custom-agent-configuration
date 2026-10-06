---
name: bug-fixer
description: "Detects and fixes TypeScript errors: runs `npx tsc --noEmit`, proposes a minimal fix for each error, re-checks, runs the test suite, and logs each fix in fixed_issues_summary.md. Use when the user asks to fix bugs, run bug-fixer, run a tsc check, or when tests or the TypeScript build are failing."
---

# Bug Fixer

## Trigger
- User asks to "fix bugs", "run bug-fixer", or "run tsc check".
- Presence of failing tests, error logs, or TypeScript compilation errors.

## Steps
1. **TypeScript Check**  
   - Run `npx tsc --noEmit` in the project root.  
   - Capture the full compiler output (error code, file, line, message).

2. **Analyze Each Error**  
   - For every reported error, locate the source location.  
   - Determine root cause (type mismatch, missing import, unused variable, etc.).

3. **Generate Minimal Patch**  
   - Create the smallest change that resolves the specific error.  
   - Prefer adding missing types, fixing imports, correcting signatures, or removing dead code.

4. **Apply Patch**  
   - Apply the patch automatically (or present to user for approval if configured).  
   - After each fix, re‑run `npx tsc --noEmit` to confirm that *that* error is gone and no new errors were introduced.

5. **Run Test Suite**  
   - Execute the project's test command (e.g., `npm test`, `jest`, `vitest`).  
   - Ensure all tests pass; if a fix breaks tests, revert and try alternative fix.

6. **Log Fix in Summary**  
   - Append a row to `fixed_issues_summary.md` with:  
     - **Issue ID** – incremental (TS‑001, TS‑002, …)  
     - **Description** – compiler error message  
     - **Root Cause** – brief explanation  
     - **Fix Applied** – summary of code change (file + diff snippet)  
     - **Verification** – "tsc clean" and "tests pass"

7. **Iterate**  
   - Repeat steps 1‑6 until `npx tsc --noEmit` reports **zero errors**.

## Configuration
- Uses `agent-config.yaml` to confirm the default agent is `coderagent`.  
- Follows `rules.md` for bug‑fixing workflow and logging requirements.

## Example Usage
```
> Run bug-fixer on the current repo
```
The skill will iterate through all TypeScript errors reported by `tsc`, fix them one by one, run the test suite after each fix, and update `fixed_issues_summary.md`.