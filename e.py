from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Static


class FixedRoundedApp(App):
    CSS = """
    Screen {
        align: center middle;
    }

    /* 1. The outer wrapper has the border, but NO background */
    .outer-box {
        border: round $primary;
        width: 40;
        height: auto;
        padding: 0;
    }

    /* 2. The inner container has the background and padding */
    .inner-content {
        background: $boost;
        padding: 1 2;
        width: 100%;
        height: auto;
        text-align: center;
    }
    """

    def compose(self) -> ComposeResult:
        # Wrap the content in an outer box that handles ONLY the border
        with Vertical(classes="outer-box"):
            yield Static(
                "Background is now clipped\nwithin the rounded border.",
                classes="inner-content",
            )


if __name__ == "__main__":
    FixedRoundedApp().run()
