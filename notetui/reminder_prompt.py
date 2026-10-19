"""Modal prompt for setting a reminder on a point."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Input, Label

from notetui.points import parse_reminder


class ReminderPromptScreen(ModalScreen):
    """Ask for a reminder spec. Dismisses with the spec string ("" clears), or None on cancel."""

    BINDINGS = [
        Binding("escape", "cancel", "Close", show=True),
    ]

    DEFAULT_CSS = """
    ReminderPromptScreen {
        align: center middle;
    }

    ReminderPromptScreen > #reminder-container {
        width: 80;
        height: auto;
        background: $surface;
        border: tall $primary;
        padding: 1 2;
    }

    ReminderPromptScreen #reminder-title {
        width: 100%;
        text-align: center;
        color: $primary;
        text-style: bold;
        padding-bottom: 1;
    }

    ReminderPromptScreen .reminder-hint {
        color: ansi_bright_black;
    }

    ReminderPromptScreen #reminder-error {
        color: $error;
        height: auto;
    }
    """

    def __init__(self, current: str = "") -> None:
        super().__init__()
        self.current = current

    def compose(self) -> ComposeResult:
        with Container(id="reminder-container"):
            yield Label("⏰ Reminder", id="reminder-title")
            yield Label("01.30 = every 1 hour 30 min    13:00 = every day at 13:00", classes="reminder-hint")
            yield Label("Leave empty to remove the reminder. Esc to cancel.", classes="reminder-hint")
            yield Input(value=self.current, placeholder="01.30 or 13:00", id="reminder-input")
            yield Label("", id="reminder-error")

    def on_mount(self) -> None:
        self.query_one("#reminder-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if value and parse_reminder(value) is None:
            self.query_one("#reminder-error", Label).update(
                "Not valid: use HH.MM for a repeating interval or HH:MM for a time of day"
            )
            return
        self.dismiss(value)

    def action_cancel(self) -> None:
        self.dismiss(None)
