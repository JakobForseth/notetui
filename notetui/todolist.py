"""Todo list widget for displaying tasks from all notes."""

from pathlib import Path
from datetime import datetime
from textual.app import ComposeResult
from textual.containers import VerticalScroll, Container
from textual.widgets import Static, Label
from textual.reactive import reactive
from textual.binding import Binding
from textual.message import Message
from textual import events
import re


class TodoItem(Static):
    """A single todo item."""

    DEFAULT_CSS = """
    TodoItem {
        width: 100%;
        height: auto;
        padding: 1;
        margin: 0 0 1 0;
        background: #1a1f2e;
        border: round #7b2cbf;
        color: #00d4ff;
    }

    TodoItem:hover {
        background: #252a3e;
        border: round #00ffff;
    }

    TodoItem:focus {
        background: #7b2cbf;
        border: heavy #00ffff;
    }

    TodoItem .todo-text {
        color: #00ffff;
        text-style: bold;
    }

    TodoItem .todo-date {
        color: #7b2cbf;
        text-style: italic;
    }
    """

    can_focus = True

    class Selected(Message):
        """Message sent when a todo is selected with Enter."""
        def __init__(self, date_str: str) -> None:
            self.date_str = date_str
            super().__init__()

    def __init__(self, text: str, date_str: str, file_path: Path, line_number: int, **kwargs):
        """Initialize a todo item.

        Args:
            text: The todo text
            date_str: The date this todo is from
            file_path: Path to the note file
            line_number: Line number of the todo in the file
        """
        super().__init__(**kwargs)
        self.todo_text = text
        self.date_str = date_str
        self.file_path = file_path
        self.line_number = line_number

    def compose(self) -> ComposeResult:
        """Compose the todo item."""
        yield Label(f"• {self.todo_text}", classes="todo-text")
        yield Label(f"  {self.date_str}", classes="todo-date")

    def _on_key(self, event: events.Key) -> None:
        """Handle key presses."""
        if event.key == "enter":
            self.post_message(self.Selected(self.date_str))
        elif event.key == "up":
            self.screen.focus_previous()
        elif event.key == "down":
            self.screen.focus_next()


class TodoList(Container):
    """A scrollable list of todos from all notes."""

    class TodoFileUpdated(Message):
        """Message sent when a todo file has been updated."""
        def __init__(self, file_path: Path) -> None:
            self.file_path = file_path
            super().__init__()

    DEFAULT_CSS = """
    TodoList {
        width: 100%;
        height: 100%;
        background: #0a0e14;
        border-left: heavy #00ffff;
        padding: 1;
    }

    TodoList #todo-header {
        width: 100%;
        height: 3;
        background: #1a1f2e;
        color: #00ffff;
        text-align: center;
        text-style: bold;
        border: tall #7b2cbf;
        padding: 1;
        margin-bottom: 1;
    }

    TodoList VerticalScroll {
        width: 100%;
        height: 1fr;
        background: #0d1117;
    }

    TodoList VerticalScroll:focus {
        border: none;
    }

    TodoList #empty-message {
        width: 100%;
        text-align: center;
        color: #7b2cbf;
        padding: 2;
        text-style: italic;
    }
    """

    todos: reactive[list] = reactive(list, recompose=True)

    BINDINGS = [
        Binding("ctrl+d", "finish_todo", "Finish", show=False),
    ]

    def __init__(self, notes_dir: Path, **kwargs):
        """Initialize the todo list.

        Args:
            notes_dir: Directory containing note files
        """
        super().__init__(**kwargs)
        self.notes_dir = notes_dir

    def compose(self) -> ComposeResult:
        """Compose the todo list."""
        yield Label("📋 ALL TODOS", id="todo-header")
        with VerticalScroll(can_focus=False):
            if not self.todos:
                yield Label(
                    "No todos found.\n\nAdd ## headings to your notes!",
                    id="empty-message"
                )
            else:
                for todo_text, date_str, file_path, line_number in self.todos:
                    yield TodoItem(todo_text, date_str, file_path, line_number)

    def scan_notes(self) -> None:
        """Scan all note files for ## headings."""
        todos = []

        if not self.notes_dir.exists():
            self.todos = todos
            return

        # Get all markdown files and sort by date (newest first)
        note_files = []
        for note_file in self.notes_dir.glob("*.md"):
            try:
                # Parse date from filename (format: DD-Mmm-YYYY.md)
                file_date = datetime.strptime(note_file.stem, "%d-%b-%Y")
                note_files.append((file_date, note_file))
            except ValueError:
                # Skip files that don't match the date format
                continue

        # Sort by date descending (newest first)
        note_files.sort(key=lambda x: x[0], reverse=True)

        for _, note_file in note_files:
            try:
                content = note_file.read_text()
                # Extract date from filename (e.g., "21-Nov-2025.md")
                filename = note_file.stem

                # Find all ## headings (with or without space after ##)
                lines = content.split('\n')
                for line_number, line in enumerate(lines):
                    line_stripped = line.strip()
                    if line_stripped.startswith('##') and not line_stripped.startswith('###'):
                        # Extract todo text (remove the ## and any space, also strip trailing #)
                        todo_text = line_stripped[2:].strip().rstrip('#').strip()

                        # Skip completed todos (those with strikethrough ~~text~~)
                        if todo_text.startswith('~~') and todo_text.endswith('~~'):
                            continue

                        if todo_text:
                            todos.append((todo_text, filename, note_file, line_number))
            except Exception:
                pass

        self.todos = todos

    def mark_todo_complete(self, todo_item: TodoItem) -> None:
        """Mark a todo as complete by adding strikethrough in the source file.

        Args:
            todo_item: The TodoItem to mark as complete
        """
        try:
            # Read the file
            content = todo_item.file_path.read_text()
            lines = content.split('\n')

            # Find the line that matches the todo text (don't rely on line_number
            # as it may be stale if the file was edited)
            target_line_idx = None
            for idx, line in enumerate(lines):
                line_stripped = line.strip()
                if line_stripped.startswith('##') and not line_stripped.startswith('###'):
                    # Extract todo text from this line
                    extracted_text = line_stripped[2:].strip().rstrip('#').strip()
                    if extracted_text == todo_item.todo_text:
                        target_line_idx = idx
                        break

            if target_line_idx is not None:
                line = lines[target_line_idx]
                # Get the indentation
                indent = line[:len(line) - len(line.lstrip())]
                # Replace with strikethrough, preserving the original todo text
                lines[target_line_idx] = f"{indent}## ~~{todo_item.todo_text}~~"

                # Write back to file
                todo_item.file_path.write_text('\n'.join(lines))

                # Notify that file was updated
                self.post_message(self.TodoFileUpdated(todo_item.file_path))

            # Rescan to update the list
            self.scan_notes()
        except Exception as e:
            pass

    def action_finish_todo(self) -> None:
        """Mark the currently focused todo as finished."""
        # Get the currently focused widget
        focused = self.screen.focused
        if focused and isinstance(focused, TodoItem):
            self.mark_todo_complete(focused)
