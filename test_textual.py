from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Button
from textual import work
import time

class TestApp(App):
    def compose(self) -> ComposeResult:
        with VerticalScroll(id="wrap"):
            yield Button("Initial", id="btn-0", classes="course-card")
        yield Button("Add", id="add-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-btn":
            self.run_worker(self.do_work)

    @work(thread=True)
    def do_work(self):
        time.sleep(1)
        self.app.call_from_thread(self.refresh_list)

    def refresh_list(self):
        wrap = self.query_one("#wrap")
        for child in wrap.query(".course-card"):
            child.remove()
        wrap.mount(Button("Initial", id="btn-0", classes="course-card"))
        wrap.mount(Button("New", id="btn-1", classes="course-card"))
        self.exit("Refreshed")

if __name__ == "__main__":
    app = TestApp()
    app.run()
    print("Done!")
