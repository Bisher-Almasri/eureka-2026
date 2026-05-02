"""
monitor.py — list running processes + (best-effort) foreground app.
 
Run:
    pip install psutil
    python monitor.py
 
Optional flags:
    python monitor.py --top 20        # show top 20 by CPU instead of 30
    python monitor.py --watch         # refresh every 2 seconds
    python monitor.py --filter chrome # only show processes matching 'chrome'
"""
 
from __future__ import annotations
 
import argparse
import os
import subprocess
import sys
import time
from typing import Optional

import re
from dataclasses import dataclass
from typing import Literal
 
import psutil
 
Category = Literal["productive", "neutral", "distraction", "unknown"]


SHORT_KEYWORDS = {"x", "vim", "git", "node", "make", "code", "word",
                  "ea desktop"}

DISTRACTION = [
    # Social / chat
    "discord", "slack", "telegram", "whatsapp", "imessage",
    "signal", "messenger", "wechat",
    # Video / streaming
    "netflix", "spotify", "music", "vlc", "iina", "quicktime player",
    "youtube",
    # Games & launchers
    "steam", "epicgameslauncher", "battle.net", "riot", "leagueclient",
    "valorant", "minecraft", "roblox", "ea desktop", "gog galaxy",
    # Social media native apps
    "twitter", "instagram", "tiktok", "reddit", "facebook",
    # Generic entertainment
    "twitch", "obs",
]

PRODUCTIVE = [
    # Editors / IDEs
    "code", "vscode", "cursor", "pycharm", "intellij", "clion", "rustrover",
    "goland", "webstorm", "phpstorm", "rider", "datagrip", "android studio",
    "xcode", "sublime text", "atom", "neovim", "nvim", "vim", "emacs",
    "zed", "helix",
    # Terminals / shells
    "terminal", "iterm", "iterm2", "wezterm", "alacritty", "kitty",
    "warp", "hyper", "tabby",
    # Engineering tooling
    "altium", "kicad", "ltspice", "vivado", "quartus", "matlab", "simulink",
    "fusion 360", "fusion360", "solidworks", "autocad", "ansys",
    # Writing / docs / research
    "obsidian", "notion", "logseq", "zotero", "mendeley", "papers",
    "scrivener", "ulysses", "typora", "marktext",
    # Office
    "microsoft word", "microsoft excel", "powerpoint", "keynote",
    "libreoffice", "soffice",
    # Dev tools
    "docker", "postman", "insomnia", "tableplus", "dbeaver", "tableau",
    "rstudio", "jupyter", "anaconda", "github desktop", "sourcetree",
    "git", "gitkraken",
    # Build / compile
    "cargo", "rustc", "gcc", "clang", "make", "cmake", "ninja",
    "javac", "node", "npm", "pnpm", "yarn", "tsc", "webpack",
]

NEUTRAL = [
    # Browsers
    "chrome", "google chrome", "safari", "firefox", "arc", "brave",
    "edge", "microsoft edge", "vivaldi", "opera",
    # Email / calendar
    "mail", "outlook", "thunderbird", "spark", "airmail",
    "calendar", "fantastical",
    # Video calls
    "zoom", "teams", "microsoft teams", "google meet", "webex", "facetime",
    # System / utilities
    "finder", "explorer", "system preferences", "system settings",
    "activity monitor", "task manager",
    # File sync
    "dropbox", "onedrive", "google drive", "icloud",
    # Password / security
    "1password", "bitwarden", "lastpass",
    # PDF / image viewers
    "preview", "acrobat", "adobe acrobat", "skim",
]


 
# ── Foreground window detection ─────────────────────────────────────────────
# psutil doesn't know about UI focus. We shell out per-platform for that.
 
def get_foreground_app() -> Optional[str]:
    """Return the name of the frontmost/focused application, or None."""
    try:
        if sys.platform == "darwin":
            # AppleScript: ask System Events which process is frontmost.
            result = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to '
                 'get name of first application process whose frontmost is true'],
                capture_output=True, text=True, timeout=2,
            )
            return result.stdout.strip() or None
 
        elif sys.platform == "win32":
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            return buf.value or None
 
        else:  # linux, bsd, etc.
            # Try xdotool first; fall back to wmctrl.
            for cmd in (["xdotool", "getactivewindow", "getwindowname"],
                        ["sh", "-c", "wmctrl -l | head -n 1"]):
                try:
                    r = subprocess.run(cmd, capture_output=True,
                                       text=True, timeout=2)
                    if r.returncode == 0 and r.stdout.strip():
                        return r.stdout.strip()
                except FileNotFoundError:
                    continue
            return None
    except Exception:
        return None
 
 
