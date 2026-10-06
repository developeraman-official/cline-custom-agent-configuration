# Project Rules for Coder Agent

## General Guidelines
- Use **coderagent** as the default agent for all coding tasks.
- Follow existing code conventions and patterns in the repository.
- Only use libraries and frameworks confirmed to be in use.
- Provide complete, functional code without omissions or placeholders.
- Be explicit about assumptions or limitations.

## Bug Fixing Rules
1. **Reproduce** the bug before fixing.
2. **Write a test** that fails because of the bug.
3. **Apply minimal fix** to resolve the issue.
4. **Run tests** to ensure fix works and no regressions.
5. **Document** the fix in the summary file.

## Code Quality
- Run linters / formatters before committing.
- Keep changes focused and atomic.
- Update documentation if behavior changes.

## Communication
- Summarize changes in `fixed_issues_summary.md` after each bug‑fix session.
- Include: issue ID, description, root cause, fix, verification steps.