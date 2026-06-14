"""
clenv - CLI Environment Manager
Main TUI entry point.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Optional

from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.spinner import Spinner
from rich.style import Style
from rich.table import Table
from rich.text import Text

import questionary
from questionary import Style as QStyle

from .scanner import CLITool, SCANNERS, scan_all
from .uninstaller import uninstall_many
from .self_uninstall import self_uninstall

console = Console()

# ─── Theme ────────────────────────────────────────────────────────────────────

BRAND   = "bold cyan"
DANGER  = "bold red"
SUCCESS = "bold green"
WARN    = "yellow"
DIM     = "dim"
ACCENT  = "bold magenta"

Q_STYLE = QStyle([
    ("qmark",         "fg:#00d7ff bold"),
    ("question",      "fg:#ffffff bold"),
    ("answer",        "fg:#00d7ff bold"),
    ("pointer",       "fg:#ff5fd7 bold"),
    ("highlighted",   "fg:#ffffff bg:#333366 bold"),
    ("selected",      "fg:#aaffaa"),
    ("separator",     "fg:#444444"),
    ("instruction",   "fg:#888888"),
    ("text",          "fg:#cccccc"),
    ("disabled",      "fg:#555555 italic"),
])


# ─── Banner ───────────────────────────────────────────────────────────────────

BANNER = r"""
  ██████╗██╗     ███████╗███╗   ██╗██╗   ██╗
 ██╔════╝██║     ██╔════╝████╗  ██║██║   ██║
 ██║     ██║     █████╗  ██╔██╗ ██║██║   ██║
 ██║     ██║     ██╔══╝  ██║╚██╗██║╚██╗ ██╔╝
 ╚██████╗███████╗███████╗██║ ╚████║ ╚████╔╝
  ╚═════╝╚══════╝╚══════╝╚═╝  ╚═══╝  ╚═══╝