# ── Process listing ─────────────────────────────────────────────────────────
 
def collect_processes(name_filter: str | None = None) -> list[dict]:
    """Snapshot all processes with cpu%, mem%, name, pid."""
    # First pass: prime cpu_percent (returns 0.0 on first call per process).
    procs = list(psutil.process_iter(["pid", "name"]))
    for p in procs:
        try:
            p.cpu_percent(None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    time.sleep(0.3)  # short window so cpu_percent has something to compare
 
    rows: list[dict] = []
    for p in procs:
        try:
            info = p.as_dict(attrs=["pid", "name", "cpu_percent",
                                    "memory_percent", "username"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
 
        name = info.get("name") or "?"
        if name_filter and name_filter.lower() not in name.lower():
            continue
 
        rows.append({
            "pid": info["pid"],
            "name": name,
            "cpu": info["cpu_percent"] or 0.0,
            "mem": info["memory_percent"] or 0.0,
            "user": info.get("username") or "",
        })
 
    rows.sort(key=lambda r: r["cpu"], reverse=True)
    return rows
 
 
# ── Rendering ───────────────────────────────────────────────────────────────
 
def print_report(top: int, name_filter: str | None) -> None:
    fg = get_foreground_app()
    rows = collect_processes(name_filter)
 
    print()
    print("─" * 78)
    print(f"  Foreground: {fg or '(unknown — no permission or unsupported OS)'}")
    print(f"  Total processes: {len(rows)}"
          + (f"   filter: {name_filter!r}" if name_filter else ""))
    print("─" * 78)
    print(f"  {'PID':>7}  {'CPU%':>6}  {'MEM%':>6}  NAME")
    print("─" * 78)
 
    for r in rows[:top]:
        rClassified = classify(r['name'])
    
        print(f"  {r['pid']:>7}  {r['cpu']:>6.1f}  {r['mem']:>6.1f}  {r['name']} {colored_badge(rClassified.category)}")
 
    if len(rows) > top:
        print(f"  … and {len(rows) - top} more (use --top N to show more)")
    print()
 
 
def clear_screen() -> None:
    os.system("cls" if sys.platform == "win32" else "clear")


@dataclass
class Classification:
    category: Category
    matched_rule: str | None


def _matches(name_lower: str, rule: str) -> bool:
    """Check if rule matches name. Use word boundaries for short rules."""
    if len(rule) <= 4 or rule in SHORT_KEYWORDS:
        # \b word boundary. re.escape handles dots, hyphens, etc.
        pattern = r"\b" + re.escape(rule) + r"\b"
        return re.search(pattern, name_lower) is not None
    return rule in name_lower


def classify(name: str) -> Classification:
    """Categorize a process by its name."""
    if not name:
        return Classification("unknown", None)

    n = name.lower()

    for rule in DISTRACTION:
        if _matches(n, rule):
            return Classification("distraction", rule)

    for rule in PRODUCTIVE:
        if _matches(n, rule):
            return Classification("productive", rule)

    for rule in NEUTRAL:
        if _matches(n, rule):
            return Classification("neutral", rule)

    return Classification("unknown", None)

ANSI = {
    "productive":  "\033[32m",   # green
    "neutral":     "\033[36m",   # cyan
    "distraction": "\033[31m",   # red
    "unknown":     "\033[90m",   # bright black / gray
    "reset":       "\033[0m",
    "bold":        "\033[1m",
}

BADGE = {
    "productive":  "PROD",
    "neutral":     "NEUT",
    "distraction": "DIST",
    "unknown":     "  ? ",
}


def colored_badge(category: Category) -> str:
    return f"{ANSI[category]}{BADGE[category]}{ANSI['reset']}"
 
 
# ── Entry ───────────────────────────────────────────────────────────────────
 
def main() -> None:
    ap = argparse.ArgumentParser(description="List running processes.")
    ap.add_argument("--top", type=int, default=30,
                    help="Show top N processes by CPU (default 30).")
    ap.add_argument("--watch", action="store_true",
                    help="Refresh every 2 seconds until Ctrl+C.")
    ap.add_argument("--filter", default=None,
                    help="Only show processes whose name contains this string.")
    args = ap.parse_args()
 
    if not args.watch:
        print_report(args.top, args.filter)
        return
 
    try:
        while True:
            clear_screen()
            print_report(args.top, args.filter)
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nstopped.")


 
 
if __name__ == "__main__":
    main()