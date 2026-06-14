"""
clenv - Self Uninstaller
Removes clenv itself cleanly from the system.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def find_self() -> dict:
    """Detect how clenv was installed and where it lives."""
    info = {
        "method": "unknown",
        "binary": shutil.which("clenv") or "",
        "package": "clenv",
        "extra_paths": [],
    }

    binary = info["binary"]
    if not binary:
        binary = sys.argv[0]
        info["binary"] = binary

    # Detect via pipx
    pipx_home = Path(os.environ.get("PIPX_HOME", Path.home() / ".local" / "pipx"))
    if (pipx_home / "venvs" / "clenv").exists():
        info["method"] = "pipx"
        return info

    # Detect via pip
    rc = subprocess.run(
        [sys.executable, "-m", "pip", "show", "clenv"],
        capture_output=True, text=True
    ).returncode
    if rc == 0:
        info["method"] = "pip"
        return info

    # Detect via brew
    brew = shutil.which("brew")
    if brew:
        rc = subprocess.run(
            [brew, "list", "clenv"], capture_output=True
        ).returncode
        if rc == 0:
            info["method"] = "brew"
            return info

    # Detect as raw script / git clone run
    script = Path(sys.argv[0]).resolve()
    if script.exists():
        info["method"] = "script"
        info["binary"] = str(script)
        # also check symlink in /usr/local/bin etc.
        for d in ["/usr/local/bin", str(Path.home() / ".local" / "bin")]:
            sym = Path(d) / "clenv"
            if sym.exists():
                info["extra_paths"].append(str(sym))

    return info


def self_uninstall(log=None) -> bool:
    """Remove clenv from the system. Returns True on success."""

    def emit(msg):
        if log:
            log(msg)

    info = find_self()
    method = info["method"]
    success = False

    emit(f"\n  Detected install method: [{method}]")

    if os.name == "nt" and method in ("pip", "pipx"):
        emit("  ℹ  Windows detected: uninstallation will complete in the background immediately after exit.")
        if method == "pipx":
            cmd = ["pipx", "uninstall", "clenv"]
            resolved = shutil.which(cmd[0])
            if resolved:
                cmd[0] = resolved
        else:
            cmd = [sys.executable, "-m", "pip", "uninstall", "-y", "clenv"]

        # Detached runner script that waits for parent process to exit
        detached_script = (
            "import sys, os, time, subprocess; "
            "pid = int(sys.argv[1]); "
            "cmd = sys.argv[2:]; "
            "while True: "
            "    try: "
            "        os.kill(pid, 0); "
            "        time.sleep(0.2); "
            "    except OSError: "
            "        break; "
            "subprocess.run(cmd)"
        )

        try:
            DETACHED_PROCESS = 0x00000008
            subprocess.Popen(
                [sys.executable, "-c", detached_script, str(os.getpid())] + cmd,
                creationflags=DETACHED_PROCESS,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                close_fds=True
            )
            success = True
        except Exception as e:
            emit(f"  ✗ Failed to launch background uninstaller: {e}")
            success = False

    elif method == "pipx":
        cmd = ["pipx", "uninstall", "clenv"]
        resolved = shutil.which(cmd[0])
        if resolved:
            cmd[0] = resolved
        r = subprocess.run(cmd, capture_output=True, text=True)
        success = r.returncode == 0
        emit("  " + (r.stdout + r.stderr).strip())

    elif method == "pip":
        r = subprocess.run(
            [sys.executable, "-m", "pip", "uninstall", "-y", "clenv"],
            capture_output=True, text=True
        )
        success = r.returncode == 0
        emit("  " + (r.stdout + r.stderr).strip())

    elif method == "brew":
        cmd = ["brew", "uninstall", "clenv"]
        resolved = shutil.which(cmd[0])
        if resolved:
            cmd[0] = resolved
        r = subprocess.run(cmd, capture_output=True, text=True)
        success = r.returncode == 0
        emit("  " + (r.stdout + r.stderr).strip())


    elif method == "script":
        binary = Path(info["binary"])
        try:
            if binary.exists():
                binary.unlink()
            success = True
            emit(f"  ✓ Removed {binary}")
        except Exception as e:
            emit(f"  ✗ {e}")

    # Remove extra symlinks / wrappers
    for extra in info.get("extra_paths", []):
        p = Path(extra)
        if p.exists() or p.is_symlink():
            try:
                p.unlink()
                emit(f"  ✓ Removed {extra}")
            except Exception as e:
                emit(f"  ⚠  {e}")

    # Clean leftover config
    config_dirs = [
        Path.home() / ".config" / "clenv",
        Path.home() / ".clenv",
        Path.home() / ".cache" / "clenv",
    ]
    for d in config_dirs:
        if d.exists():
            try:
                shutil.rmtree(d)
                emit(f"  🗑  Removed {d}")
            except Exception:
                pass

    return success
