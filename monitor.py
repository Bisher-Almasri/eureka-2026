"""
monitor.py — list running processes and run a focus guard.

Run:
    uv run python monitor.py

Optional flags:
    uv run python monitor.py --top 20
    uv run python monitor.py --watch
    uv run python monitor.py --filter chrome
    uv run python monitor.py --focus
    uv run python monitor.py --focus --popup
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Literal, Optional

import psutil

from classify import ANSI, Classification, classify, colored_badge

Category = Literal["productive", "neutral", "distraction", "unknown"]


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


# ── Browser tab detection ───────────────────────────────────────────────────

@dataclass
class BrowserTab:
    browser: str
    title: str
    url: str
    active: bool = False

    @property
    def label(self) -> str:
        if self.url:
            return f"{self.title} {self.url}".strip()
        return self.title


CHROMIUM_BROWSERS = (
    "Google Chrome",
    "Brave Browser",
    "Microsoft Edge",
    "Arc",
    "Vivaldi",
    "Opera",
)


def _run_osascript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=4,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _applescript_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _app_is_running(app_name: str) -> bool:
    if sys.platform != "darwin":
        return False

    script = (
        'tell application "System Events" to '
        f'(name of processes) contains "{app_name}"'
    )
    return _run_osascript(script).lower() == "true"


def _split_tab_rows(output: str, browser: str, active_index: int | None = None) -> list[BrowserTab]:
    tabs: list[BrowserTab] = []
    for index, line in enumerate(output.splitlines(), start=1):
        parts = line.split("\t", 1)
        title = parts[0].strip() if parts else ""
        url = parts[1].strip() if len(parts) > 1 else ""
        if title or url:
            tabs.append(
                BrowserTab(
                    browser=browser,
                    title=title or "(untitled)",
                    url=url,
                    active=active_index == index,
                )
            )
    return tabs


def collect_browser_tabs() -> list[BrowserTab]:
    """Best-effort browser tab snapshot. Currently supports macOS browsers."""
    if sys.platform != "darwin":
        return []

    tabs: list[BrowserTab] = []

    if _app_is_running("Safari"):
        script = """
tell application "Safari"
    set tabRows to {}
    repeat with w in windows
        repeat with t in tabs of w
            set end of tabRows to (name of t) & tab & (URL of t)
        end repeat
    end repeat
    set AppleScript's text item delimiters to linefeed
    return tabRows as text
end tell
""".strip()
        tabs.extend(_split_tab_rows(_run_osascript(script), "Safari"))

    for browser in CHROMIUM_BROWSERS:
        if not _app_is_running(browser):
            continue
        script = f"""
tell application "{browser}"
    set tabRows to {{}}
    repeat with w in windows
        repeat with t in tabs of w
            set end of tabRows to (title of t) & tab & (URL of t)
        end repeat
    end repeat
    set AppleScript's text item delimiters to linefeed
    return tabRows as text