"""

TAGLINE = "Your CLI junk drawer, finally cleaned up."


def print_banner():
    console.print(Text(BANNER, style=BRAND), justify="center")
    console.print(Text(TAGLINE, style=DIM), justify="center")
    console.print()


# ─── Scanning UI ──────────────────────────────────────────────────────────────

def run_scan() -> list[CLITool]:
    tools: list[CLITool] = []
    current_label = [""]

    def progress(label: str):
        current_label[0] = label

    with Live(console=console, refresh_per_second=8) as live:
        import threading
        done = threading.Event()
        error: list[Exception] = []

        def _worker():
            try:
                nonlocal tools
                tools = scan_all(progress_cb=progress)
            except Exception as e:
                error.append(e)
            finally:
                done.set()

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

        while not done.is_set():
            spinner = Spinner("dots", text=f" Scanning [bold cyan]{current_label[0]}[/]…")
            live.update(Panel(spinner, title="[bold]clenv[/] · Scanning", border_style="cyan"))
            time.sleep(0.1)

        if error:
            console.print(f"[{DANGER}]Scan error: {error[0]}[/]")
            sys.exit(1)

    return tools


# ─── Tool Table ───────────────────────────────────────────────────────────────

SOURCE_COLORS = {
    "brew":   "green",
    "npm":    "red",
    "pip":    "yellow",
    "pipx":   "yellow",
    "cargo":  "orange3",
    "gem":    "magenta",
    "go":     "cyan",
    "apt":    "blue",
    "dnf":    "blue",
    "system": "dim",
    "binary": "dim",
}


def build_table(tools: list[CLITool], selected: set[str]) -> Table:
    tbl = Table(
        box=box.ROUNDED,
        border_style="cyan",
        header_style=f"{BRAND}",
        show_lines=False,
        expand=True,
    )
    tbl.add_column("#",        width=4,  style=DIM, justify="right")
    tbl.add_column("",         width=3)   # checkbox
    tbl.add_column("Tool",     min_width=18, style="bold white")
    tbl.add_column("Source",   width=10)
    tbl.add_column("Version",  width=12, style=DIM)
    tbl.add_column("Used",     width=18)
    tbl.add_column("Binary",   min_width=20, style=DIM)

    for i, tool in enumerate(tools, 1):
        check = "[bold green]✔[/]" if tool.name in selected else "[ ]"
        src_color = SOURCE_COLORS.get(tool.source, "white")
        source_cell = f"[{src_color}]{tool.source_icon} {tool.source}[/]"
        used_style = "green" if tool.last_used == "seen in history" else "dim red"
        used_cell = f"[{used_style}]{tool.last_used or '—'}[/]"
        tbl.add_row(
            str(i),
            check,
            tool.name,
            source_cell,
            tool.version[:12],
            used_cell,
            tool.binary_path or "—",
        )
    return tbl


# ─── Interactive Selector ──────────────────────────────────────────────────────

def select_tools(tools: list[CLITool]) -> list[CLITool]:
    """Let user multi-select tools to uninstall via questionary checkbox."""
    console.print()
    console.print(Rule(f"[{BRAND}]Select tools to remove[/]"))
    console.print(
        Text(
            "  Space = toggle  |  A = all  |  I = invert  |  Enter = confirm\n",
            style=DIM,
        )
    )

    choices = []
    for tool in tools:
        src_badge = f"[{tool.source}]"
        label = f"{tool.name:<30} {src_badge:<12} v{tool.version:<14} {tool.last_used or ''}"
        choices.append(
            questionary.Choice(title=label, value=tool.name, checked=False)
        )

    selected_names: list[str] = questionary.checkbox(
        "Which CLI tools do you want to uninstall?",
        choices=choices,
        style=Q_STYLE,
    ).ask()

    if selected_names is None:
        return []  # Ctrl+C

    name_set = set(selected_names)
    return [t for t in tools if t.name in name_set]


# ─── Summary Panel ─────────────────────────────────────────────────────────────

def show_summary(tools: list[CLITool]):
    by_source: dict[str, int] = {}
    for t in tools:
        by_source[t.source] = by_source.get(t.source, 0) + 1

    grid = Table.grid(expand=True, padding=(0, 2))
    grid.add_column(justify="left")
    grid.add_column(justify="left")

    grid.add_row(
        Text(f"  Total CLI tools found:", style=DIM),
        Text(str(len(tools)), style=BRAND),
    )
    for src, count in sorted(by_source.items(), key=lambda x: -x[1]):
        icon = next((t.source_icon for t in tools if t.source == src), "")
        grid.add_row(
            Text(f"    {icon} {src}", style=DIM),
            Text(str(count), style="white"),
        )

    console.print(Panel(grid, title=f"[{BRAND}]Scan Complete[/]", border_style="cyan"))
    console.print()


# ─── Uninstall Confirmation + Execution ───────────────────────────────────────

def confirm_and_uninstall(to_remove: list[CLITool]) -> bool:
    if not to_remove:
        return False

    console.print()
    console.print(Rule(f"[{DANGER}]Confirm Removal[/]"))
    console.print()

    tbl = Table(box=box.SIMPLE_HEAVY, show_header=False, padding=(0, 2))
    tbl.add_column(style="bold red")
    tbl.add_column(style=DIM)
    for t in to_remove:
        tbl.add_row(f"✗  {t.name}", f"via {t.source}")
    console.print(tbl)

    clean = Confirm.ask(
        "\n  [yellow]Also remove leftover config/cache files?[/]",
        default=True,
    )

    console.print()
    go = Confirm.ask(
        f"  [{DANGER}]Remove {len(to_remove)} tool(s)? This cannot be undone.[/]",
        default=False,
    )
    if not go:
        console.print(f"\n  [{WARN}]Cancelled.[/]\n")
        return False

    console.print()
    log_lines: list[str] = []

    def log(msg: str):
        log_lines.append(msg)
        console.print(msg)

    results = uninstall_many(to_remove, clean_configs=clean, log=log)

    console.print()
    ok = sum(1 for r in results if r["success"])
    fail = len(results) - ok
    console.print(Panel(
        f"[{SUCCESS}]✔ {ok} removed[/]   [{DANGER if fail else DIM}]✗ {fail} failed[/]",
        title=f"[{BRAND}]Done[/]",
        border_style="cyan",
    ))
    return True


# ─── Self-Remove Flow ──────────────────────────────────────────────────────────

def offer_self_remove():
    console.print()
    console.print(Rule(f"[{DIM}]clenv self-removal[/]"))
    console.print(
        Text(
            "\n  clenv will now remove itself from your system — \n"
            "  it would be hypocritical not to offer this.\n",
            style=DIM,
        )
    )
    go = Confirm.ask(
        f"  [{WARN}]Uninstall clenv too?[/]",
        default=False,
    )
    if not go:
        return

    console.print()

    def log(msg: str):
        console.print(msg)

    ok = self_uninstall(log=log)
    console.print()
    if ok:
        console.print(f"  [{SUCCESS}]clenv has been removed. Goodbye! 👋[/]")
    else:
        console.print(f"  [{WARN}]Couldn't fully remove clenv (may need sudo). Binary: removed manually if needed.[/]")


# ─── Goodbye Screen ────────────────────────────────────────────────────────────

GOODBYE = """
  ╭──────────────────────────────────────────────────╮
  │                                                  │
  │   Thanks for using  c l e n v  !                │
  │                                                  │
  │   Your terminal is a little lighter now.         │
  │   Go ship something great. 🚀                    │
  │                                                  │
  │   ★  github.com/AnasNafees1802/clenv            │
  │                                                  │
  ╰──────────────────────────────────────────────────╯
