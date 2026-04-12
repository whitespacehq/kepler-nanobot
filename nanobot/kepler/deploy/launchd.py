"""Generate and manage a macOS launchd plist for the NanoBot gateway."""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path


LABEL = "com.whitespace.kepler-nanobot"
PLIST_NAME = f"{LABEL}.plist"


def _launch_agents_dir() -> Path:
    return Path.home() / "Library" / "LaunchAgents"


def _plist_path() -> Path:
    return _launch_agents_dir() / PLIST_NAME


def generate_plist(repo_root: Path) -> dict:
    """Build the plist dict for the gateway, using paths relative to *repo_root*."""
    venv_python = repo_root / ".venv" / "bin" / "python"
    config_path = repo_root / "config.json"
    log_dir = repo_root / "logs"

    if not venv_python.exists():
        raise FileNotFoundError(f"Venv not found: {venv_python}")
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    log_dir.mkdir(exist_ok=True)

    # Load .env so we can inline env vars into the plist.
    # launchd doesn't inherit shell env, so everything must be explicit.
    env_vars = _load_dotenv(repo_root / ".env")
    env_vars.update({
        "HOME": str(Path.home()),
        "PATH": _build_path(),
    })

    return {
        "Label": LABEL,
        "Comment": "Kepler NanoBot Gateway",
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 10,
        "WorkingDirectory": str(repo_root),
        "ProgramArguments": [
            str(venv_python),
            "-m", "nanobot",
            "gateway",
            "--config", str(config_path),
        ],
        "StandardOutPath": str(log_dir / "gateway.log"),
        "StandardErrorPath": str(log_dir / "gateway.err.log"),
        "EnvironmentVariables": env_vars,
    }


def _load_dotenv(path: Path) -> dict[str, str]:
    """Minimal .env parser — no dependency on python-dotenv at generation time."""
    env = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def _build_path() -> str:
    """Build a PATH that includes common tool locations."""
    candidates = [
        Path.home() / ".local" / "bin",
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
        Path("/usr/bin"),
        Path("/bin"),
    ]
    return ":".join(str(p) for p in candidates if p.exists())


def install(repo_root: Path) -> Path:
    """Generate and install the plist. Returns the plist path."""
    plist = generate_plist(repo_root)
    dest = _plist_path()
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Unload first if already installed.
    if dest.exists():
        subprocess.run(["launchctl", "unload", str(dest)], capture_output=True)

    with open(dest, "wb") as f:
        plistlib.dump(plist, f)

    subprocess.run(["launchctl", "load", str(dest)], check=True)
    return dest


def uninstall() -> None:
    """Unload and remove the plist."""
    dest = _plist_path()
    if dest.exists():
        subprocess.run(["launchctl", "unload", str(dest)], capture_output=True)
        dest.unlink()


def status() -> str:
    """Check if the service is loaded."""
    result = subprocess.run(
        ["launchctl", "list", LABEL],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        # Parse PID from output
        for line in result.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) >= 3 and parts[2] == LABEL:
                pid = parts[0]
                return f"running (PID {pid})" if pid != "-" else "loaded but not running"
        return "loaded"
    return "not installed"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Manage Kepler NanoBot launchd service")
    parser.add_argument("action", choices=["install", "uninstall", "status", "generate"])
    parser.add_argument("--repo", default=None, help="Path to kepler-nanobot repo root")
    args = parser.parse_args()

    repo = Path(args.repo) if args.repo else Path(__file__).resolve().parents[3]

    if args.action == "install":
        dest = install(repo)
        print(f"Installed and loaded: {dest}")
    elif args.action == "uninstall":
        uninstall()
        print("Unloaded and removed.")
    elif args.action == "status":
        print(f"Kepler NanoBot: {status()}")
    elif args.action == "generate":
        plist = generate_plist(repo)
        plistlib.dump(plist, sys.stdout.buffer)
