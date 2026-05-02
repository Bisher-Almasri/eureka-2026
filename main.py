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

import json
import time
from dataclasses import dataclass, field
from typing import List
from urllib import error, request
from uuid import uuid4

from rich.syntax import Syntax
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, ProgressBar, Static, TextArea

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
    challenge: dict | None = None


@dataclass
class Part:
    title: str
    sections: List[Section] = field(default_factory=list)


@dataclass
class Course:
    title: str
    parts: List[Part] = field(default_factory=list)
    is_coding: bool = True

    @property
    def total_sections(self) -> int:
        return sum(len(p.sections) for p in self.parts)

    def flat_sections(self) -> List[tuple[int, int, Section]]:
        out: List[tuple[int, int, Section]] = []
        for pi, part in enumerate(self.parts):
            for si, sec in enumerate(part.sections):
                out.append((pi, si, sec))
        return out


def challenge_for_section(section: Section) -> dict:
    if section.challenge:
        return section.challenge

    topic = section.title
    return {
        "topic": topic,
        "language": "python",
        "instructions": (
            f"Practice the idea from '{topic}' by completing `practice_answer`. "
            "Return a short string that includes one key term or idea from this section. "
            "This fallback block keeps practice available even when the generated lesson "
            "did not include custom tests."
        ),
        "starter_code": (
            "def practice_answer():\n"
            f"    # Replace this with a short answer about: {topic}\n"
            '    return ""\n'
        ),
        "tests": [
            {
                "name": "returns a non-empty string",
                "code": "answer = practice_answer()\nassert isinstance(answer, str)\nassert len(answer.strip()) >= 8",
            },
            {
                "name": "mentions a course idea",
                "code": (
                    "answer = practice_answer().lower()\n"
                    f"keywords = {json.dumps(_keywords_for_section(section))}\n"
                    "assert any(keyword in answer for keyword in keywords)"
                ),
            },
        ],
    }


def _keywords_for_section(section: Section) -> list[str]:
    words = [
        word.strip(".,:;!?()[]{}'\"`").lower()
        for word in f"{section.title} {section.body}".split()
    ]
    keywords = [
        word
        for word in words
        if len(word) >= 5
        and word not in {"section", "about", "using", "learn", "value"}
    ]
    return list(dict.fromkeys(keywords[:8])) or ["code", "program"]


CODING_KEYWORDS = {
    "api",
    "app",
    "backend",
    "bug",
    "code",
    "coding",
    "compiler",
    "css",
    "data structure",
    "debug",
    "frontend",
    "function",
    "html",
    "javascript",
    "program",
    "programming",
    "python",
    "react",
    "rust",
    "software",
    "sql",
    "variable",
    "web development",
}


def infer_is_coding(course_data: dict, prompt: str = "") -> bool:
    raw_flag = course_data.get("ic", course_data.get("is_coding"))
    if isinstance(raw_flag, bool):
        return raw_flag
    if isinstance(raw_flag, str):
        return raw_flag.strip().lower() in {"true", "yes", "1", "coding"}

    language = str(course_data.get("l") or "").lower()
    haystack = f"{prompt} {course_data.get('t', '')} {course_data.get('d', '')} {language}".lower()
    if any(keyword in haystack for keyword in CODING_KEYWORDS):
        return True

    for part_data in course_data.get("c", []):
        for sec_data in part_data.get("s", []):
            for content in sec_data.get("c", []):
                if content.get("type") == "code":
                    return True
    return False


RUST_COURSE = Course(
    title="Introduction to the Rust Programming Language",
    parts=[
        Part(
            "Part 1: Getting Started with Rust",
            [
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
                    "https://sh.rustup.rs | sh",
                    code_lang="bash",
                ),
                Section(
                    "Variables and Data Types",
                    "Variables in Rust are immutable by default. Use `mut` to "
                    "make them mutable.",
                    code="let x = 5;\nlet mut y = 10;\ny += 1;",
                    challenge={
                        "topic": "functions",
                        "language": "python",
                        "instructions": (
                            "Write a Python function named `double_number` that "
                            "returns the input value multiplied by 2."
                        ),
                        "starter_code": "def double_number(value):\n    # replace this with your code\n    pass\n",
                        "tests": [
                            {
                                "name": "doubles a positive number",
                                "code": "assert double_number(4) == 8",
                            },
                            {
                                "name": "doubles zero",
                                "code": "assert double_number(0) == 0",
                            },
                            {
                                "name": "doubles a negative number",
                                "code": "assert double_number(-3) == -6",
                            },
                        ],
                    },
                ),
                Section(
                    "Basic Operations",
                    "Arithmetic, comparison, and logical operators work much "
                    "like in C-family languages, but with stricter type rules.",
                ),
            ],
        ),
        Part(
            "Part 2: Ownership and Borrowing",
            [
                Section(
                    "Ownership",
                    "Every value in Rust has a single owner. When the owner "
                    "goes out of scope, the value is dropped.",
                ),
                Section(
                    "Borrowing",
                    "Borrowing lets you reference a value without taking " "ownership.",
                    code="fn len(s: &String) -> usize {\n    s.len()\n}",
                ),
                Section(
                    "Mutable References",
                    "One mutable reference OR many immutable references — "
                    "never both at the same time.",
                ),
                Section(
                    "Lifetimes", "Lifetimes describe how long references are valid."
                ),
            ],
        ),
        Part(
            "Part 3: Data Structures: Structs, Enums, and Vectors",
            [
                Section("Structs", "Structs group related fields."),
                Section("Enums", "Enums let a value be one of several variants."),
                Section("Vectors", "Vec<T> is a growable, heap-allocated array."),
            ],
        ),
        Part(
            "Part 4: Concurrency",
            [
                Section("Threads", "std::thread::spawn launches OS threads."),
                Section("Channels", "mpsc channels move values between threads."),
                Section("Async", "async/await with tokio for I/O concurrency."),
            ],
        ),
    ],
)

