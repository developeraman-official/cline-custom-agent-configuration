#!/usr/bin/env python3
"""
Cline Agent System Initialization Script.

Run at the start of a session to validate the agent definitions and load any
persisted agent state.

Layout assumptions
------------------
* CONFIG dir : where agents/ and agent-config.yaml live. Defaults to the
               directory containing this script; override with $CLINE_DIR.
* WORKSPACE  : the project you are working on. Defaults to the current
               directory; override with --workspace. Agent state is stored in
               <WORKSPACE>/<persistence_dir> (default ".agent"), so it travels
               with the project and is not mixed into this config repo.

Exit codes: 0 = ok, 1 = problems found (invalid agent definitions or config).
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # optional at runtime; required to validate frontmatter
    yaml = None

FRONTMATTER = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n", re.S)


def load_config(config_dir: Path) -> dict:
    defaults = {"default_agent": "coderagent", "persistence_dir": ".agent"}
    cfg_file = config_dir / "agent-config.yaml"
    if not cfg_file.exists() or yaml is None:
        return defaults
    try:
        loaded = yaml.safe_load(cfg_file.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        print(f"   ⚠️  agent-config.yaml is not valid YAML: {exc}")
        return {**defaults, "_error": True}
    return {**defaults, **loaded}


def check_agents(agents_dir: Path):
    """Return (names, errors). Parses each agent's YAML frontmatter."""
    names, errors = [], []
    for path in sorted(agents_dir.glob("*.agent.md")):
        names.append(path.name[: -len(".agent.md")])
        if yaml is None:
            continue
        match = FRONTMATTER.match(path.read_text(encoding="utf-8"))
        if not match:
            errors.append(f"{path.name}: missing YAML frontmatter")
            continue
        try:
            meta = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError as exc:
            errors.append(f"{path.name}: invalid YAML frontmatter ({str(exc).splitlines()[0]})")
            continue
        for key in ("name", "description"):
            if not meta.get(key):
                errors.append(f"{path.name}: frontmatter is missing '{key}'")
    return names, errors


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"   ⚠️  Error reading {path.name}: {exc}")
        return None


def initialize_agent_system(workspace: Path) -> dict:
    config_dir = Path(os.environ.get("CLINE_DIR", Path(__file__).resolve().parent))
    config = load_config(config_dir)
    agent_dir = workspace / config["persistence_dir"]

    print("🔧 Initializing Cline Agent System...")
    print(f"   Config directory : {config_dir}")
    print(f"   Workspace        : {workspace}")
    print(f"   Agent state dir  : {agent_dir}")

    agent_dir.mkdir(parents=True, exist_ok=True)
    state_file, lanes_file = agent_dir / "state.json", agent_dir / "lanes.json"

    has_existing_state = state_file.exists() and lanes_file.exists()
    if has_existing_state:
        print("📂 Found existing agent state, loading...")
        state, lanes = read_json(state_file), read_json(lanes_file)
        if state is None or lanes is None:
            has_existing_state = False
            print("\n⚠️  State files unreadable, starting fresh (originals left untouched)")
        else:
            print(f"   ✅ Session: {state.get('session_id', 'unknown')}")
            print(f"   🎯 Goal: {state.get('goal') or '(none)'}")
            print(f"   📋 Todos: {len(state.get('todos', {}))}")
            print(f"   🛤️  Lanes: {len(state.get('lanes', {}))} (in lanes.json: {len(lanes.get('lanes', []))})")
            print(f"   📍 Current lane: {state.get('current_lane') or '(none)'}")
            print(f"   🕐 Last updated: {state.get('updated_at', '')}")
            summary = state.get("final_summary", "")
            if summary:
                print(f"   📝 Final summary: {summary[:100]}{'...' if len(summary) > 100 else ''}")
            print("\n✅ Agent system ready - will resume from previous session")
    else:
        print("📝 No existing state found, starting fresh session")

    agents_dir = config_dir / "agents"
    if agents_dir.exists():
        names, errors = check_agents(agents_dir)
    else:
        names, errors = [], [f"agents directory not found: {agents_dir}"]
    if config.get("_error"):
        errors.append("agent-config.yaml is invalid")

    print(f"\n🤖 Available agents ({len(names)}):")
    for name in names:
        print(f"   - {name}")

    default_agent = config["default_agent"]
    if names and default_agent.lower() not in {n.lower() for n in names}:
        errors.append(f"default_agent '{default_agent}' does not match any file in agents/")
    print(f"\n🎯 Default agent: {default_agent}")

    if yaml is None:
        print("   ℹ️  PyYAML not installed: agent frontmatter was not validated (pip install pyyaml)")

    if not errors:
        print("🚀 Cline Agent System initialized successfully!")
    else:
        print("\n❌ Problems found:")
        for err in errors:
            print(f"   - {err}")

    return {
        "initialized": not errors,
        "has_existing_state": has_existing_state,
        "agent_dir": str(agent_dir),
        "default_agent": default_agent,
        "available_agents": names,
        "errors": errors,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate Cline agents and load persisted agent state.")
    parser.add_argument("--workspace", default=os.getcwd(), help="project directory that holds the agent state dir")
    args = parser.parse_args()
    sys.exit(0 if initialize_agent_system(Path(args.workspace).resolve())["initialized"] else 1)
