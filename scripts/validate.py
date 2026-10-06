#!/usr/bin/env python3
"""
Repository validation. Run locally (`python scripts/validate.py`) or in CI.

Checks (tracked files only, via `git ls-files`):
  1. every .json file parses
  2. agent-config.yaml parses and its default_agent exists in agents/
  3. every agents/*.agent.md has valid YAML frontmatter with name + description
  4. every skills/*/ has a valid SKILL.md (delegates to skill-creator's quick_validate.py)
  5. every .py file compiles
  6. secret / machine-local files are not tracked, and no obvious credentials are committed
  7. relative markdown links resolve

Requires: Python 3.9+, PyYAML.
"""
import json
import py_compile
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
FRONTMATTER = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n", re.S)

FORBIDDEN_TRACKED = {
    "data/secrets.json",
    "data/settings/providers.json",
    "data/globalState.json",
}
FORBIDDEN_PATTERNS = [r"(^|/)\.env(\..*)?$"]

# Well-known credential shapes. Placeholders such as <YOUR_..._KEY> never match.
SECRET_PATTERNS = {
    "OpenRouter key": re.compile(r"sk-or-v1-[A-Za-z0-9]{20,}"),
    "NVIDIA key": re.compile(r"nvapi-[A-Za-z0-9_\-]{20,}"),
    "Anthropic key": re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    "OpenAI-style key": re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "AWS access key id": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}
# JSON config fields that must hold a placeholder (<...>) or be empty when committed.
SECRET_FIELD = re.compile(r'"(apiKey|openRouterApiKey|[A-Za-z]*ApiKey|[A-Za-z]*Secret|[A-Za-z]*Token)"\s*:\s*"([^"]*)"')

errors = []


def fail(msg):
    errors.append(msg)
    print(f"  ✗ {msg}")


def tracked():
    out = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode("utf-8")
    return [p for p in out.split("\0") if p and (ROOT / p).is_file()]


def section(title):
    print(f"\n== {title}")


def check_json(files):
    section("JSON files parse")
    for f in (f for f in files if f.endswith(".json")):
        try:
            json.loads((ROOT / f).read_text(encoding="utf-8"))
        except ValueError as exc:
            fail(f"{f}: {exc}")


def check_agents(files):
    section("Agent definitions")
    names = set()
    for f in (f for f in files if re.fullmatch(r"agents/[^/]+\.agent\.md", f)):
        names.add(Path(f).name[: -len(".agent.md")].lower())
        m = FRONTMATTER.match((ROOT / f).read_text(encoding="utf-8"))
        if not m:
            fail(f"{f}: missing YAML frontmatter")
            continue
        try:
            meta = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError as exc:
            fail(f"{f}: invalid YAML frontmatter ({str(exc).splitlines()[0]})")
            continue
        for key in ("name", "description"):
            if not meta.get(key):
                fail(f"{f}: frontmatter missing '{key}'")
        tools = meta.get("tools")
        if isinstance(tools, list):
            dups = sorted({t for t in tools if tools.count(t) > 1})
            if dups:
                fail(f"{f}: duplicate tools {dups}")
    cfg = ROOT / "agent-config.yaml"
    if cfg.exists():
        try:
            data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            fail(f"agent-config.yaml: {exc}")
            return
        default = str(data.get("default_agent", "")).lower()
        if default and default not in names:
            fail(f"agent-config.yaml: default_agent '{default}' has no agents/{default}.agent.md")


def check_skills(files):
    section("Skills")
    validator = ROOT / "skills" / "skill-creator" / "scripts" / "quick_validate.py"
    skill_dirs = sorted({Path(f).parts[1] for f in files if re.fullmatch(r"skills/[^/]+/SKILL\.md", f)})
    for d in (d for d in sorted({Path(f).parts[1] for f in files if f.startswith("skills/")}) if d not in skill_dirs):
        fail(f"skills/{d}: no SKILL.md")
    for d in skill_dirs:
        if not validator.exists():
            fail("skills/skill-creator/scripts/quick_validate.py missing; cannot validate skills")
            return
        r = subprocess.run([sys.executable, str(validator), str(ROOT / "skills" / d)], capture_output=True, text=True)
        if r.returncode != 0:
            fail(f"skills/{d}: {(r.stdout + r.stderr).strip().splitlines()[-1] if (r.stdout + r.stderr).strip() else 'invalid'}")


def check_python(files):
    section("Python compiles")
    with tempfile.TemporaryDirectory() as tmp:
        for f in (f for f in files if f.endswith(".py")):
            try:
                py_compile.compile(str(ROOT / f), cfile=str(Path(tmp) / "x.pyc"), doraise=True)
            except py_compile.PyCompileError as exc:
                fail(f"{f}: {exc.msg.strip().splitlines()[-1]}")


def check_secrets(files):
    section("No secrets or machine-local state committed")
    for f in files:
        if f in FORBIDDEN_TRACKED or any(re.search(p, f) for p in FORBIDDEN_PATTERNS):
            fail(f"{f}: must not be tracked (gitignored; use the *.example.json template)")
    for f in files:
        if f.startswith("skills/logo-design/assets/library/svg/") or not f.endswith((".json", ".md", ".yaml", ".yml", ".py", ".ts", ".txt")):
            continue
        text = (ROOT / f).read_text(encoding="utf-8", errors="ignore")
        for label, pat in SECRET_PATTERNS.items():
            if pat.search(text):
                fail(f"{f}: looks like a committed {label}")
        if f.endswith(".json"):
            for m in SECRET_FIELD.finditer(text):
                value = m.group(2)
                if value and not (value.startswith("<") and value.endswith(">")):
                    fail(f"{f}: field '{m.group(1)}' holds a real-looking value; use a <PLACEHOLDER>")


def check_links(files):
    section("Relative markdown links")
    for f in (f for f in files if f.endswith(".md")):
        base = (ROOT / f).parent
        text = (ROOT / f).read_text(encoding="utf-8", errors="ignore")
        text = re.sub(r"```.*?```", "", text, flags=re.S)  # ignore fenced code
        for m in re.finditer(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", text):
            target = m.group(1)
            if re.match(r"[a-zA-Z][a-zA-Z0-9+.\-]*:", target):
                continue
            if not (base / target).resolve().exists():
                fail(f"{f}: broken link -> {target}")


def main():
    files = tracked()
    print(f"Validating {len(files)} tracked files")
    for check in (check_json, check_agents, check_skills, check_python, check_secrets, check_links):
        check(files)
    print()
    if errors:
        print(f"FAILED: {len(errors)} problem(s)")
        return 1
    print("OK: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
