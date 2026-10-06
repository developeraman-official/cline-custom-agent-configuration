# cline-configuration

Personal [Cline](https://docs.cline.bot) configuration: an orchestrator/worker agent setup, a few custom skills, and non-secret settings.

The layout mirrors Cline's config directory (`~/.cline/`, with app data under `data/`), so you can clone it there, or into a project's `.cline/` directory for project-scoped use.

## Layout

| Path | What it is |
|------|-----------|
| `agents/` | Agent definitions (`*.agent.md`, YAML frontmatter + instructions) |
| `skills/` | Skills: `auth-best-practices`, `bug-fixer`, `logo-design`, `razorpay-integration-skill`, `secure-implementation`, `skill-creator` |
| `agent-config.yaml` | Default agent and where agent state is persisted |
| `rules.md` | Project rules for the coder agent |
| `initialize_agents.py` | Validates agent definitions and reports saved session state |
| `data/settings/` | Non-secret Cline settings (`global-settings.json`, `models.json`, MCP settings) |
| `scripts/validate.py` | Repository checks, also run in CI |
| `fixed_issues_summary.md` | Log appended to by the `bug-fixer` skill |

## Setup

1. Clone into your Cline config directory (or a project's `.cline/`).
2. Create your local, **untracked** credential files from the templates:
   ```bash
   cp data/secrets.example.json data/secrets.json
   cp data/settings/providers.example.json data/settings/providers.json
   ```
   Then replace every `<YOUR_..._KEY>` placeholder with your own key. These files are in `.gitignore`; CI fails if they are ever committed.
3. Check the setup:
   ```bash
   pip install pyyaml
   python initialize_agents.py --workspace /path/to/your/project
   ```

## How the agents work

`coderagent` is the default agent. For a multi-part task it:

1. builds a todo list and groups todos into **lanes** that never write the same file,
2. dispatches the lanes in parallel to `coder-worker` (max 10 at a time, 120 s timeout, up to 3 retries per lane),
3. **applies** the `proposed_changes` each worker returns (workers never write files), then runs typecheck, lint and tests,
4. persists its state to `<workspace>/.agent/state.json` and `lanes.json` so a closed editor can resume.

`coder` and `coder-architect` are variants of the same orchestrator. The specialist agents (`authentication-`, `database-`, `api-integration-specialist`, `security-reviewer`) all apply the `secure-implementation` skill.

## Validation

```bash
python scripts/validate.py
```

Checks JSON validity, agent and skill frontmatter, Python compilation, relative links, and that no secrets or machine-local state are tracked. The same script runs in GitHub Actions on every push to `main` and every pull request.

## Security note

Never commit API keys. If a real key was ever committed to this repository, rotate it: removing a file from the latest commit does not remove it from git history.
# cline-custom-agent-configuration
# cline-custom-agent-configuration
