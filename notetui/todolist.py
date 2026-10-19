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
import json
import os
import re

from rich.style import Style
from rich.text import Text

from notetui.carryover import sync_earlier_copies
from notetui.points import DAILY, PRIORITY_COLORS, notes_end, parse_point


class TodoItem(Static):
    """A single todo item."""

    DEFAULT_CSS = """
    TodoItem {
        width: 100%;
        height: auto;
        padding: 0 1 0 2;
    }

    TodoItem:hover {
        text-style: underline;
    }

    TodoItem:focus {
        background: ansi_blue;
        color: ansi_black;
    }

    TodoItem .todo-reminder {
        color: ansi_bright_black;
        text-style: italic;
        padding-left: 5;
    }

    TodoItem:focus .todo-reminder { color: ansi_black; }
    """

    can_focus = True

    class Selected(Message):
        """Message sent when a todo is selected with Enter."""
        def __init__(self, date_str: str) -> None:
            self.date_str = date_str
            super().__init__()

    def __init__(self, text: str, date_str: str, file_path: Path, line_number: int,
                 is_point: bool = False, priority: int | None = None, reminder: str | None = None,
                 has_notes: bool = False, **kwargs):
        """Initialize a todo item.

        Args:
            text: The todo text
            date_str: The date this todo is from
            file_path: Path to the note file
            line_number: Line number of the todo in the file
        """
        if priority is not None:
            kwargs["classes"] = f"priority-{priority}"
        super().__init__(**kwargs)
        self.todo_text = text
        self.is_point = is_point
        self.priority = priority
        self.reminder = reminder
        self.has_notes = has_notes
        self.date_str = date_str
        self.file_path = file_path
        self.line_number = line_number

    def compose(self) -> ComposeResult:
        """Compose the todo item."""
        # Importance as a coloured tag in its own column, so the point's own
        # text stands alone; the reminder goes underneath, dimmed
        if self.priority is not None:
            tag = Text(f" {self.priority} ", style=Style(color="black", bgcolor=PRIORITY_COLORS[self.priority], bold=True))
        else:
            tag = Text("   ")
        marker = ("↻" if self.priority == DAILY else "☐") if self.is_point else "•"
        notes = " 📝" if self.has_notes else ""
        yield Label(Text.assemble(tag, f" {marker} ", self.todo_text, notes), classes="todo-text")
        if self.reminder:
            yield Label(f"⏰ {self.reminder}", classes="todo-reminder", markup=False)

    def _on_key(self, event: events.Key) -> None:
        """Handle key presses.

        Up/Down move between days; Shift+Up/Down move between the todos
        inside this day's box.
        """
        group = self.parent
        if event.key == "enter":
            self.post_message(self.Selected(self.date_str))
        elif event.key in ("up", "down") and isinstance(group, NoteGroup):
            event.stop()
            group.focus_neighbour_day(-1 if event.key == "up" else 1)
        elif event.key in ("shift+up", "shift+down") and isinstance(group, NoteGroup):
            event.stop()
            group.focus_item(self, -1 if event.key == "shift+up" else 1)


class GroupHeading(Static):
    """The foldable date line at the top of a note's box."""

    can_focus = True

    class Toggled(Message):
        """Sent when the heading asks to fold or unfold its group."""
        def __init__(self, date_str: str, collapsed: bool | None) -> None:
            self.date_str = date_str
            self.collapsed = collapsed
            """True/False to fold/unfold, None to flip."""
            super().__init__()

    def __init__(self, date_str: str, count: int, collapsed: bool) -> None:
        super().__init__()
        self.date_str = date_str
        try:
            title = datetime.strptime(date_str, "%d-%b-%Y").strftime("%A %d %b %Y")
        except ValueError:
            title = date_str
        self.label = f"{title}  ({count})"
        self.show_collapsed(collapsed)

    def show_collapsed(self, collapsed: bool) -> None:
        self.update(("▸ " if collapsed else "▾ ") + self.label)

    def _on_key(self, event: events.Key) -> None:
        group = self.parent
        if event.key == "enter":
            event.stop()
            self.post_message(TodoItem.Selected(self.date_str))
        elif event.key == "space":
            event.stop()
            self.post_message(self.Toggled(self.date_str, None))
        elif event.key == "left":
            event.stop()
            self.post_message(self.Toggled(self.date_str, True))
        elif event.key == "right":
            event.stop()
            self.post_message(self.Toggled(self.date_str, False))
        elif event.key in ("up", "down") and isinstance(group, NoteGroup):
            event.stop()
            group.focus_neighbour_day(-1 if event.key == "up" else 1)
        elif event.key == "shift+down" and isinstance(group, NoteGroup):
            event.stop()
            group.focus_item(None, 1)