"""


def show_goodbye():
    console.print()
    console.print(Text(GOODBYE, style="bold cyan"), justify="center")
    console.print()


# ─── Main Menu Loop ────────────────────────────────────────────────────────────

def main_menu(tools: list[CLITool]):
    while True:
        console.print()
        action = questionary.select(
            "What would you like to do?",
            choices=[
                questionary.Choice("🗑  Uninstall selected CLI tools", value="uninstall"),
                questionary.Choice("📋  View all detected tools (table)", value="view"),
                questionary.Choice("🔄  Re-scan",                         value="rescan"),
                questionary.Choice("🚪  Exit",                             value="exit"),
            ],
            style=Q_STYLE,
        ).ask()

        if action is None or action == "exit":
            break

        elif action == "view":
            console.print()
            selected: set[str] = set()
            console.print(build_table(tools, selected))
            console.print(f"\n  [{DIM}]{len(tools)} tools detected[/]\n")

        elif action == "rescan":
            console.print(f"\n  [{BRAND}]Re-scanning…[/]\n")
            tools = run_scan()
            show_summary(tools)

        elif action == "uninstall":
            to_remove = select_tools(tools)
            if not to_remove:
                console.print(f"\n  [{DIM}]Nothing selected.[/]")
                continue
            confirm_and_uninstall(to_remove)
            # Refresh tool list after removal
            tools = [t for t in tools if t not in to_remove]

    # ── Exit sequence ──────────────────────────────────────────────────────
    offer_self_remove()
    show_goodbye()


# ─── Entry Point ───────────────────────────────────────────────────────────────

def run():
    try:
        console.clear()
        print_banner()

        console.print(
            Panel(
                Text(
                    "clenv scans your system for CLI tools installed via brew, npm, pip,\n"
                    "pipx, cargo, gem, go, apt and more — then lets you cleanly remove them.",
                    justify="center",
                    style=DIM,
                ),
                border_style="cyan",
            )
        )
        console.print()

        tools = run_scan()
        show_summary(tools)

        if not tools:
            console.print(f"  [{WARN}]No CLI tools found. Your system is already clean![/]\n")
            show_goodbye()
            return

        main_menu(tools)

    except KeyboardInterrupt:
        console.print(f"\n\n  [{DIM}]Interrupted. Exiting clenv.[/]\n")
        sys.exit(0)


if __name__ == "__main__":
    run()
