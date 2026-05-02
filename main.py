"""
Gyft TUI — Textual port of the Gyft study app.

Two screens:
  • DashboardScreen — landing page with Create-Course card and course list
  • CourseScreen    — individual course view with sidebar TOC + content pane

Navigation:
  • Click a course on the dashboard → pushes CourseScreen
  • Click "← Back to Dashboard"      → pops back
  • ← / → arrow keys navigate sections inside a course
  • Esc also goes back

Run:
    pip install textual
    python gyft_tui.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from rich.syntax import Syntax
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, ProgressBar, Static


# ──────────────────────────────────────────────────────────────────────────────
# Data model
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class Section:
    title: str
    body: str
    code: str | None = None
    code_lang: str = "rust"
    footer: str | None = None


@dataclass
class Part:
    title: str
    sections: List[Section] = field(default_factory=list)


@dataclass
class Course:
    title: str
    parts: List[Part] = field(default_factory=list)

    @property
    def total_sections(self) -> int:
        return sum(len(p.sections) for p in self.parts)

    def flat_sections(self) -> List[tuple[int, int, Section]]:
        out: List[tuple[int, int, Section]] = []
        for pi, part in enumerate(self.parts):
            for si, sec in enumerate(part.sections):
                out.append((pi, si, sec))
        return out


RUST_COURSE = Course(
    title="Introduction to the Rust Programming Language",
    parts=[
        Part("Part 1: Getting Started with Rust", [
            Section(
                "Introduction to Rust",
                "Rust is a systems programming language focused on safety, "
                "speed, and concurrency. It achieves memory safety without "
                "garbage collection, making it suitable for performance-"
                "critical applications.\n\n"
                "This section provides an overview of Rust's core principles "
                "and benefits.",
                code='fn main() {\n    println!("Hello, world!");\n}',
                footer=(
                    "The code above is a basic Rust program that prints "
                    "'Hello, world!' to the console. The println! macro is "
                    "used for output."
                ),
            ),
            Section(
                "Setting up Your Environment",
                "Install rustup, the official Rust toolchain installer.",
                code='curl --proto "=https" --tlsv1.2 -sSf '
                     'https://sh.rustup.rs | sh',
                code_lang="bash",
            ),
            Section(
                "Variables and Data Types",
                "Variables in Rust are immutable by default. Use `mut` to "
                "make them mutable.",
                code='let x = 5;\nlet mut y = 10;\ny += 1;',
            ),
            Section(
                "Basic Operations",
                "Arithmetic, comparison, and logical operators work much "
                "like in C-family languages, but with stricter type rules.",
            ),
        ]),
        Part("Part 2: Ownership and Borrowing", [
            Section("Ownership",
                    "Every value in Rust has a single owner. When the owner "
                    "goes out of scope, the value is dropped."),
            Section("Borrowing",
                    "Borrowing lets you reference a value without taking "
                    "ownership.",
                    code='fn len(s: &String) -> usize {\n    s.len()\n}'),
            Section("Mutable References",
                    "One mutable reference OR many immutable references — "
                    "never both at the same time."),
            Section("Lifetimes",
                    "Lifetimes describe how long references are valid."),
        ]),
        Part("Part 3: Data Structures: Structs, Enums, and Vectors", [
            Section("Structs", "Structs group related fields."),
            Section("Enums", "Enums let a value be one of several variants."),
            Section("Vectors", "Vec<T> is a growable, heap-allocated array."),
        ]),
        Part("Part 4: Concurrency", [
            Section("Threads", "std::thread::spawn launches OS threads."),
            Section("Channels", "mpsc channels move values between threads."),
            Section("Async", "async/await with tokio for I/O concurrency."),
        ]),
    ],
)

COURSES = [RUST_COURSE]


# ──────────────────────────────────────────────────────────────────────────────
# Styling
# ──────────────────────────────────────────────────────────────────────────────
CSS = """
Screen { background: #0a0f1e; color: #e6ebf5; }

/* ─── Top nav ────────────────────────────────────────────────────────── */
#nav-wrap { height: 5; align: center middle; padding-top: 1; }
#nav {
    width: auto; height: 3;
    background: #0f172a; border: round #2d3a5c;
    padding: 0 3;
}
#nav-brand { color: #ffffff; text-style: bold; padding: 0 3; }
.nav-item { padding: 0 3; color: #6b7a99; }
.nav-item-active {
    padding: 0 3; color: #ffffff;
    background: #1a2540; border: round #4f3df5;
}

/* ─── Dashboard ──────────────────────────────────────────────────────── */
#dashboard-body {
    align: center top;
    width: 100%;
    height: 1fr;
}