class NoteGroup(Container):
    """All todos from one note, in one box."""

    DEFAULT_CSS = """
    NoteGroup {
        width: 100%;
        height: auto;
        /* A "tall" border draws its line at the very edge of each border cell,
           so the background fills the box right up to the line without
           spilling outside it (a round border's line runs through the middle
           of its cells, which can't be half coloured) */
        border: tall ansi_bright_black;
        background: $note-background;
        margin: 0 0 1 0;
        padding: 0;
    }

    NoteGroup:focus-within {
        border: tall ansi_blue;
    }

    NoteGroup GroupHeading {
        width: 100%;
        padding: 0 1;
        text-style: bold;
        color: ansi_blue;
    }

    NoteGroup GroupHeading:focus {
        background: ansi_blue;
        color: ansi_black;
    }

    NoteGroup.collapsed TodoItem {
        display: none;
    }
    """

    def __init__(self, date_str: str, todos: list[dict], collapsed: bool) -> None:
        super().__init__(classes="collapsed" if collapsed else "")
        self.date_str = date_str
        self.todos = todos
        self.collapsed = collapsed

    def compose(self) -> ComposeResult:
        yield GroupHeading(self.date_str, len(self.todos), self.collapsed)
        for todo in self.todos:
            yield TodoItem(**todo)

    def focus_neighbour_day(self, step: int) -> None:
        """Focus the heading of the previous (-1) or next (+1) day's box."""
        groups = list(self.parent.query_children(NoteGroup).results()) if self.parent else [self]
        index = groups.index(self) + step
        if 0 <= index < len(groups):
            groups[index].query_one(GroupHeading).focus()
        else:
            # No day further that way: settle on this day's own heading
            self.query_one(GroupHeading).focus()

    def tab_day(self, step: int) -> None:
        """Tab / Shift+Tab: jump to the next / previous day, past the last one back to the note."""
        groups = list(self.parent.query_children(NoteGroup).results()) if self.parent else [self]
        index = groups.index(self) + step
        if 0 <= index < len(groups):
            groups[index].query_one(GroupHeading).focus()
        elif self.app.editor:
            self.app.editor.focus()

    def focus_item(self, current: "TodoItem | None", step: int) -> None:
        """Move between the todos inside this box (from the heading when current is None)."""
        if self.collapsed:
            return
        items = list(self.query_children(TodoItem).results())
        if not items:
            return
        if current is None:
            index = 0 if step > 0 else len(items) - 1
        else:
            index = items.index(current) + step
        if index < 0:
            self.query_one(GroupHeading).focus()
        elif index < len(items):
            items[index].focus()


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
        background: ansi_default;
        border-left: heavy ansi_bright_black;
        padding: 0 1;
    }

    TodoList #todo-header {
        width: 100%;
        height: 3;
        color: ansi_blue;
        text-align: center;
        text-style: bold;
        border: tall ansi_bright_black;
        background: $note-background;
        margin-bottom: 1;
    }

    TodoList VerticalScroll {
        width: 100%;
        height: 1fr;
        background: ansi_default;
    }

    TodoList VerticalScroll:focus {
        border: none;
    }

    TodoList #empty-message {
        width: 100%;
        text-align: center;
        color: ansi_bright_black;
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
        self.collapsed: set[str] = load_collapsed()

    def compose(self) -> ComposeResult:
        """Compose the todo list."""
        yield Label("📋 ALL TODOS  (Ctrl+O fold all)", id="todo-header")
        with VerticalScroll(can_focus=False):
            if not self.todos:
                yield Label(
                    "No todos found.\n\nAdd ## headings to your notes!",
                    id="empty-message"
                )
            else:
                # Group by note, keeping the newest-first order of the scan
                groups: dict[str, list[dict]] = {}
                for todo in self.todos:
                    groups.setdefault(todo["date_str"], []).append(todo)
                for date_str, todos in groups.items():
                    yield NoteGroup(date_str, todos, date_str in self.collapsed)

    def scan_notes(self) -> None:
        """Scan all note files for ## headings and unchecked points."""
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
                            todos.append(dict(text=todo_text, date_str=filename,
                                              file_path=note_file, line_number=line_number))
                        continue

                    point = parse_point(line)
                    if point and point.is_open and point.text:
                        todos.append(dict(
                            text=point.text, date_str=filename, file_path=note_file,
                            line_number=line_number, is_point=True, priority=point.priority,
                            reminder=point.reminder.describe() if point.reminder else None,
                            has_notes=notes_end(lines, line_number) > line_number + 1,
                        ))
            except Exception:
                pass

        # Within each note, most important first (unprioritised last). Notes stay
        # newest first: the sort is stable and the date is the primary key.
        dates = {t["date_str"]: i for i, t in reversed(list(enumerate(todos)))}
        todos.sort(key=lambda t: (dates[t["date_str"]], 6 if t.get("priority") is None else t["priority"]))
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

            if todo_item.is_point:
                target_line_idx = None
                for idx, line in enumerate(lines):
                    point = parse_point(line)
                    if point and point.is_open and point.text == todo_item.todo_text:
                        point.checked = True
                        lines[idx] = point.format()
                        target_line_idx = idx
                        break
                if target_line_idx is not None:
                    todo_item.file_path.write_text('\n'.join(lines))
                    self.post_message(self.TodoFileUpdated(todo_item.file_path))
                    # A carried-over point: tick off its copies on earlier days too
                    day = datetime.strptime(todo_item.date_str, "%d-%b-%Y")
                    for synced in sync_earlier_copies(self.notes_dir, day, todo_item.todo_text, True):
                        self.post_message(self.TodoFileUpdated(synced))
                target_line_idx = None

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
            if focused.is_point and focused.priority == DAILY:
                self.app.notify("↻ Daily item — it comes back every day, nothing to tick off")
                return
            self.mark_todo_complete(focused)

    def on_group_heading_toggled(self, message: GroupHeading.Toggled) -> None:
        """Fold or unfold one note's group."""
        date_str = message.date_str
        collapse = message.collapsed if message.collapsed is not None else date_str not in self.collapsed
        self._set_collapsed({date_str} if collapse else set(), {date_str})
        self.call_after_refresh(self._focus_heading, date_str)

    def toggle_all(self) -> None:
        """Fold every group, or unfold them all if they're already folded."""
        all_dates = {t["date_str"] for t in self.todos}
        if all_dates <= self.collapsed:
            self._set_collapsed(set(), all_dates)
        else:
            self._set_collapsed(all_dates, all_dates)

    def _set_collapsed(self, collapse: set[str], scope: set[str]) -> None:
        self.collapsed = (self.collapsed - scope) | collapse
        save_collapsed(self.collapsed)
        for group in self.query(NoteGroup).results():
            folded = group.date_str in self.collapsed
            if folded != group.collapsed:
                group.collapsed = folded
                group.set_class(folded, "collapsed")
                group.query_one(GroupHeading).show_collapsed(folded)

    def _focus_heading(self, date_str: str) -> None:
        for heading in self.query(GroupHeading).results():
            if heading.date_str == date_str:
                heading.focus()
                return


def _collapsed_file() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "notetui" / "collapsed.json"


def load_collapsed() -> set[str]:
    """Which notes are folded in the sidebar, remembered between runs."""
    try:
        return set(json.loads(_collapsed_file().read_text()))
    except (OSError, ValueError, TypeError):
        return set()


def save_collapsed(collapsed: set[str]) -> None:
    try:
        path = _collapsed_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(sorted(collapsed)))
    except OSError:
        pass
