"""
clenv - CLI Environment Manager
Scanner: detects installed CLI tools across all package managers
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ─── Data Model ───────────────────────────────────────────────────────────────

@dataclass
class CLITool:
    name: str
    source: str          # brew / npm / pip / pipx / cargo / gem / go / apt / system / binary
    version: str = "unknown"
    binary_path: str = ""
    uninstall_cmd: list[str] = field(default_factory=list)
    config_paths: list[str] = field(default_factory=list)
    description: str = ""
    last_used: Optional[str] = None

    @property
    def source_icon(self) -> str:
        icons = {
            "brew":   "🍺",
            "npm":    "📦",
            "pip":    "🐍",
            "pipx":   "🐍",
            "cargo":  "🦀",
            "gem":    "💎",
            "go":     "🐹",
            "apt":    "🐧",
            "dnf":    "🎩",
            "system": "⚙️ ",
            "binary": "📁",
        }
        return icons.get(self.source, "❓")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _run(cmd: list[str], timeout: int = 10) -> tuple[int, str, str]:
    """Run a subprocess, return (returncode, stdout, stderr)."""
    try:
        # Resolve command path (vital for .cmd/.bat files on Windows)
        if cmd:
            resolved = _which(cmd[0])
            if resolved:
                cmd = [resolved] + cmd[1:]
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError):
        return -1, "", ""


def _which(name: str) -> str:
    path = shutil.which(name)
    return path or ""


def _guess_config_paths(name: str) -> list[str]:
    """Return likely leftover config/cache paths for a tool."""
    home = Path.home()
    candidates = [
        home / f".{name}",
        home / f".{name}rc",
        home / f".config" / name,
        home / f".cache" / name,
        home / f".local" / "share" / name,
        Path("/etc") / name,
    ]
    return [str(p) for p in candidates if p.exists()]


# ─── Per-Manager Scanners ─────────────────────────────────────────────────────

def scan_brew() -> list[CLITool]:
    tools: list[CLITool] = []
    if not _which("brew"):
        return tools
    rc, out, _ = _run(["brew", "list", "--formula", "-1"])
    if rc != 0:
        return tools
    for name in out.splitlines():
        name = name.strip()
        if not name:
            continue
        _, info_out, _ = _run(["brew", "info", "--json=v1", name], timeout=15)
        version = "unknown"
        desc = ""
        try:
            data = json.loads(info_out)
            if data:
                version = data[0].get("installed", [{}])[0].get("version", "unknown")
                desc = data[0].get("desc", "")
        except (json.JSONDecodeError, IndexError, KeyError):
            pass
        binary = _which(name)
        tools.append(CLITool(
            name=name,
            source="brew",
            version=version,
            binary_path=binary,
            uninstall_cmd=["brew", "uninstall", "--force", name],
            config_paths=_guess_config_paths(name),
            description=desc,
        ))
    return tools


def scan_npm() -> list[CLITool]:
    tools: list[CLITool] = []
    if not _which("npm"):
        return tools
    rc, out, _ = _run(["npm", "list", "-g", "--depth=0", "--json"], timeout=20)
    if rc not in (0, 1):  # npm returns 1 when there are peer dep warnings
        return tools
    try:
        data = json.loads(out)
        deps = data.get("dependencies", {})
    except json.JSONDecodeError:
        return tools
    for pkg, meta in deps.items():
        version = meta.get("version", "unknown")
        # derive likely binary name (strip @scope/prefix)
        bin_name = pkg.split("/")[-1]
        binary = _which(bin_name)
        tools.append(CLITool(
            name=pkg,
            source="npm",
            version=version,
            binary_path=binary or "",
            uninstall_cmd=["npm", "uninstall", "-g", pkg],
            config_paths=_guess_config_paths(bin_name),
        ))
    return tools


def scan_pipx() -> list[CLITool]:
    tools: list[CLITool] = []
    if not _which("pipx"):
        return tools
    rc, out, _ = _run(["pipx", "list", "--json"], timeout=20)
    if rc != 0:
        return tools
    try:
        data = json.loads(out)
        venvs = data.get("venvs", {})
    except json.JSONDecodeError:
        return tools
    for pkg, meta in venvs.items():
        version = meta.get("metadata", {}).get("main_package", {}).get("package_version", "unknown")
        binary = _which(pkg)
        tools.append(CLITool(
            name=pkg,
            source="pipx",
            version=version,
            binary_path=binary or "",
            uninstall_cmd=["pipx", "uninstall", pkg],
            config_paths=_guess_config_paths(pkg),
        ))
    return tools


def scan_pip() -> list[CLITool]:
    """Find pip-installed packages that expose console_scripts (actual CLI tools)."""
    tools: list[CLITool] = []
    if not _which("pip3") and not _which("pip"):
        return tools
    pip_cmd = "pip3" if _which("pip3") else "pip"

    # Get scripts directory
    rc, scripts_dir, _ = _run([pip_cmd, "show", "pip"], timeout=10)
    rc2, out, _ = _run([pip_cmd, "list", "--format=json"], timeout=20)
    if rc2 != 0:
        return tools
    try:
        packages = json.loads(out)
    except json.JSONDecodeError:
        return tools

    for pkg in packages:
        name = pkg["name"]
        version = pkg["version"]
        # Only include if binary exists in PATH
        bin_candidates = [name, name.lower(), name.replace("-", "_"), name.replace("_", "-")]
        binary = next((_which(b) for b in bin_candidates if _which(b)), "")
        if not binary:
            continue
        # Skip known non-CLI packages
        skip = {"pip", "setuptools", "wheel", "pkg-resources"}
        if name.lower() in skip:
            continue
        tools.append(CLITool(
            name=name,
            source="pip",
            version=version,
            binary_path=binary,
            uninstall_cmd=[sys.executable, "-m", "pip", "uninstall", "-y", name],
            config_paths=_guess_config_paths(name.lower()),
        ))
    return tools


def scan_cargo() -> list[CLITool]:
    tools: list[CLITool] = []
    cargo_bin = Path.home() / ".cargo" / "bin"
    if not cargo_bin.exists():
        return tools

    # Read .crates2.json for metadata
    crates_file = Path.home() / ".cargo" / ".crates2.json"
    bin_to_crate: dict[str, tuple[str, str]] = {}  # bin_name -> (crate_name, version)
    if crates_file.exists():
        try:
            data = json.loads(crates_file.read_text())
            for key, meta in data.get("installs", {}).items():
                # key format: "crate_name version (registry+...)"
                parts = key.split(" ")
                if len(parts) >= 2:
                    crate_name = parts[0]
                    version = parts[1]
                    for bin_name in meta.get("bins", []):
                        bin_to_crate[bin_name] = (crate_name, version)
        except Exception:
            pass

    for binary in cargo_bin.iterdir():
        if binary.name.endswith((".d", ".rlib")) or not binary.is_file():
            continue
        bin_name = binary.name
        
        # Match binary name to crate name & version
        if bin_name in bin_to_crate:
            crate_name, version = bin_to_crate[bin_name]
        else:
            # Fallback for Windows where extensions differ or files aren't in json
            stem = binary.stem
            crate_name, version = bin_to_crate.get(stem, (stem, "unknown"))
            
        tools.append(CLITool(
            name=crate_name,
            source="cargo",
            version=version,
            binary_path=str(binary),
            uninstall_cmd=["cargo", "uninstall", crate_name],
            config_paths=_guess_config_paths(crate_name),
        ))
    return tools


def scan_gem() -> list[CLITool]:
    tools: list[CLITool] = []
    if not _which("gem"):
        return tools
    rc, out, _ = _run(["gem", "list", "--no-versions"], timeout=15)
    if rc != 0:
        return tools
    # Filter to gems that put a binary in PATH
    for name in out.splitlines():
        name = name.strip()
        if not name or name.startswith("***"):
            continue
        binary = _which(name)
        if not binary:
            continue
        _, ver_out, _ = _run(["gem", "list", name, "--exact"])
        version = "unknown"
        if "(" in ver_out:
            version = ver_out.split("(")[-1].rstrip(")")
        tools.append(CLITool(
            name=name,
            source="gem",
            version=version,
            binary_path=binary,
            uninstall_cmd=["gem", "uninstall", "-x", name],
            config_paths=_guess_config_paths(name),
        ))
    return tools


def scan_go() -> list[CLITool]:
    tools: list[CLITool] = []
    gopath = os.environ.get("GOPATH", str(Path.home() / "go"))
    go_bin = Path(gopath) / "bin"
    if not go_bin.exists():
        return tools
    for binary in go_bin.iterdir():
        if binary.is_file() and os.access(binary, os.X_OK):
            tools.append(CLITool(
                name=binary.name,
                source="go",
                version="unknown",
                binary_path=str(binary),
                # Go has no uninstall command; just remove the binary
                uninstall_cmd=["rm", "-f", str(binary)],
                config_paths=_guess_config_paths(binary.name),
            ))
    return tools


def scan_apt() -> list[CLITool]:
    tools: list[CLITool] = []
    if not _which("dpkg"):
        return tools
    rc, out, _ = _run(["dpkg", "-l"], timeout=15)
    if rc != 0:
        return tools
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 4 or not line.startswith("ii"):
            continue
        name = parts[1].split(":")[0]
        version = parts[2]
        binary = _which(name)
        if not binary:
            continue
        tools.append(CLITool(
            name=name,
            source="apt",
            version=version,
            binary_path=binary,
            uninstall_cmd=["sudo", "apt", "remove", "-y", name],
            config_paths=_guess_config_paths(name),
        ))
    return tools


# ─── Shell History Last-Used ───────────────────────────────────────────────────

def _load_shell_history() -> list[str]:
    """Load recent shell history lines."""
    history_files = [
        Path.home() / ".bash_history",
        Path.home() / ".zsh_history",
        Path.home() / ".local" / "share" / "fish" / "fish_history",
    ]
    lines: list[str] = []
    for hf in history_files:
        if hf.exists():
            try:
                text = hf.read_text(errors="ignore")
                lines.extend(text.splitlines()[-2000:])
            except OSError:
                pass
    return lines


def annotate_last_used(tools: list[CLITool]) -> None:
    """Tag each tool with whether it appears in recent shell history."""
    history = _load_shell_history()
    history_text = "\n".join(history)
    for tool in tools:
        bin_name = Path(tool.binary_path).name if tool.binary_path else tool.name.split("/")[-1]
        if bin_name in history_text:
            tool.last_used = "seen in history"
        else:
            tool.last_used = "never / not found"


# ─── Main Entry ───────────────────────────────────────────────────────────────

SCANNERS = [
    ("Homebrew",  scan_brew),
    ("npm (global)", scan_npm),
    ("pipx",      scan_pipx),
    ("pip",       scan_pip),
    ("Cargo",     scan_cargo),
    ("RubyGems",  scan_gem),
    ("Go",        scan_go),
    ("APT/dpkg",  scan_apt),
]


def scan_all(progress_cb=None) -> list[CLITool]:
    """Run all scanners. progress_cb(label) called before each scanner."""
    all_tools: list[CLITool] = []
    seen_bins: set[str] = set()

    for label, fn in SCANNERS:
        if progress_cb:
            progress_cb(label)
        try:
            found = fn()
        except Exception:
            found = []

        for tool in found:
            key = tool.binary_path or f"{tool.source}:{tool.name}"
            if key not in seen_bins:
                seen_bins.add(key)
                all_tools.append(tool)

    annotate_last_used(all_tools)
    return all_tools