#create-card {
    width: 70%;
    max-width: 120;
    margin: 1 0 0 0;
    padding: 2 3;
    height: auto;
    background: #0f172a; border: round #2d3a5c;
}
#create-header { height: 5; align: left middle; }
#sparkle-badge {
    width: 7; height: 3; content-align: center middle;
    background: #4f3df5; color: #ffffff; text-style: bold;
    border: round #6e5cff; margin-right: 3;
}
#create-title { text-style: bold; color: #ffffff; }
#create-sub   { color: #8a96b3; }
#create-input-row { height: 3; margin-top: 1; align: center middle; }
#prompt-input {
    background: #131b30; color: #cfd6e6;
    border: round #2d3a5c; padding: 0 2;
}
#prompt-input:focus { border: round #4f3df5; }
#generate-btn {
    margin-left: 2; min-width: 24;
    background: #4f3df5; color: #ffffff; text-style: bold;
    border: round #6e5cff;
}
#generate-btn:hover { background: #5d4cff; }

#courses-wrap {
    width: 70%;
    max-width: 120;
    margin: 2 0 0 0;
    height: 1fr;
}
#courses-title {
    text-style: bold;
    margin-bottom: 1;
    text-align: center;
    width: 100%;
}
.course-card {
    width: 100%;
    height: 3; padding: 0 3;
    background: #131b30; color: #ffffff;
    border: round #2d3a5c;
    margin-bottom: 1;
    text-align: left;
}
.course-card:hover { background: #1a2540; border: round #4f3df5; }

/* ─── Course detail ──────────────────────────────────────────────────── */
#course-header {
    margin: 1 0 0 0;
    height: auto;
    align: center top;
}
#header-row {
    height: 3;
    width: 90%;
    max-width: 160;
    align: center middle;
}
#back-btn {
    background: #131b30; color: #ffffff;
    border: round #2d3a5c; min-width: 26;
}
#back-btn:hover { border: round #4f3df5; }
#course-title {
    text-style: bold; text-align: center;
    width: 1fr; padding: 0 3;
}
#header-spacer { width: 26; }

#progress-row {
    height: 3;
    align: center middle;
    margin-top: 1;
}
#progress-label { color: #8a96b3; padding-right: 1; }
#progress-bar { width: 50; }
#progress-text { color: #cfd6e6; padding-left: 1; }

#course-body {
    margin: 1 4 1 4;
    height: 1fr;
    align: center top;
}

#sidebar {
    width: 42;
    background: #0f172a; border: round #2d3a5c;
    padding: 1 2;
    margin-right: 2;
}
#sidebar-title {
    text-style: bold;
    padding: 0 1 1 1;
    color: #ffffff;
    text-align: center;
    width: 100%;
}
.part-title {
    text-style: bold; color: #cfd6e6;
    padding: 1 1 0 1;
}
.section-item {
    width: 100%;
    height: 3; margin: 0 0 1 0; padding: 0 2;
    background: #131b30; color: #cfd6e6;
    border: round #2d3a5c;
    text-align: left;
}
.section-item:hover { background: #1a2540; }
.section-active {
    background: #4f3df5; color: #ffffff; text-style: bold;
    border: round #6e5cff;
}

#content {
    background: #0f172a;
    border: round #2d3a5c;
    padding: 2 4;
}
#section-title {
    text-style: bold;
    text-align: left;
}
#section-body  { color: #cfd6e6; margin-top: 1; }
#section-code {
    background: #131b30;
    border: round #2d3a5c;
    padding: 1 2;
    margin-top: 1;
}
#section-footer { color: #cfd6e6; margin-top: 1; }

