"""
classify.py — categorize processes as productive / neutral / distraction.

Used by monitor.py. Pattern-based, case-insensitive substring matching with
word-boundary checks for short rules to avoid false positives.

Precedence: distraction > productive > neutral > unknown.

Tweak the rule lists for your own workflow — e.g. if you're a video editor,
move 'premiere' and 'finalcut' to PRODUCTIVE.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Category = Literal["productive", "neutral", "distraction", "unknown"]


# ── Rules ───────────────────────────────────────────────────────────────────
# Rules <= 4 chars or in SHORT_KEYWORDS get word-boundary matching to avoid
# matching inside unrelated process names (e.g. 'x' inside 'kworker/R-xfs').

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


# ── ANSI color helpers ──────────────────────────────────────────────────────

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