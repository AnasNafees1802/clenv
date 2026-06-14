"""
clenv - Uninstaller
Runs removal commands and cleans up leftover config/cache paths.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable

from .scanner import CLITool


def _run_cmd(cmd: list[str], sudo: bool = False) -> tuple[bool, str]:
    """Execute a shell command. Returns (success, output)."""
    try:
        # Resolve command path (vital for .cmd/.bat files on Windows)
        if cmd:
            resolved = shutil.which(cmd[0])
            if resolved:
                cmd = [resolved] + cmd[1:]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        combined = (result.stdout + result.stderr).strip()
        return result.returncode == 0, combined
    except FileNotFoundError as e:
        return False, f"Command not found: {e}"
    except subprocess.TimeoutExpired:
        return False, "Timed out after 60 seconds"
    except Exception as e:
        return False, str(e)


def uninstall_tool(
    tool: CLITool,
    clean_configs: bool = True,
    log: Callable[[str], None] | None = None,
) -> dict:
    """
    Uninstall a single tool.
    Returns a result dict: {success, tool, output, cleaned_paths}
    """
    result = {
        "success": False,
        "tool": tool,
        "output": "",
        "cleaned_paths": [],
        "errors": [],
    }

    def emit(msg: str):
        if log:
            log(msg)

    # ── Step 1: Run uninstall command ──────────────────────────────────────
    if tool.uninstall_cmd:
        emit(f"  → Running: {' '.join(tool.uninstall_cmd)}")
        ok, out = _run_cmd(tool.uninstall_cmd)
        result["output"] = out
        if ok:
            emit(f"  ✓ Uninstalled {tool.name}")
            result["success"] = True
        else:
            emit(f"  ✗ Uninstall command failed: {out}")
            result["errors"].append(out)
            # For 'go' tools (rm -f), check if binary is gone anyway
            if tool.source == "go":
                if tool.binary_path and not Path(tool.binary_path).exists():
                    result["success"] = True
            else:
                result["success"] = False
    else:
        # No uninstall command — try removing the binary directly
        if tool.binary_path and Path(tool.binary_path).exists():
            try:
                os.remove(tool.binary_path)
                result["success"] = True
                emit(f"  ✓ Removed binary: {tool.binary_path}")
            except PermissionError:
                msg = f"Permission denied removing {tool.binary_path}"
                result["errors"].append(msg)
                emit(f"  ✗ {msg}")
        else:
            result["success"] = True  # already gone

    # ── Step 2: Clean up config/cache paths ───────────────────────────────
    if clean_configs and tool.config_paths:
        for path_str in tool.config_paths:
            path = Path(path_str)
            if not path.exists():
                continue
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                result["cleaned_paths"].append(path_str)
                emit(f"  🗑  Removed config: {path_str}")
            except Exception as e:
                msg = f"Could not remove {path_str}: {e}"
                result["errors"].append(msg)
                emit(f"  ⚠  {msg}")

    return result


def uninstall_many(
    tools: list[CLITool],
    clean_configs: bool = True,
    log: Callable[[str], None] | None = None,
) -> list[dict]:
    """Uninstall multiple tools in sequence."""
    results = []
    for tool in tools:
        r = uninstall_tool(tool, clean_configs=clean_configs, log=log)
        results.append(r)
    return results