end tell
""".strip()
        active_script = f'tell application "{browser}" to return active tab index of front window'
        active_index_text = _run_osascript(active_script)
        active_index = int(active_index_text) if active_index_text.isdigit() else None
        tabs.extend(_split_tab_rows(_run_osascript(script), browser, active_index))

    return tabs


# ── Focus guard ─────────────────────────────────────────────────────────────

@dataclass
class Distraction:
    source: str
    name: str
    rule: str | None = None
    active: bool = False

    def describe(self) -> str:
        active = "active " if self.active else ""
        rule = f" via {self.rule!r}" if self.rule else ""
        return f"{active}{self.source}: {self.name}{rule}"


@dataclass
class FocusSnapshot:
    foreground: str | None
    foreground_classification: Classification
    distractions: list[Distraction]

    @property
    def is_distracted(self) -> bool:
        return bool(self.distractions)

    @property
    def is_working(self) -> bool:
        return (
            not self.distractions
            and self.foreground_classification.category == "productive"
        )


def inspect_focus_state(check_tabs: bool = True) -> FocusSnapshot:
    foreground = get_foreground_app()
    foreground_classification = classify(foreground or "")
    distractions: list[Distraction] = []

    for row in collect_processes():
        classification = classify(row["name"])
        if classification.category == "distraction":
            distractions.append(
                Distraction(
                    source="process",
                    name=f"{row['name']} (pid {row['pid']})",
                    rule=classification.matched_rule,
                    active=foreground and row["name"].lower() == foreground.lower(),
                )
            )

    if check_tabs:
        for tab in collect_browser_tabs():
            classification = classify(tab.label)
            if classification.category == "distraction":
                distractions.append(
                    Distraction(
                        source=f"{tab.browser} tab",
                        name=tab.title,
                        rule=classification.matched_rule,
                        active=tab.active,
                    )
                )

    return FocusSnapshot(
        foreground=foreground,
        foreground_classification=foreground_classification,
        distractions=distractions,
    )


def show_focus_popup(message: str, timeout_seconds: int) -> bool:
    """Return True when the popup was ignored instead of acknowledged."""
    if sys.platform != "darwin":
        return False

    script = "\n".join(
        [
            "display dialog "
            + _applescript_quote(message)
            + " with title "
            + _applescript_quote("Eureka focus guard")
            + " buttons {"
            + _applescript_quote("Back to work")
            + "} default button "
            + _applescript_quote("Back to work")
            + " giving up after "
            + str(timeout_seconds),
            "return result as text",
        ]
    )

    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout_seconds + 2,
        )
    except subprocess.TimeoutExpired:
        return True

    if result.returncode != 0:
        return True
    return "gave up:true" in result.stdout.replace(" ", "").lower()


def notify(
    message: str,
    use_notification: bool,
    use_popup: bool,
    popup_timeout_seconds: int,
) -> bool:
    """Notify the user. Return True if an interactive popup was ignored."""
    print("\a", end="", flush=True)
    print(f"{ANSI['distraction']}{ANSI['bold']}FOCUS:{ANSI['reset']} {message}")

    if use_popup:
        ignored = show_focus_popup(message, popup_timeout_seconds)
        if ignored:
            print(
                f"{ANSI['distraction']}Popup ignored; hydra mode will escalate.{ANSI['reset']}"
            )
        return ignored

    if use_notification and sys.platform == "darwin":
        subprocess.run(
            [
                "osascript",
                "-e",
                "display notification "
                + _applescript_quote(message)
                + " with title "
                + _applescript_quote("Eureka focus guard"),
            ],
            capture_output=True,
            text=True,
            timeout=2,
        )
    return False


def print_focus_summary(snapshot: FocusSnapshot, max_items: int = 8) -> None:
    fg = snapshot.foreground or "(unknown)"
    fg_badge = colored_badge(snapshot.foreground_classification.category)
    print(f"Foreground: {fg} {fg_badge}")

    if snapshot.is_working:
        print(f"{ANSI['productive']}Working. Nice, keep going.{ANSI['reset']}")
        return

    if not snapshot.distractions:
        print("No known distractions open, but foreground is not classified as productive.")
        return

    print(f"{ANSI['distraction']}Distractions detected:{ANSI['reset']}")
    for item in snapshot.distractions[:max_items]:
        print(f"  - {item.describe()}")
    remaining = len(snapshot.distractions) - max_items
    if remaining > 0:
        print(f"  ... and {remaining} more")


def run_focus_guard(
    interval_seconds: float,
    annoy_seconds: float,
    check_tabs: bool,
    use_notification: bool,
    use_popup: bool,
    popup_timeout_seconds: int,
    max_popups: int,
) -> None:
    print("Focus guard started. Ctrl+C stops it.")
    next_annoy_at = 0.0
    was_distracted = False
    popup_count = 1

    try:
        while True:
            snapshot = inspect_focus_state(check_tabs=check_tabs)
            now = time.monotonic()

            if snapshot.is_distracted:
                if now >= next_annoy_at:
                    top_reason = snapshot.distractions[0].describe()
                    ignored_count = 0
                    for popup_index in range(popup_count):
                        prefix = ""
                        if use_popup and popup_count > 1:
                            prefix = f"[{popup_index + 1}/{popup_count}] "
                        ignored = notify(
                            f"{prefix}Back to work. {top_reason}",
                            use_notification,
                            use_popup,
                            popup_timeout_seconds,
                        )
                        if ignored:
                            ignored_count += 1

                    snapshot = inspect_focus_state(check_tabs=check_tabs)
                    still_distracted = snapshot.is_distracted
                    
                    try:
                        import urllib.request
                        req = urllib.request.Request(
                            f"http://192.168.254.98:1504/buzz?seconds={popup_count}",
                            method="POST"
                        )
                        urllib.request.urlopen(req, timeout=2)
                    except Exception:
                        pass

                    if use_popup and ignored_count and still_distracted:
                        popup_count = min(max_popups, popup_count * 2)
                        next_annoy_at = now
                    else:
                        popup_count = 1
                        next_annoy_at = now + annoy_seconds
                    print_focus_summary(snapshot)
                was_distracted = True
            else:
                if was_distracted:
                    print(f"{ANSI['productive']}Recovered. Distractions cleared.{ANSI['reset']}")
                was_distracted = False
                next_annoy_at = now
                popup_count = 1

            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print("\nstopped.")


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
        classified = classify(r["name"])

        print(f"  {r['pid']:>7}  {r['cpu']:>6.1f}  {r['mem']:>6.1f}  {r['name']} {colored_badge(classified.category)}")
 
    if len(rows) > top:
        print(f"  … and {len(rows) - top} more (use --top N to show more)")
    print()
 
 
def clear_screen() -> None:
    os.system("cls" if sys.platform == "win32" else "clear")


# ── Entry ───────────────────────────────────────────────────────────────────
 
def main() -> None:
    ap = argparse.ArgumentParser(description="List running processes.")
    ap.add_argument("--top", type=int, default=30,
                    help="Show top N processes by CPU (default 30).")
    ap.add_argument("--watch", action="store_true",
                    help="Refresh every 2 seconds until Ctrl+C.")
    ap.add_argument("--filter", default=None,
                    help="Only show processes whose name contains this string.")
    ap.add_argument("--focus", action="store_true",
                    help="Annoy you while distracting processes or browser tabs are open.")
    ap.add_argument("--interval", type=float, default=5.0,
                    help="Seconds between focus checks (default 5).")
    ap.add_argument("--annoy-every", type=float, default=15.0,
                    help="Seconds between nags while distracted (default 15).")
    ap.add_argument("--no-browser-tabs", action="store_true",
                    help="Skip browser tab inspection.")
    ap.add_argument("--notify", action="store_true",
                    help="Use desktop notifications in addition to terminal bells.")
    ap.add_argument("--popup", action="store_true",
                    help="Use macOS dialogs that can detect ignored prompts and hydra-escalate.")
    ap.add_argument("--popup-timeout", type=int, default=8,
                    help="Seconds before a popup counts as ignored (default 8).")
    ap.add_argument("--max-popups", type=int, default=8,
                    help="Maximum hydra popups per nag cycle (default 8).")
    args = ap.parse_args()

    if args.focus:
        run_focus_guard(
            interval_seconds=max(1.0, args.interval),
            annoy_seconds=max(1.0, args.annoy_every),
            check_tabs=not args.no_browser_tabs,
            use_notification=args.notify,
            use_popup=args.popup,
            popup_timeout_seconds=max(1, args.popup_timeout),
            max_popups=max(1, args.max_popups),
        )
        return
 
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