#nav-row {
    height: 3;
    margin-top: 2;
    align: center middle;
}
.nav-btn {
    background: #131b30; color: #ffffff;
    border: round #2d3a5c;
    width: 26;
    margin: 0 1;
}
.nav-btn:hover { border: round #4f3df5; }
#quiz-btn {
    background: #4f3df5; color: #ffffff; text-style: bold;
    border: round #6e5cff;
    width: 26;
    margin: 0 1;
}
#quiz-btn:hover { background: #5d4cff; }
#nav-hint {
    text-align: center;
    color: #8a96b3;
    height: 1;
    margin-top: 1;
}

#status {
    dock: bottom; height: 1;
    background: #0f172a; color: #8a96b3; padding: 0 3;
}
"""


# ──────────────────────────────────────────────────────────────────────────────
# Shared widgets
# ──────────────────────────────────────────────────────────────────────────────

class NavBar(Static):
    def __init__(self, active: str = "DDQ Animation") -> None:
        super().__init__()
        self._active = active

    def compose(self) -> ComposeResult:
        with Container(id="nav-wrap"):
            with Horizontal(id="nav"):
                yield Static("Gyft", id="nav-brand")
                for label in ("Dashboard", "Gyfts", "DDQ Animation"):
                    cls = ("nav-item-active" if label == self._active
                           else "nav-item")
                    yield Static(label, classes=cls)


# ──────────────────────────────────────────────────────────────────────────────
# Dashboard
# ──────────────────────────────────────────────────────────────────────────────

class DashboardScreen(Screen):
    BINDINGS = [
        Binding("ctrl+n", "focus_input", "New course"),
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield NavBar(active="DDQ Animation")

        with Vertical(id="dashboard-body"):
            with Vertical(id="create-card"):
                with Horizontal(id="create-header"):
                    yield Static("✦", id="sparkle-badge")
                    with Vertical():
                        yield Static("Create New Course", id="create-title")
                        yield Static(
                            "Generate a personalized learning experience with AI",
                            id="create-sub",
                        )
                with Horizontal(id="create-input-row"):
                    yield Input(
                        placeholder=(
                            "What would you like to learn? "
                            "(e.g., 'Python for Data Science', 'React Fundamentals')"
                        ),
                        id="prompt-input",
                    )
                    yield Button("+ Generate Course", id="generate-btn")

            with VerticalScroll(id="courses-wrap"):
                yield Static("Your Courses", id="courses-title")
                for i, course in enumerate(COURSES):
                    yield Button(
                        f"  {course.title}    ·  {course.total_sections} sections",
                        id=f"course-{i}",
                        classes="course-card",
                    )

        yield Static(
            "ready · ⌃N new course · click a course to open · q quit",
            id="status",
        )
        yield Footer()

    def action_focus_input(self) -> None:
        self.query_one("#prompt-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "generate-btn":
            prompt = self.query_one("#prompt-input", Input).value.strip()
            if not prompt:
                self._set_status("Type a topic first, then hit Generate.")
                return
            self._set_status(f"Generating course: “{prompt}” … (stub)")
        elif bid.startswith("course-"):
            idx = int(bid.split("-")[1])
            self.app.push_screen(CourseScreen(COURSES[idx]))

    def _set_status(self, text: str) -> None:
        self.query_one("#status", Static).update(text)


# ──────────────────────────────────────────────────────────────────────────────
# Course detail
# ──────────────────────────────────────────────────────────────────────────────

class CourseScreen(Screen):
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("left", "prev_section", "Previous"),
        Binding("right", "next_section", "Next"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, course: Course) -> None:
        super().__init__()
        self.course = course
        self.flat = course.flat_sections()
        self.cursor = 0

    def compose(self) -> ComposeResult:
        yield NavBar(active="DDQ Animation")

        with Vertical(id="course-header"):
            with Horizontal(id="header-row"):
                yield Button("← Back to Dashboard", id="back-btn")
                yield Static(self.course.title, id="course-title")
            with Horizontal(id="progress-row"):
                yield Static("Progress:", id="progress-label")
                yield ProgressBar(
                    total=self.course.total_sections,
                    show_eta=False,
                    show_percentage=False,
                    id="progress-bar",
                )
                yield Static(
                    f"1/{self.course.total_sections}", id="progress-text"
                )

        with Horizontal(id="course-body"):
            with VerticalScroll(id="sidebar"):
                yield Static("Course Content", id="sidebar-title")
                flat_idx = 0
                for part in self.course.parts:
                    yield Static(part.title, classes="part-title")
                    for sec in part.sections:
                        cls = "section-item"
                        if flat_idx == self.cursor:
                            cls += " section-active"
                        yield Button(
                            sec.title,
                            id=f"sec-{flat_idx}",
                            classes=cls,
                        )
                        flat_idx += 1

            with VerticalScroll(id="content"):
                yield Static("", id="section-title")
                yield Static("", id="section-body")
                yield Static("", id="section-code")
                yield Static("", id="section-footer")
                with Horizontal(id="nav-row"):
                    yield Button("← Previous Section",
                                 id="prev-btn", classes="nav-btn")
                    yield Button("Quiz This Section", id="quiz-btn")
                    yield Button("Next Section →",
                                 id="next-btn", classes="nav-btn")
                yield Static("", id="nav-hint")

        yield Static("← / → navigate · Esc back · q quit", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self._render_section()

    def action_prev_section(self) -> None:
        if self.cursor > 0:
            self.cursor -= 1
            self._render_section()

    def action_next_section(self) -> None:
        if self.cursor < len(self.flat) - 1:
            self.cursor += 1
            self._render_section()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "back-btn":
            self.app.pop_screen()
        elif bid == "prev-btn":
            self.action_prev_section()
        elif bid == "next-btn":
            self.action_next_section()
        elif bid == "quiz-btn":
            sec = self.flat[self.cursor][2]
            self._set_status(f"Quiz for: {sec.title} (stub)")
        elif bid.startswith("sec-"):
            self.cursor = int(bid.split("-")[1])
            self._render_section()

    def _render_section(self) -> None:
        _, _, sec = self.flat[self.cursor]

        self.query_one("#section-title", Static).update(sec.title)
        self.query_one("#section-body", Static).update(sec.body)

        code_widget = self.query_one("#section-code", Static)
        if sec.code:
            code_widget.display = True
            code_widget.update(
                Syntax(
                    sec.code,
                    sec.code_lang,
                    theme="monokai",
                    background_color="#0a0a0d",
                    line_numbers=False,
                )
            )
        else:
            code_widget.display = False
            code_widget.update("")

        footer_widget = self.query_one("#section-footer", Static)
        if sec.footer:
            footer_widget.display = True
            footer_widget.update(sec.footer)
        else:
            footer_widget.display = False
            footer_widget.update("")

        bar = self.query_one("#progress-bar", ProgressBar)
        bar.update(progress=self.cursor + 1)
        self.query_one("#progress-text", Static).update(
            f"{self.cursor + 1}/{self.course.total_sections}"
        )
        self.query_one("#nav-hint", Static).update(
            f"Section {self.cursor + 1} of {self.course.total_sections} · "
            f"Use ← → keys to navigate"
        )

        for i in range(len(self.flat)):
            btn = self.query_one(f"#sec-{i}", Button)
            if i == self.cursor:
                btn.add_class("section-active")
            else:
                btn.remove_class("section-active")

    def _set_status(self, text: str) -> None:
        self.query_one("#status", Static).update(text)


# ──────────────────────────────────────────────────────────────────────────────
# App
# ──────────────────────────────────────────────────────────────────────────────

class GyftTUI(App):
    CSS = CSS
    TITLE = "Gyft"
    SUB_TITLE = "Personalized AI learning, in your terminal"

    def on_mount(self) -> None:
        self.push_screen(DashboardScreen())


if __name__ == "__main__":
    GyftTUI().run()