COURSES = [RUST_COURSE]


# ──────────────────────────────────────────────────────────────────────────────
# Styling
# ──────────────────────────────────────────────────────────────────────────────
CSS = """
Screen { background: $background; color: $text; }

/* ─── Top nav ────────────────────────────────────────────────────────── */
#nav-wrap { height: 5; align: center middle; padding-top: 1; }
#nav {
    width: auto; height: 3;
    background: $panel; border: round $primary;
    padding: 0 3;
}
#nav-brand { color: $text; text-style: bold; padding: 0 3; }
.nav-item { padding: 0 3; color: $text-muted; }
.nav-item-active {
    padding: 0 3; color: $text;
    background: $boost; border: round $primary;
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
    background: $panel; border: round $primary;
}
#create-header { height: 5; align: left middle; }
#sparkle-badge {
    width: 7; height: 3; content-align: center middle;
    background: $primary; color: $text; text-style: bold;
    border: round $accent; margin-right: 3;
}
#create-title { text-style: bold; color: $text; }
#create-sub   { color: $text-muted; }
#create-input-row { height: 3; margin-top: 1; }
#prompt-input {
    background: $surface; color: $text;
    border: round $primary; padding: 0 2;
    width: 1fr;
}
#prompt-input:focus { border: round $primary; }
#create-button-row { height: 3; margin-top: 1; align: center middle; }
#generate-btn {
    width: 24;
    height: 3;
    background: $primary; color: $text; text-style: bold;
    border: round $accent;
    margin-right: 1;
    padding: 0 1;
}
#generate-btn:hover { background: $accent; }
#profile-btn {
    width: 18;
    height: 3;
    background: $accent; color: $text; text-style: bold;
    border: round $primary;
    margin-right: 1;
    padding: 0 1;
}
#profile-btn:hover { background: $primary; border: round $accent; }
#debug-btn {
    width: 20;
    height: 3;
    background: $boost; color: $text;
    border: round $primary;
    padding: 0 1;
}
#debug-btn:hover { border: round $accent; }

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
    /*background: $surface; color: $text;*/
    border: round $primary;
    margin-bottom: 1;
    text-align: left;
}
.course-card:hover { border: round $accent; }

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
    border: round $primary; min-width: 26;
}
#back-btn:hover { border: round $accent; }
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
#progress-label { color: $text-muted; padding-right: 1; }
#progress-bar { width: 50; }
#progress-text { color: $text; padding-left: 1; }
#adaptive-row {
    height: 4;
    width: 90%;
    max-width: 160;
    align: center middle;
}
#skill-level {
    color: $text;
    border: round $primary;
    padding: 0 2;
    margin-right: 2;
}
#recommendation {
    color: $text;
    width: 1fr;
}

#course-body {
    margin: 1 4 1 4;
    height: 1fr;
    align: center top;
}

#sidebar {
    width: 42;
    background: $panel; border: round $primary;
    padding: 1 2;
    margin-right: 2;
}
#sidebar-title {
    text-style: bold;
    padding: 0 1 1 1;
    color: $text;
    text-align: center;
    width: 100%;
}
.part-title {
    text-style: bold; color: $text;
    padding: 1 1 0 1;
}
.section-item {
    width: 100%;
    height: 3; margin: 0 0 1 0; padding: 0 2;
    border: round $primary;
    text-align: left;
}
.section-active {
    border: round $accent;
}

#content {
    background: $panel;
    border: round $primary;
    padding: 2 4;
}
#section-title {
    text-style: bold;
    text-align: left;
}
#section-body  { color: $text; margin-top: 1; }
#section-code {
    background: $surface;
    border: round $primary;
    margin-top: 1;
}
#section-footer { color: $text; margin-top: 1; }

#nav-row {
    height: 3;
    margin-top: 2;
    align: center middle;
}
.nav-btn {
    background: $surface; color: $text;
    border: round $primary;
    width: 26;
    margin: 0 1;
}
.nav-btn:hover { border: round $accent; }
#quiz-btn {
    background: $primary; color: $text; text-style: bold;
    border: round $accent;
    width: 26;
    margin: 0 1;
}
#quiz-btn:hover { background: $accent; }
#practice-btn {
    background: $success; color: $text; text-style: bold;
    border: round $warning;
    min-width: 28;
    margin: 0 1;
}
#practice-btn:hover { background: $warning; }
#nav-hint {
    text-align: center;
    color: $text-muted;
    height: 1;
    margin-top: 1;
}

#status {
    dock: bottom; height: 1;
    background: $panel; color: $text-muted; padding: 0 3;
}

/* ─── Practice and Debug Coach ──────────────────────────────────────── */
#workspace {
    margin: 1 3;
    height: 1fr;
}
#instructions-pane, #editor-pane {
    background: $panel;
    border: round $primary;
    padding: 1 2;
    width: 1fr;
}
#instructions-pane {
    margin-right: 1;
}
#editor-pane {
    margin-left: 1;
}
#pane-title {
    text-style: bold;
    color: $text;
    height: 1;
}
#practice-instructions, #debug-response {
    color: $text;
    margin-top: 1;
}
#code-editor {
    height: 1fr;
    background: $surface;
    color: $text;
    border: round $primary;
    margin-top: 1;
}
#output-panel {
    height: 14;
    margin: 0 3 1 3;
    background: $panel;
    border: round $primary;
    padding: 1 2;
}
#output-title {
    text-style: bold;
    color: $text;
}
#test-output {
    color: $text;
}
#action-row {
    height: 3;
    margin-top: 1;
    align: center middle;
}
.action-btn {
    background: $boost; color: $text;
    border: round $primary;
    min-width: 18;
    margin-right: 1;
}
.action-btn:hover { border: round $accent; }
#run-tests-btn {
    background: $success;
    border: round $warning;
    min-width: 22;
}
#run-tests-btn:hover { background: $warning; }
#hint-btn {
    background: $primary;
    border: round $accent;
    min-width: 18;
}

/* ─── Interactive quiz ──────────────────────────────────────────────── */
#quiz-panel {
    width: 82%;
    max-width: 130;
    height: auto;
    margin: 2 0;
    padding: 2 3;
    background: $panel;
    border: round $primary;
}
#quiz-title {
    text-style: bold;
    color: $text;
    margin-bottom: 1;
}
#quiz-question {
    color: $text;
    margin-bottom: 1;
}
.answer-btn {
    width: 100%;
    height: 3;
    text-align: left;
    background: $surface;
    color: $text;
    border: round $primary;
    margin-bottom: 1;
}
.answer-btn:hover { border: round $accent; }
#quiz-feedback {
    color: $text;
    min-height: 5;
    margin: 1 0;
}
#quiz-next-btn {
    background: $primary;
    color: $text;
    border: round $accent;
    width: 24;
}

/* ─── Profile Screen ────────────────────────────────────────────────── */
#profile-header {
    height: 5;
    align: center middle;
    margin: 1 0 0 0;
}
#profile-title {
    text-style: bold;
    width: 1fr;
    text-align: center;
    padding: 0 3;
}
#profile-back-btn {
    background: $surface; color: $text;
    border: round $primary; min-width: 26;
}
#profile-back-btn:hover { border: round $accent; }
#profile-header-spacer { width: 26; }

#profile-body {
    margin: 1 4 1 4;
    height: 1fr;
    align: center top;
}

.stat-card {
    width: 1fr;
    height: auto;
    padding: 1 2;
    margin-bottom: 1;
    background: $panel;
    border: round $primary;
}
.stat-card-title {
    text-style: bold;
    color: $text;
    margin-bottom: 1;
}
.stat-row {
    height: auto;
    margin-bottom: 1;
}
.stat-label {
    color: $text-muted;
    width: 40%;
    text-align: left;
}
.stat-value {
    color: $text;
    width: 60%;
    text-align: left;
    text-style: bold;
}

#profile-skills {
    width: 100%;
    margin-bottom: 1;
}
.skill-item {
    height: 3;
    margin-bottom: 1;
    padding: 0 2;
    background: $surface;
    border: round $primary;
    align: center middle;
}
.skill-topic {
    color: $text;
    width: 1fr;
    text-align: left;
}
.skill-badge {
    color: $text;
    text-style: bold;
    padding: 0 2;
}
.skill-beginner {
    color: $text;
    background: $boost;
}
.skill-intermediate {
    color: $text;
    background: $accent;
}
.skill-advanced {
    color: $text;
    background: $success;
}

#profile-mistakes {
    width: 100%;
    margin-bottom: 1;
}
.mistake-item {
    height: auto;
    padding: 1 2;
    margin-bottom: 1;
    background: $surface;
    border: round $primary;
}
.mistake-topic {
    color: $accent;
    text-style: bold;
}
.mistake-text {
    color: $text;
    margin-top: 1;
}

.section-label {
    color: $text;
    text-style: bold;
    margin-top: 2;
    margin-bottom: 1;
}
/* ─── Global button appearance: remove filled backgrounds ───────────────── */
Button, .nav-btn, .action-btn, .answer-btn, #generate-btn, #profile-btn, #debug-btn, #quiz-btn, #practice-btn, #run-tests-btn, #hint-btn {
    background: transparent;
    color: $text;
    border: round $primary;
    padding: 0 1;
}

Button:hover, .nav-btn:hover, .action-btn:hover, .answer-btn:hover, #generate-btn:hover, #profile-btn:hover, #debug-btn:hover, #quiz-btn:hover, #practice-btn:hover, #run-tests-btn:hover, #hint-btn:hover {
    background: transparent;
    border: round $accent;
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
                    cls = "nav-item-active" if label == self._active else "nav-item"
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
                with Horizontal(id="create-button-row"):
                    yield Button("+ Generate Course", id="generate-btn")
                    yield Button("Profile", id="profile-btn")
                    yield Button("Debug Coach", id="debug-btn")

            with VerticalScroll(id="courses-wrap"):
                yield Static("Your Courses", id="courses-title")
                for i, course in enumerate(COURSES):
                    yield Button(
                        f"  {course.title}    ·  {course.total_sections} sections",
                        id=f"course-{i}",
                        classes="course-card",
                    )

        yield Static(
            "ready · ⌃N new course · click a course to open · Profile button · q quit",
            id="status",
        )
        yield Footer()

    def action_focus_input(self) -> None:
        self.query_one("#prompt-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "prompt-input":
            self._trigger_generate()

    def _trigger_generate(self) -> None:
        prompt = self.query_one("#prompt-input", Input).value.strip()
        if not prompt:
            self._set_status("Type a topic first, then hit Generate.")
            return
        self._set_status(f"Generating course: “{prompt}” … (Please wait)")
        self.fetch_course(prompt)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "generate-btn":
            self._trigger_generate()
        elif bid == "profile-btn":
            self.app.push_screen(ProfileScreen())
        elif bid == "debug-btn":
            self.app.push_screen(DebugCoachScreen())
        elif bid.startswith("course-"):
            idx = int(bid.split("-")[1])
            self.app.push_screen(CourseScreen(COURSES[idx]))

    def _set_status(self, text: str) -> None:
        self.query_one("#status", Static).update(text)

    @work(thread=True)
    def fetch_course(self, prompt: str) -> None:
        try:
            req = request.Request(
                "http://127.0.0.1:8000/api/ai/generate-course",
                data=json.dumps({"prompt": prompt}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with request.urlopen(req) as response:
                data = json.loads(response.read().decode("utf-8"))

            course_data_str = data.get("response", "")
            course_data = json.loads(course_data_str)

            is_coding = infer_is_coding(course_data, prompt)
            course = Course(
                title=course_data.get("t", "Unknown Course"),
                parts=[],
                is_coding=is_coding,
            )
            course_lang = course_data.get("l", "text")
            for part_data in course_data.get("c", []):
                part = Part(title=part_data.get("n", "Unknown Part"), sections=[])
                for sec_data in part_data.get("s", []):
                    sec_title = sec_data.get("t", "Unknown Section")
                    body_parts = []
                    code = None
                    code_lang = course_lang
                    footer_parts = []

                    found_code = False
                    for content in sec_data.get("c", []):
                        if content.get("type") == "p":
                            if not found_code:
                                body_parts.append(content.get("text", ""))
                            else:
                                footer_parts.append(content.get("text", ""))
                        elif is_coding and content.get("type") == "code":
                            code = content.get("code", "")
                            code_lang = content.get("lang", course_lang)
                            found_code = True

                    sec = Section(
                        title=sec_title,
                        body="\n\n".join(body_parts),
                        code=code,
                        code_lang=code_lang,
                        footer="\n\n".join(footer_parts) if footer_parts else None,
                    )
                    part.sections.append(sec)
                course.parts.append(part)

            self.app.call_from_thread(self._add_course, course)
        except Exception as e:
            self.app.call_from_thread(self._set_status, f"Error: {str(e)}")

    def _add_course(self, course: Course) -> None:
        COURSES.append(course)
        wrap = self.query_one("#courses-wrap")
        i = len(COURSES) - 1
        wrap.mount(
            Button(
                f"  {course.title}    ·  {course.total_sections} sections",
                id=f"course-{i}",
                classes="course-card",
            )
        )
        self._set_status(f"Course '{course.title}' generated successfully!")


# ──────────────────────────────────────────────────────────────────────────────
# Course detail
# ──────────────────────────────────────────────────────────────────────────────


class CourseScreen(Screen):
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("left", "prev_section", "Previous"),
        Binding("right", "next_section", "Next"),
        Binding("p", "practice", "Practice"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, course: Course) -> None:
        super().__init__()
        self.course = course
        self.flat = course.flat_sections()
        self.cursor = 0
        self.user_state: dict = {}
        self.section_started_at = time.monotonic()

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
                yield Static(f"1/{self.course.total_sections}", id="progress-text")
            with Horizontal(id="adaptive-row"):
                yield Static("Skill: beginner", id="skill-level")
                yield Static(
                    "Recommended next lesson: start with this section.",
                    id="recommendation",
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
                    yield Button("← Previous Section", id="prev-btn", classes="nav-btn")
                    yield Button("Quiz This Section", id="quiz-btn")
                    yield Button("Practice Block", id="practice-btn")
                    yield Button("Next Section →", id="next-btn", classes="nav-btn")
                yield Static("", id="nav-hint")

        yield Static("← / → navigate · Esc back · q quit", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self._render_section()
        self.fetch_user_state()

    def action_prev_section(self) -> None:
        if self.cursor > 0:
            self._record_section_progress(completed=False)
            self.cursor -= 1
            self.section_started_at = time.monotonic()
            self._render_section()

    def action_next_section(self) -> None:
        if self.cursor < len(self.flat) - 1:
            self._record_section_progress(completed=True)
            self.cursor += 1
            self.section_started_at = time.monotonic()
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
            if not self.course.is_coding:
                return
            sec = self.flat[self.cursor][2]
            self._set_status(f"Generating Quiz for: {sec.title} (Please wait)")
            self.fetch_quiz(sec)
        elif bid == "practice-btn":
            self.action_practice()
        elif bid.startswith("sec-"):
            self._record_section_progress(completed=False)
            self.cursor = int(bid.split("-")[1])
            self.section_started_at = time.monotonic()
            self._render_section()

    def action_practice(self) -> None:
        if not self.course.is_coding:
            self._set_status("Practice blocks are available for coding courses.")
            return

        sec = self.flat[self.cursor][2]
        if sec.challenge:
            self.app.push_screen(ChallengeScreen(sec, sec.challenge))
            return

        self._set_status(f"Generating AI practice block for: {sec.title} ...")
        self.fetch_challenge(sec)

    @work(thread=True)
    def fetch_challenge(self, sec: Section) -> None:
        fallback = challenge_for_section(sec)
        try:
            req = request.Request(
                "http://127.0.0.1:8000/api/ai/generate-challenge",
                data=json.dumps(
                    {
                        "user_id": "default",
                        "title": sec.title,
                        "body": sec.body,
                        "code": sec.code or "",
                        "language": sec.code_lang,
                    }
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with request.urlopen(req) as response:
                data = json.loads(response.read().decode("utf-8"))
            challenge = self._normalize_ai_challenge(data.get("response"), fallback)
            sec.challenge = challenge
            self.app.call_from_thread(self._open_challenge, sec, challenge, True)
        except Exception:
            self.app.call_from_thread(self._open_challenge, sec, fallback, False)

    def _normalize_ai_challenge(self, challenge: object, fallback: dict) -> dict:
        if not isinstance(challenge, dict):
            return fallback

        tests = challenge.get("tests")
        if not isinstance(tests, list):
            return fallback

        normalized_tests = []
        for test in tests:
            if not isinstance(test, dict):
                continue
            name = str(test.get("name") or "generated test")
            code = str(test.get("code") or "").strip()
            if code:
                normalized_tests.append({"name": name, "code": code})

        starter_code = str(challenge.get("starter_code") or "").strip()
        instructions = str(challenge.get("instructions") or "").strip()
        if not starter_code or not instructions or not normalized_tests:
            return fallback

        return {
            "topic": str(challenge.get("topic") or fallback["topic"]),
            "language": "python",
            "instructions": instructions,
            "starter_code": starter_code,
            "tests": normalized_tests[:5],
        }

    def _open_challenge(self, sec: Section, challenge: dict, from_ai: bool) -> None:
        self._set_status(
            "AI practice block ready."
            if from_ai
            else "AI practice failed; opened fallback block."
        )
        self.app.push_screen(ChallengeScreen(sec, challenge))

    @work(thread=True)
    def fetch_user_state(self) -> None:
        try:
            with request.urlopen(
                "http://127.0.0.1:8000/user-state?user_id=default"
            ) as response:
                state = json.loads(response.read().decode("utf-8"))
            self.app.call_from_thread(self._apply_user_state, state)
        except Exception:
            pass

    @work(thread=True)
    def update_progress(self, payload: dict) -> None:
        try:
            req = request.Request(
                "http://127.0.0.1:8000/update-progress",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with request.urlopen(req) as response:
                state = json.loads(response.read().decode("utf-8"))
            self.app.call_from_thread(self._apply_user_state, state)
        except Exception:
            pass

    def _record_section_progress(self, completed: bool) -> None:
        _, _, sec = self.flat[self.cursor]
        elapsed = int(time.monotonic() - self.section_started_at)
        self.update_progress(
            {
                "user_id": "default",
                "lesson_id": sec.title,
                "topic": sec.title,
                "completed": completed,
                "time_spent_seconds": elapsed,
            }
        )

    def _apply_user_state(self, state: dict) -> None:
        self.user_state = state
        self._update_adaptive_panel()

    @work(thread=True)
    def fetch_quiz(self, sec: Section) -> None:
        try:
            req = request.Request(
                "http://127.0.0.1:8000/api/ai/generate-questions",
                data=json.dumps({"prompt": sec.body}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with request.urlopen(req) as response:
                data = json.loads(response.read().decode("utf-8"))

            questions_str = data.get("response", "")
            questions = json.loads(questions_str)

            if questions and len(questions) > 0:
                self.app.call_from_thread(self._open_quiz, sec, questions)
            else:
                self.app.call_from_thread(self._set_status, "No questions generated.")
        except Exception as e:
            self.app.call_from_thread(self._set_status, f"Error: {str(e)}")

    def _open_quiz(self, sec: Section, questions: list[dict]) -> None:
        self._set_status("Quiz ready.")
        self.app.push_screen(QuizScreen(sec, questions))

    def _render_section(self) -> None:
        _, _, sec = self.flat[self.cursor]

        self.query_one("#section-title", Static).update(sec.title)
        self.query_one("#section-body", Static).update(sec.body)

        code_widget = self.query_one("#section-code", Static)
        if self.course.is_coding and sec.code:
            code_widget.display = True
            code_widget.update(
                Syntax(
                    sec.code,
                    sec.code_lang,
                    theme="monokai",
                    # background_color="#0a0a0d",
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
        quiz_btn = self.query_one("#quiz-btn", Button)
        practice_btn = self.query_one("#practice-btn", Button)
        quiz_btn.display = self.course.is_coding
        practice_btn.display = self.course.is_coding
        practice_btn.disabled = not self.course.is_coding
        self._update_adaptive_panel()

        for i in range(len(self.flat)):
            btn = self.query_one(f"#sec-{i}", Button)
            if i == self.cursor:
                btn.add_class("section-active")
            else:
                btn.remove_class("section-active")

    def _set_status(self, text: str) -> None:
        self.query_one("#status", Static).update(text)

    def _update_adaptive_panel(self) -> None:
        _, _, sec = self.flat[self.cursor]
        profile = self.user_state.get("profile", {})
        skill_levels = (
            profile.get("skill_levels", {}) if isinstance(profile, dict) else {}
        )
        skill = skill_levels.get(sec.title, skill_levels.get("general", "beginner"))
        recommendations = self.user_state.get("recommendations") or [
            "Recommended next lesson: complete this section and try the practice block."
        ]
        hint = (
            self.user_state.get("adaptive_hint")
            or "Your course will adapt as you complete quizzes and practice."
        )
        self.query_one("#skill-level", Static).update(f"Skill: {skill}")
        self.query_one("#recommendation", Static).update(
            f"Recommended next lesson: {recommendations[0]} · {hint}"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Interactive practice
# ──────────────────────────────────────────────────────────────────────────────


class QuizScreen(Screen):
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("n", "next_question", "Next"),
    ]

    def __init__(self, section: Section, questions: list[dict]) -> None:
        super().__init__()
        self.section = section
        self.questions = [q for q in questions if isinstance(q, dict)]
        self.cursor = 0
        self.correct_count = 0
        self.wrong_count = 0
        self.answered_current = False

    def compose(self) -> ComposeResult:
        yield NavBar(active="DDQ Animation")
        with Vertical(id="dashboard-body"):
            with Vertical(id="quiz-panel"):
                yield Static("", id="quiz-title")
                yield Static("", id="quiz-question")
                yield Button("", id="answer-a1", classes="answer-btn")
                yield Button("", id="answer-a2", classes="answer-btn")
                yield Button("", id="answer-a3", classes="answer-btn")
                yield Button("", id="answer-a4", classes="answer-btn")
                yield Static("", id="quiz-feedback")
                with Horizontal(id="action-row"):
                    yield Button("Next", id="quiz-next-btn")
                    yield Button("Back", id="quiz-back-btn", classes="action-btn")
        yield Static("Pick an answer · n next · Esc back", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self._render_question()

    def action_next_question(self) -> None:
        self._next_question()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid.startswith("answer-"):
            self._answer(bid.removeprefix("answer-"))
        elif bid == "quiz-next-btn":
            self._next_question()
        elif bid == "quiz-back-btn":
            self.app.pop_screen()

    def _render_question(self) -> None:
        if not self.questions:
            self.query_one("#quiz-title", Static).update("Quiz")
            self.query_one("#quiz-question", Static).update(
                "No questions were generated."
            )
            return

        question = self.questions[self.cursor]
        self.answered_current = False
        self.query_one("#quiz-title", Static).update(
            f"Quiz: {self.section.title} · {self.cursor + 1}/{len(self.questions)}"
        )
        self.query_one("#quiz-question", Static).update(question.get("q", "Question"))
        for key in ("a1", "a2", "a3", "a4"):
            self.query_one(f"#answer-{key}", Button).label = (
                f"{key.upper()}: {question.get(key, '')}"
            )
            self.query_one(f"#answer-{key}", Button).disabled = False
        self.query_one("#quiz-feedback", Static).update("Choose the best answer.")
        self.query_one("#quiz-next-btn", Button).disabled = True

    def _answer(self, selected: str) -> None:
        if self.answered_current:
            return

        question = self.questions[self.cursor]
        correct = question.get("correct", "")
        explanation = self._explanation(question)
        self.answered_current = True

        for key in ("a1", "a2", "a3", "a4"):
            self.query_one(f"#answer-{key}", Button).disabled = True

        if selected == correct:
            self.correct_count += 1
            self.query_one("#quiz-feedback", Static).update(
                f"Correct.\n\n{explanation}"
            )
        else:
            self.wrong_count += 1
            self.query_one("#quiz-feedback", Static).update(
                f"Not quite. You picked {selected.upper()}, but the answer is {correct.upper()}.\n\n"
                f"{explanation}"
            )

        self.query_one("#quiz-next-btn", Button).disabled = False

    def _next_question(self) -> None:
        if not self.questions:
            self.app.pop_screen()
            return

        if not self.answered_current:
            self.query_one("#quiz-feedback", Static).update(
                "Pick an answer first so the quiz can adapt to your result."
            )
            return

        if self.cursor < len(self.questions) - 1:
            self.cursor += 1
            self._render_question()
            return

        total = len(self.questions)
        score = round((self.correct_count / total) * 100)
        self.query_one("#quiz-title", Static).update("Quiz complete")
        self.query_one("#quiz-question", Static).update(
            f"Score: {self.correct_count}/{total} ({score}%)"
        )
        self.query_one("#quiz-feedback", Static).update(
            "Nice work. Your skill profile has been updated, including retries for missed questions."
        )
        self.query_one("#quiz-next-btn", Button).label = "Done"
        self.save_quiz_progress(score)
        self.answered_current = True
        self.questions = []

    def _explanation(self, question: dict) -> str:
        explanation = str(question.get("e") or "").strip()
        if explanation:
            return explanation

        correct_key = question.get("correct", "")
        correct_text = question.get(correct_key, "the correct option")
        return (
            f"The correct answer is {correct_key.upper()}: {correct_text}. "
            "Review the section example and compare it with the wording of each option."
        )

    @work(thread=True)
    def save_quiz_progress(self, score: int) -> None:
        try:
            req = request.Request(
                "http://127.0.0.1:8000/update-progress",
                data=json.dumps(
                    {
                        "user_id": "default",
                        "lesson_id": self.section.title,
                        "quiz_id": f"{self.section.title}-quiz",
                        "topic": self.section.title,
                        "completed": score >= 70,
                        "quiz_score": score,
                        "retries": self.wrong_count,
                        "mistakes": [self.section.title] if self.wrong_count else [],
                    }
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            request.urlopen(req).close()
        except Exception:
            pass


class ChallengeScreen(Screen):
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+r", "run_tests", "Run tests"),
        Binding("ctrl+h", "request_hint", "Hint"),
    ]

    def __init__(self, section: Section, challenge: dict | None = None) -> None:
        super().__init__()
        self.section = section
        self.challenge = challenge or challenge_for_section(section)
        self.last_results: list[dict] = []
        self.hint_level = 0

    def compose(self) -> ComposeResult:
        yield NavBar(active="DDQ Animation")
        with Horizontal(id="workspace"):
            with Vertical(id="instructions-pane"):
                yield Static("Challenge", id="pane-title")
                yield Static(
                    self.challenge.get("instructions", ""), id="practice-instructions"
                )
                yield Static("Hint progression: none yet", id="debug-response")
            with Vertical(id="editor-pane"):
                yield Static("Code", id="pane-title")
                yield TextArea(
                    self.challenge.get("starter_code", ""),
                    language=self.challenge.get("language", "python"),
                    id="code-editor",
                )
                with Horizontal(id="action-row"):
                    yield Button(
                        "Run Tests (Ctrl+R)", id="run-tests-btn", classes="action-btn"
                    )
                    yield Button(
                        "AI Hint (Ctrl+H)", id="hint-btn", classes="action-btn"
                    )
                    yield Button("Back", id="practice-back-btn", classes="action-btn")
        with Vertical(id="output-panel"):
            yield Static("Output", id="output-title")
            yield Static(
                "This block was generated for the current lesson. Run tests with the button or Ctrl+R.",
                id="test-output",
            )
        yield Static("Ctrl+R run tests · Ctrl+H hint · Esc back", id="status")
        yield Footer()

    def action_run_tests(self) -> None:
        self._run_tests()

    def action_request_hint(self) -> None:
        self._request_hint()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "run-tests-btn":
            self._run_tests()
        elif bid == "hint-btn":
            self._request_hint()
        elif bid == "practice-back-btn":
            self.app.pop_screen()

    def _editor_text(self) -> str:
        editor = self.query_one("#code-editor", TextArea)
        return editor.text

    def _run_tests(self) -> None:
        self.query_one("#test-output", Static).update(
            Text("Running tests...", style="yellow")
        )
        self.run_tests(self._editor_text())

    def _request_hint(self) -> None:
        self.hint_level = min(4, self.hint_level + 1)
        self.query_one("#debug-response", Static).update(
            f"Requesting level {self.hint_level} hint..."
        )
        self.request_hint(self._editor_text(), self.hint_level)

    @work(thread=True)
    def run_tests(self, code: str) -> None:
        try:
            req = request.Request(
                "http://127.0.0.1:8000/run-code",
                data=json.dumps(
                    {
                        "language": self.challenge.get("language", "python"),
                        "code": code,
                        "tests": self.challenge.get("tests", []),
                        "timeout_seconds": 5,
                    }
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with request.urlopen(req) as response:
                data = json.loads(response.read().decode("utf-8"))
            self.last_results = data.get("results", [])
            self.app.call_from_thread(self._show_test_results, data)
            self.app.call_from_thread(self._store_attempt, code, data)
        except Exception as exc:
            self.app.call_from_thread(
                self._show_test_error, f"Error running tests: {exc}"
            )

    @work(thread=True)
    def request_hint(self, code: str, hint_level: int) -> None:
        try:
            req = request.Request(
                "http://127.0.0.1:8000/api/ai/challenge-hint",
                data=json.dumps(
                    {
                        "user_id": "default",
                        "topic": self.challenge.get("topic", self.section.title),
                        "instructions": self.challenge.get("instructions", ""),
                        "code": code,
                        "test_results": self.last_results,
                        "hint_level": hint_level,
                    }
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with request.urlopen(req) as response:
                data = json.loads(response.read().decode("utf-8"))
            hint = data.get("response", {})
            self.app.call_from_thread(self._show_hint, hint)
        except Exception as exc:
            self.app.call_from_thread(self._show_hint_error, f"Hint error: {exc}")

    @work(thread=True)
    def save_progress(self, payload: dict) -> None:
        try:
            req = request.Request(
                "http://127.0.0.1:8000/update-progress",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            request.urlopen(req).close()
        except Exception:
            pass

    def _show_test_results(self, data: dict) -> None:
        output = Text()
        all_passed = bool(data.get("passed"))
        output.append(
            "All tests passed\n\n" if all_passed else "Some tests failed\n\n",
            style="bold green" if all_passed else "bold red",
        )
        for result in data.get("results", []):
            passed = bool(result.get("passed"))
            marker = "PASS" if passed else "FAIL"
            detail = result.get("error") or result.get("stdout") or ""
            output.append(f"{marker} ", style="bold green" if passed else "bold red")
            output.append(f"{result.get('name')}", style="white")
            if detail:
                output.append(f": {detail}", style="green" if passed else "red")
            output.append("\n")
        self.query_one("#test-output", Static).update(
            output or Text("No tests returned.", style="yellow")
        )

    def _show_test_error(self, message: str) -> None:
        self.query_one("#test-output", Static).update(Text(message, style="bold red"))

    def _show_hint_error(self, message: str) -> None:
        self.query_one("#debug-response", Static).update(message)

    def _show_hint(self, hint: dict) -> None:
        self.query_one("#debug-response", Static).update(
            f"Hint level {hint.get('hint_level', self.hint_level)}\n"
            f"{hint.get('hint', '')}\n\n"
            f"{hint.get('encouragement', '')}\n"
            f"Next: {hint.get('next_step', '')}"
        )

    def _store_attempt(self, code: str, data: dict) -> None:
        passed = bool(data.get("passed"))
        failed_names = [
            result.get("name", "test")
            for result in data.get("results", [])
            if not result.get("passed")
        ]
        self.save_progress(
            {
                "user_id": "default",
                "lesson_id": self.section.title,
                "topic": self.challenge.get("topic", self.section.title),
                "completed": passed,
                "quiz_score": 100 if passed else 50,
                "retries": 0 if passed else 1,
                "mistakes": failed_names,
                "attempt": code,
                "solution": code if passed else "",
            }
        )


class DebugCoachScreen(Screen):
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+enter", "submit_code", "Submit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.session_id = f"debug-{uuid4().hex[:8]}"

    def compose(self) -> ComposeResult:
        yield NavBar(active="DDQ Animation")
        with Horizontal(id="workspace"):
            with Vertical(id="instructions-pane"):
                yield Static("Debug Coach", id="pane-title")
                yield Static(
                    "Paste buggy code, submit it, then revise based on each hint. "
                    "The coach escalates from a vague hint to a full solution only after repeated attempts.",
                    id="practice-instructions",
                )
                yield Static("Hint level: 0", id="debug-response")
            with Vertical(id="editor-pane"):
                yield Static("Buggy Code", id="pane-title")
                yield TextArea(
                    "def add_one(value):\n    return value + 2\n\nprint(add_one(1))\n",
                    language="python",
                    id="code-editor",
                )
                with Horizontal(id="action-row"):
                    yield Button(
                        "Submit Attempt", id="debug-submit-btn", classes="action-btn"
                    )
                    yield Button("Back", id="debug-back-btn", classes="action-btn")
        with Vertical(id="output-panel"):
            yield Static("Coach Response", id="output-title")
            yield Static(
                "Submit your first attempt to receive a level 1 hint.", id="test-output"
            )
        yield Static("Ctrl+Enter submit · Esc back", id="status")
        yield Footer()

    def action_submit_code(self) -> None:
        self._submit_code()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "debug-submit-btn":
            self._submit_code()
        elif bid == "debug-back-btn":
            self.app.pop_screen()

    def _submit_code(self) -> None:
        code = self.query_one("#code-editor", TextArea).text
        self.query_one("#test-output", Static).update("Asking the coach...")
        self.submit_code(code)

    @work(thread=True)
    def submit_code(self, code: str) -> None:
        try:
            req = request.Request(
                "http://127.0.0.1:8000/api/ai/debug-coach",
                data=json.dumps(
                    {
                        "user_id": "default",
                        "session_id": self.session_id,
                        "language": "python",
                        "topic": "debugging",
                        "code": code,
                    }
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with request.urlopen(req) as response:
                data = json.loads(response.read().decode("utf-8"))
            self.app.call_from_thread(self._show_response, data)
        except Exception as exc:
            self.app.call_from_thread(self._show_error, f"Debug Coach error: {exc}")

    def _show_response(self, data: dict) -> None:
        response = data.get("response", {})
        hint_level = response.get("hint_level", data.get("hint_level", 1))
        self.query_one("#debug-response", Static).update(
            f"Hint level: {hint_level} · attempts: {data.get('attempt_count', 1)}"
        )
        self.query_one("#test-output", Static).update(
            f"{response.get('hint', '')}\n\n"
            f"{response.get('encouragement', '')}\n"
            f"Next: {response.get('next_step', '')}"
        )

    def _show_error(self, message: str) -> None:
        self.query_one("#test-output", Static).update(message)


# ──────────────────────────────────────────────────────────────────────────────
# User Profile
# ──────────────────────────────────────────────────────────────────────────────


class ProfileScreen(Screen):
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield NavBar(active="Profile")

        with Vertical(id="profile-header"):
            with Horizontal():
                yield Button("← Back", id="profile-back-btn")
                yield Static("Your Learning Profile", id="profile-title")
                yield Static("", id="profile-header-spacer")

        with VerticalScroll(id="profile-body"):
            # Overview stats
            with Vertical(classes="stat-card"):
                yield Static("Learning Overview", classes="stat-card-title")
                yield Static("", id="profile-overview")

            # Skill levels
            with Vertical(classes="stat-card"):
                yield Static("Skills & Levels", classes="stat-card-title")
                yield Static("", id="profile-skills-content")

            # Recent mistakes
            with Vertical(classes="stat-card"):
                yield Static("Recent Challenges", classes="stat-card-title")
                yield Static("", id="profile-mistakes-content")

            # Recommendations
            with Vertical(classes="stat-card"):
                yield Static("Personalized Recommendations", classes="stat-card-title")
                yield Static("", id="profile-recommendations-content")

        yield Static("Esc back · q quit", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.fetch_profile()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "profile-back-btn":
            self.app.pop_screen()

    @work(thread=True)
    def fetch_profile(self) -> None:
        try:
            with request.urlopen(
                "http://127.0.0.1:8000/user-state?user_id=default"
            ) as response:
                data = json.loads(response.read().decode("utf-8"))
            self.app.call_from_thread(self._render_profile, data)
        except Exception as e:
            self.app.call_from_thread(
                self._show_error, f"Error loading profile: {str(e)}"
            )

    def _render_profile(self, data: dict) -> None:
        profile = data.get("profile", {})
        pace = data.get("pace", "steady learner")
        recommendations = data.get("recommendations", [])
        adaptive_hint = data.get("adaptive_hint", "")

        # Overview
        lessons_completed = len(profile.get("lessons_completed", []))
        quiz_count = len(profile.get("quiz_scores", {}))
        total_time = sum(
            int(v) for v in profile.get("time_spent_per_lesson", {}).values()
        )
        total_time_display = f"{total_time // 60} min" if total_time else "0 min"

        overview_text = (
            f"Lessons Completed: {lessons_completed}\n"
            f"Quiz Attempts: {quiz_count}\n"
            f"Time Invested: {total_time_display}\n"
            f"Learning Pace: {pace}"
        )
        self.query_one("#profile-overview", Static).update(overview_text)

        # Skills
        skill_levels = profile.get("skill_levels", {})
        if skill_levels:
            skills_text = Text()
            for topic, level in sorted(skill_levels.items()):
                level_color = (
                    "green"
                    if level == "advanced"
                    else "yellow" if level == "intermediate" else "blue"
                )
                skills_text.append(f"  • {topic}: ", style="white")
                skills_text.append(level.upper(), style=f"bold {level_color}")
                skills_text.append("\n")
            self.query_one("#profile-skills-content", Static).update(skills_text)
        else:
            self.query_one("#profile-skills-content", Static).update(
                "Start a lesson to build your skill profile."
            )

        # Recent mistakes
        mistakes = profile.get("recent_mistakes", [])
        if mistakes:
            mistakes_text = Text()
            for mistake in mistakes[-5:]:  # Show last 5
                topic = mistake.get("topic", "Unknown")
                mistake_desc = mistake.get("mistake", "")
                mistakes_text.append(f"  {topic}: ", style="bold yellow")
                mistakes_text.append(f"{mistake_desc}\n", style="white")
            self.query_one("#profile-mistakes-content", Static).update(mistakes_text)
        else:
            self.query_one("#profile-mistakes-content", Static).update(
                "No recent mistakes tracked."
            )

        # Recommendations
        if recommendations:
            rec_text = Text()
            for i, rec in enumerate(recommendations[:3], 1):
                rec_text.append(f"  {i}. ", style="bold $primary")
                rec_text.append(f"{rec}\n", style="white")
            if adaptive_hint:
                rec_text.append(f"\n  💡 {adaptive_hint}", style="bold $accent")
            self.query_one("#profile-recommendations-content", Static).update(rec_text)
        else:
            self.query_one("#profile-recommendations-content", Static).update(
                "Complete quizzes and practice blocks to get personalized recommendations."
            )

    def _show_error(self, message: str) -> None:
        self.query_one("#profile-overview", Static).update(
            Text(message, style="bold red")
        )


class GyftTUI(App):
    CSS = CSS
    TITLE = "Gyft"
    SUB_TITLE = "Personalized AI learning, in your terminal"
    THEME = "dracula"

    def on_mount(self) -> None:
        self.push_screen(DashboardScreen())


if __name__ == "__main__":
    GyftTUI().run()
