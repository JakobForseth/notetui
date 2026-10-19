"""Search modal screen for fuzzy finding notes."""

from datetime import datetime
from pathlib import Path

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, Label, Static

from notetui.notes import NoteManager, SearchResult


class SearchResultItem(Static):
    """A single search result item."""

    can_focus = True

    def __init__(self, result: SearchResult) -> None:
        super().__init__()
        self.result = result

    def compose(self) -> ComposeResult:
        date_str = self.result.date.strftime("%d %b %Y")
        # Truncate long lines
        content = self.result.line_content
        if len(content) > 60:
            content = content[:57] + "..."
        yield Label(f"[bold cyan]{date_str}[/] [dim]L{self.result.line_number}[/]", markup=True)
        yield Label(f"  {content}")

    def _on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            event.stop()
            # Get the modal screen and call select
            screen = self.screen
            if isinstance(screen, SearchModalScreen):
                screen.select_result(self.result)
        elif event.key == "up":
            event.stop()
            self.screen.focus_previous()
        elif event.key == "down":
            event.stop()
            self.screen.focus_next()

    def _on_click(self, event: events.Click) -> None:
        screen = self.screen
        if isinstance(screen, SearchModalScreen):
            screen.select_result(self.result)


class SearchModalScreen(ModalScreen):
    """A modal screen for searching notes."""

    BINDINGS = [
        Binding("escape", "cancel", "Close", show=True),
    ]

    DEFAULT_CSS = """
    SearchModalScreen {
        align: center middle;
    }

    SearchModalScreen > #search-container {
        width: 80;
        height: 30;
        background: ansi_default;
        border: tall ansi_blue;
        padding: 1;
    }

    SearchModalScreen #search-title {
        text-align: center;
        color: ansi_blue;
        text-style: bold;
        padding-bottom: 1;
    }

    SearchModalScreen #search-input {
        width: 100%;
        background: ansi_default;
        border: tall ansi_bright_black;
        margin-bottom: 1;
    }

    SearchModalScreen #search-input:focus {
        border: tall ansi_blue;
    }

    SearchModalScreen #search-results {
        width: 100%;
        height: 1fr;
        background: ansi_default;
        border: tall ansi_bright_black;
    }

    SearchModalScreen .search-hint {
        text-align: center;
        color: ansi_bright_black;
        padding: 2;
    }

    SearchModalScreen SearchResultItem {
        width: 100%;
        height: auto;
        padding: 0 1;
        background: ansi_default;
    }

    SearchModalScreen SearchResultItem:focus {
        background: ansi_blue;
    }

    SearchModalScreen SearchResultItem:hover {
        background: ansi_bright_black;
    }
    """

    def __init__(self, note_manager: NoteManager) -> None:
        super().__init__()
        self.note_manager = note_manager
        self.results: list[SearchResult] = []

    def compose(self) -> ComposeResult:
        with Container(id="search-container"):
            yield Label("🔍 Search Notes", id="search-title")
            yield Input(placeholder="Type to search...", id="search-input")
            yield VerticalScroll(Label("Start typing to search all notes", classes="search-hint"), id="search-results")

    def on_mount(self) -> None:
        """Focus the search input when mounted."""
        self.query_one("#search-input", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        if event.input.id == "search-input":
            self._perform_search(event.value)

    def _perform_search(self, query: str) -> None:
        """Perform the search and update results."""
        results_container = self.query_one("#search-results", VerticalScroll)
        results_container.remove_children()

        if len(query) >= 2:
            self.results = self.note_manager.search_notes(query)
            if self.results:
                for result in self.results[:30]:  # Limit to 30 results
                    results_container.mount(SearchResultItem(result))
            else:
                results_container.mount(Label("No results found", classes="search-hint"))
        else:
            self.results = []
            results_container.mount(Label("Type at least 2 characters to search", classes="search-hint"))

    def select_result(self, result: SearchResult) -> None:
        """Select a result and dismiss the modal."""
        self.dismiss((result.date, result.line_number))

    def action_cancel(self) -> None:
        """Cancel and close the modal."""
        self.dismiss(None)
