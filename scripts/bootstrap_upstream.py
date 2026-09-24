#!/usr/bin/env python3
"""Install/update the upstream codex-with-chatgpt checkout and Codex skill.

This bootstraps only the upstream code, build, and local skill file required by
chatgpt-pr-loop's transport/HANDOFF layer. It intentionally does NOT run
`c2c setup` or create MCP/Cloudflare/ChatGPT connectors.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

UPSTREAM_REPO = "https://github.com/XiaoDuoYa/codex-with-chatgpt.git"
UPSTREAM_WEB = "https://github.com/XiaoDuoYa/codex-with-chatgpt"
PLACEHOLDER = "<ACTUAL_CHECKOUT_PATH>"
MIN_NODE_MAJOR = 20


class BootstrapError(RuntimeError):
    pass


def run(cmd: list[str], cwd: Path | None = None, capture: bool = False) -> str:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    if proc.returncode != 0:
        detail = ""
        if capture:
            detail = (proc.stderr or proc.stdout or "").strip()
        suffix = f": {detail}" if detail else ""
        raise BootstrapError(f"command failed ({proc.returncode}): {' '.join(cmd)}{suffix}")
    return (proc.stdout or "").strip() if capture else ""


def node_major(version: str) -> int | None:
    match = re.match(r"^v?(\d+)(?:\.|$)", version.strip())
    return int(match.group(1)) if match else None


def normalize_remote(value: str) -> str:
    value = value.strip().rstrip("/")
    if value.endswith(".git"):
        value = value[:-4]
    if value.startswith("git@github.com:"):
        value = "https://github.com/" + value[len("git@github.com:") :]
    return value.lower()


def render_upstream_skill(source: str, checkout: Path) -> str:
    if PLACEHOLDER not in source:
        raise BootstrapError("upstream SKILL.md no longer contains the checkout placeholder")
    return source.replace(PLACEHOLDER, str(checkout.resolve()))


def default_checkout() -> Path:
    return Path.home() / ".codex" / "vendor" / "codex-with-chatgpt"


def default_skill_dir() -> Path:
    return Path.home() / ".codex" / "skills" / "codex-with-chatgpt"


def git_head(checkout: Path) -> str | None:
    if not (checkout / ".git").is_dir():
        return None
    try:
        return run(["git", "rev-parse", "HEAD"], cwd=checkout, capture=True)
    except BootstrapError:
        return None


def status(checkout: Path, skill_dir: Path) -> dict:
    skill_path = skill_dir / "SKILL.md"
    return {
        "upstreamRepository": UPSTREAM_WEB,
        "checkout": str(checkout),
        "checkoutPresent": (checkout / ".git").is_dir(),
        "upstreamHead": git_head(checkout),
        "installedSkill": str(skill_path),
        "skillPresent": skill_path.is_file(),
        "mcpSetup": "not-managed-by-chatgpt-pr-loop",
    }


def ensure_prerequisites() -> tuple[str, str, str]:
    git = shutil.which("git")
    node = shutil.which("node")
    corepack = shutil.which("corepack")
    if not git:
        raise BootstrapError("git is required")
    if not node:
        raise BootstrapError("Node.js >= 20 is required")
    version = run([node, "--version"], capture=True)
    major = node_major(version)
    if major is None or major < MIN_NODE_MAJOR:
        raise BootstrapError(f"Node.js >= {MIN_NODE_MAJOR} is required; found {version or 'unknown'}")
    if not corepack:
        raise BootstrapError("corepack is required (normally bundled with Node.js)")
    return git, node, corepack


def install_or_update(checkout: Path, skill_dir: Path, skip_build: bool = False) -> dict:
    git, _node, corepack = ensure_prerequisites()
    checkout = checkout.expanduser().resolve()
    skill_dir = skill_dir.expanduser().resolve()

    if checkout.exists() and not (checkout / ".git").is_dir():
        if any(checkout.iterdir()):
            raise BootstrapError(f"checkout path exists but is not a git repository: {checkout}")
        checkout.rmdir()

    if not checkout.exists():
        checkout.parent.mkdir(parents=True, exist_ok=True)
        run([git, "clone", "--branch", "main", "--single-branch", UPSTREAM_REPO, str(checkout)])
    else:
        remote = run([git, "remote", "get-url", "origin"], cwd=checkout, capture=True)
        if normalize_remote(remote) != normalize_remote(UPSTREAM_REPO):
            raise BootstrapError(f"existing checkout has unexpected origin: {remote}")
        dirty = run([git, "status", "--porcelain"], cwd=checkout, capture=True)
        if dirty:
            raise BootstrapError(
                "upstream checkout has local changes; refusing to overwrite them. "
                "Commit/stash/remove those changes, then rerun."
            )
        run([git, "fetch", "origin", "main"], cwd=checkout)
        run([git, "checkout", "main"], cwd=checkout)
        run([git, "merge", "--ff-only", "origin/main"], cwd=checkout)

    if not skip_build:
        run([corepack, "pnpm", "install"], cwd=checkout)
        run([corepack, "pnpm", "build"], cwd=checkout)

    source_skill = checkout / "skill" / "SKILL.md"
    if not source_skill.is_file():
        raise BootstrapError(f"upstream skill not found: {source_skill}")
    rendered = render_upstream_skill(source_skill.read_text(encoding="utf-8"), checkout)

    skill_dir.mkdir(parents=True, exist_ok=True)
    target = skill_dir / "SKILL.md"
    target.write_text(rendered, encoding="utf-8")

    result = status(checkout, skill_dir)
    result.update(
        {
            "ok": True,
            "built": not skip_build,
            "note": (
                "Upstream transport skill installed. chatgpt-pr-loop does not run "
                "c2c setup or create MCP/Cloudflare/ChatGPT connectors."
            ),
        }
    )
    return result


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--checkout", default=str(default_checkout()))
    p.add_argument("--skill-dir", default=str(default_skill_dir()))
    p.add_argument("--check", action="store_true", help="report status without changing anything")
    p.add_argument("--skip-build", action="store_true", help="developer/testing only")
    return p


def main() -> None:
    args = parser().parse_args()
    checkout = Path(args.checkout).expanduser()
    skill_dir = Path(args.skill_dir).expanduser()
    try:
        if args.check:
            result = {"ok": True, **status(checkout, skill_dir)}
        else:
            result = install_or_update(checkout, skill_dir, skip_build=args.skip_build)
        print(json.dumps(result, indent=2, sort_keys=True))
    except BootstrapError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2, sort_keys=True))
        raise SystemExit(2)


if __name__ == "__main__":
    main()
