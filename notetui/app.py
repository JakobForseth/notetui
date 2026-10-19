"""Main TUI application for note taking."""

from datetime import datetime
from pathlib import Path
import shutil

import pyperclip

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header, TextArea, Label, Static, Button
from textual.reactive import reactive

from notetui.notes import NoteManager
from notetui.carryover import carry_over, sync_earlier_copies
from notetui.calendar import Calendar
from notetui.todolist import GroupHeading, NoteGroup, TodoList, TodoItem
from notetui.search import SearchModalScreen
from notetui.vim_editor import VimTextArea, darker_terminal_background
from notetui.points import parse_point, parse_reminder
from notetui.reminder_prompt import ReminderPromptScreen


class NoteTUI(App):
    """A keyboard-driven TUI for daily markdown notes."""

    # Colours use the terminal's own ANSI palette (see the ansi-dark theme set in
    # __init__), so the app follows whatever theme the terminal is using.
    CSS = """
    Screen {
        background: ansi_default;
    }

    Header {
        background: ansi_default;
        color: ansi_blue;
        text-style: bold;
    }

    Footer {
        background: ansi_default;
    }

    Toast, Toast:ansi {
        background: $toast-background;
    }

    FooterKey .footer-key--key {
        color: ansi_blue;
        background: ansi_default;
    }

    FooterKey .footer-key--description {
        color: ansi_default;
        background: ansi_default;
    }

    #main-container {
        width: 100%;
        height: 100%;
    }

    #split-container {
        width: 100%;
        height: 100%;
    }

    #split-container.hide {
        display: none;
    }

    #editor-container {
        width: 2fr;
        height: 100%;
    }

    #todo-container {
        width: 1fr;
        height: 100%;
    }

    #info-bar {
        width: 100%;
        height: 3;
        padding: 0 2;
        color: ansi_blue;
        border: tall ansi_bright_black;
    }

    #calendar-container {
        width: 100%;
        height: 100%;
        display: none;
    }

    #calendar-container.show {
        display: block;
    }

    TextArea {
        width: 100%;
        height: 1fr;
        background: ansi_default;
        color: ansi_default;
        border: tall ansi_bright_black;
    }

    TextArea:focus {
        border: tall ansi_blue;
    }

    #status-text {
        text-align: left;
        content-align: left middle;
        color: ansi_blue;
        text-style: bold;
    }

    #file-path {
        text-align: right;
        content-align: right middle;
        color: ansi_bright_black;
    }

    #button-bar {
        width: 100%;
        height: auto;
        padding: 1;
        align: center middle;
    }

    .action-button {
        margin: 0 1;
        min-width: 16;
    }

    /* The buttons keep their original fixed colours (the terminal theme may
       have no real green or blue) */
    #save-button {
        background: #1a472a;
        color: #00ff88;
        border: tall #2d6a4f;
    }

    #save-button:hover {
        background: #2d6a4f;
    }

    #refresh-button {
        background: #1a3a5c;
        color: #00d4ff;
        border: tall #2d5a8a;
    }

    #refresh-button:hover {
        background: #2d5a8a;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+s", "save", "Save", priority=True),
        Binding("ctrl+n", "next_day", "Next Day", priority=True),
        Binding("ctrl+p", "prev_day", "Prev Day", priority=True),
        Binding("ctrl+f", "toggle_search", "Search", priority=True),
        Binding("ctrl+]", "next_week", "Next Week", priority=True),
        Binding("ctrl+[", "prev_week", "Prev Week", priority=True),
        Binding("ctrl+t", "today", "Today", priority=True),
        Binding("ctrl+k", "toggle_calendar", "Calendar", priority=True),
        Binding("ctrl+c", "copy_selection", "Copy", priority=True),
        Binding("ctrl+v", "paste", "Paste", priority=True),
        Binding("ctrl+h", "show_help", "Help", priority=True),
        Binding("ctrl+o", "toggle_fold_all", "Fold Todos", priority=True),
        Binding("ctrl+enter", "finish_todo_on_line", "Finish Todo", show=False),
        Binding("tab", "tab_day(1)", "Next Day Box", show=False, priority=True),
        Binding("shift+tab", "tab_day(-1)", "Previous Day Box", show=False, priority=True),
        Binding("escape", "escape", "Back", show=False),
    ]

    current_date: reactive[datetime] = reactive(datetime.now)
    show_calendar: reactive[bool] = reactive(False)

    def __init__(self, notes_dir: Path | None = None):
        """Initialize the NoteTUI app.

        Args:
            notes_dir: Directory to store notes. Defaults to ~/notes/
        """
        super().__init__()
        self.theme = "ansi-dark"
        self.note_manager = NoteManager(notes_dir)
        self.editor: VimTextArea | None = None
        self.calendar_widget: Calendar | None = None
        self.todo_list: TodoList | None = None
        self._previous_date: datetime | None = None
        self._content_dirty: bool = False
        # The open note as last loaded/saved, and a disk version we already warned about
        self._disk_text: str | None = None
        self._warned_disk: str | None = None
        # Fingerprint of all notes, so changes to other days refresh the todo list
        self._notes_stamp: tuple = ()
        self.current_date = datetime.now()
        # Before anything loads: bring unfinished points from earlier days into today
        self._carried_on_start = carry_over(self.note_manager, self.current_date)

    def get_theme_variable_defaults(self) -> dict[str, str]:
        """$note-background: the editor's darker shade, shared by the sidebar boxes.
        $toast-background: darker still, so notifications stand out over both."""
        return {
            "note-background": darker_terminal_background() or "ansi_default",
            "toast-background": darker_terminal_background(0.35) or "ansi_black",
        }

    def compose(self) -> ComposeResult:
        """Compose the TUI layout."""
        yield Header(show_clock=True)

        with Container(id="main-container"):
            with Horizontal(id="split-container"):
                with Vertical(id="editor-container"):
                    with Horizontal(id="info-bar"):
                        yield Label(self._get_status_text(), id="status-text")
                        yield Label(self._get_file_path(), id="file-path")
                    yield VimTextArea(
                        self.note_manager.get_note_content(self.current_date),
                        language="markdown",
                        show_line_numbers=True,
                    )
                    with Horizontal(id="button-bar"):
                        save_btn = Button("💾 Save", id="save-button", classes="action-button")
                        save_btn.can_focus = False
                        yield save_btn
                        refresh_btn = Button("🔄 Refresh", id="refresh-button", classes="action-button")
                        refresh_btn.can_focus = False
                        yield refresh_btn

                with Container(id="todo-container"):
                    yield TodoList(self.note_manager.notes_dir)

            with Container(id="calendar-container"):
                yield Calendar(self.current_date)

        yield Footer()

    def on_mount(self) -> None:
        """Handle mount event."""
        self.title = "NoteTUI - Daily Notes"
        self.sub_title = "Press Ctrl+H for help"
        self.editor = self.query_one(VimTextArea)
        self.calendar_widget = self.query_one(Calendar)
        self.todo_list = self.query_one(TodoList)
        # Track the initial date
        self._previous_date = self.current_date
        # Start autosave timer (every 60 seconds)
        self.set_interval(60, self._autosave)
        # Pick up entries added from outside (e.g. with notetui-add)
        self._disk_text = self._read_disk()
        self._notes_stamp = self._notes_dir_stamp()
        self.set_interval(1, self._check_external_change)
        # Move cursor to line 2 on startup
        if self.editor:
            self.editor.move_cursor((1, 0))
        # Scan for todos
        if self.todo_list:
            self.todo_list.scan_notes()
        # Update info bar to show vim mode
        self._update_info_bar()
        self._notify_carried(self._carried_on_start)

    def _notify_carried(self, count: int) -> None:
        if count:
            self.notify(f"↪ Carried over {count} unfinished point{'s' if count != 1 else ''}")

    def watch_current_date(self, new_date: datetime) -> None:
        """React to date changes."""
        if self.editor and self._previous_date and self.editor.text != self._known_text(self._previous_date):
            # Save unsaved edits to the PREVIOUS date before loading new content.
            # Untouched notes aren't rewritten, so changes made outside survive.
            self._write_note(self._previous_date, self.editor.text)
            # Refresh todo list after saving
            if self.todo_list:
                self.todo_list.scan_notes()

        # Arriving at today (e.g. after midnight): carry unfinished points over first
        if new_date.date() == datetime.now().date():
            carried = carry_over(self.note_manager, new_date)
            if carried and self.todo_list:
                self.todo_list.scan_notes()
            self._notify_carried(carried)

        # Load the new date's content
        if self.editor:
            self.editor.text = self.note_manager.get_note_content(new_date)
            self._disk_text = self._read_disk()
            self._update_info_bar()
            # Move cursor to line 2 (index 1, column 0)
            self.editor.move_cursor((1, 0))

        # Remember this date for next time
        self._previous_date = new_date
        # Reset dirty flag after loading new content
        self._content_dirty = False

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Track when content has been modified."""
        self._content_dirty = True

    def on_vim_text_area_mode_changed(self, event) -> None:
        """Update status bar when vim mode changes."""
        self._update_info_bar()

    def on_vim_text_area_point_changed(self, event: VimTextArea.PointChanged) -> None:
        """Save right away so the sidebar and the reminder service see the change."""
        self._save_current_note()
        self._content_dirty = False
        if event.toggled_text:
            # A carried-over point: tick off (or un-tick) its copies on earlier days
            synced = sync_earlier_copies(
                self.note_manager.notes_dir, self.current_date, event.toggled_text, event.checked
            )
            if synced and self.todo_list:
                self.todo_list.scan_notes()
        self.notify(event.description)

    def on_vim_text_area_reminder_requested(self, event: VimTextArea.ReminderRequested) -> None:
        """Ask for a reminder for the line the cursor is on."""
        if not self.editor:
            return
        row = event.row
        point = parse_point(self.editor.document.get_line(row))
        current = point.reminder.spec if point and point.reminder else ""

        def handle_reminder(value: str | None) -> None:
            if value is None or not self.editor:
                return
            reminder = parse_reminder(value) if value else None
            self.editor.set_reminder(row, reminder)
            self._save_current_note()
            self._content_dirty = False
            self.notify(f"⏰ Reminder {reminder.describe()}" if reminder else "Reminder removed")

        self.push_screen(ReminderPromptScreen(current), handle_reminder)

    def _autosave(self) -> None:
        """Autosave if content has changed."""
        if self._content_dirty and self.editor:
            self._save_current_note()
            self._content_dirty = False

    def watch_show_calendar(self, show: bool) -> None:
        """React to calendar visibility changes."""
        split_container = self.query_one("#split-container")
        calendar_container = self.query_one("#calendar-container")

        if show:
            split_container.add_class("hide")
            calendar_container.add_class("show")
            if self.calendar_widget:
                # Update calendar to current date and focus it
                self.calendar_widget.selected_date = self.current_date
                self.calendar_widget.display_date = self.current_date
                self.calendar_widget.refresh(recompose=True)
                self.calendar_widget.call_after_refresh(self.calendar_widget.focus_selected_date)
        else:
            calendar_container.remove_class("show")
            split_container.remove_class("hide")
            if self.editor:
                self.editor.focus()

    def _save_current_note(self) -> None:
        """Save the current note content to the current date."""
        if self.editor:
            self._write_note(self.current_date, self.editor.text)
            # Update the previous date tracker
            self._previous_date = self.current_date
            # Refresh todo list after saving
            if self.todo_list:
                self.todo_list.scan_notes()

    def _read_disk(self) -> str | None:
        """The current note's file as it is on disk, or None if it doesn't exist yet."""
        path = self.note_manager.get_note_path(self.current_date)
        try:
            return path.read_text()
        except OSError:
            return None

    def _known_text(self, date: datetime) -> str:
        """What the editor started from: the file as last seen, or the blank new-day note."""
        if self._disk_text is not None:
            return self._disk_text
        return self.note_manager._create_default_content(date)

    def _write_note(self, date: datetime, content: str) -> None:
        """Write content to the note for date.

        If the file changed on disk since it was loaded, the other version is
        copied to .conflicts/ first so neither side's changes are lost.
        """
        path = self.note_manager.get_note_path(date)
        try:
            disk = path.read_text()
        except OSError:
            disk = None
        if disk is not None and disk != self._disk_text and disk != content:
            conflicts_dir = self.note_manager.notes_dir / ".conflicts"
            conflicts_dir.mkdir(exist_ok=True)
            backup = conflicts_dir / f"{path.stem}.{datetime.now():%H%M%S}.md"
            shutil.copy2(path, backup)
            self.notify(f"The version on disk was saved to {backup}", severity="warning", timeout=10)
        self.note_manager.save_note_content(date, content)
        self._disk_text = content
        self._warned_disk = None

    def _notes_dir_stamp(self) -> tuple:
        """(name, mtime, size) of every note; changes when any note is added, removed or edited."""
        stamp = []
        for p in self.note_manager.notes_dir.glob("*.md"):
            try:
                st = p.stat()
            except OSError:
                continue
            stamp.append((p.name, st.st_mtime_ns, st.st_size))
        return tuple(sorted(stamp))

    def _check_external_change(self) -> None:
        """Watch the notes folder: refresh todos when any note changes, and merge
        changes to the open note."""
        stamp = self._notes_dir_stamp()
        if stamp != self._notes_stamp:
            self._notes_stamp = stamp
            if self.todo_list:
                self.todo_list.scan_notes()
        self._check_open_note()

    def _check_open_note(self) -> None:
        """Merge in changes made to the open note's file by something else.

        notetui-add only ever appends, so the usual case is: the file is what
        we last loaded or saved, plus new lines at the end. Those get added to
        the editor even while you're typing. Anything else is only reloaded
        when there's no unsaved typing to lose.
        """
        if not self.editor:
            return
        disk = self._read_disk()
        if disk is None or disk == self._disk_text or disk == self._warned_disk:
            return
        # What the editor started from: the file as last seen, or the blank
        # new-day note if the file didn't exist yet
        known = self._known_text(self.current_date)
        base = known.rstrip("\n")
        if self.editor.text == known:
            # Nothing unsaved: just load the new version
            cursor = self.editor.cursor_location
            self.editor.text = disk
            lines = disk.split("\n")
            row = min(cursor[0], len(lines) - 1)
            self.editor.move_cursor((row, min(cursor[1], len(lines[row]))))
        elif disk.startswith(base):
            # Unsaved typing, but the file only grew at the end: add that part
            content = self.editor.text.rstrip("\n").split("\n")
            end = (len(content) - 1, len(content[-1]))
            self.editor.read_only = False
            self.editor.replace(disk[len(base):], end, self.editor.document.end)
            self.editor.read_only = self.editor.vim_mode == "NORMAL"
        else:
            self.notify(
                "This note changed on disk. Press Refresh to load it (your unsaved typing would be lost), "
                "or save to keep your version (the one on disk is then kept in .conflicts/).",
                severity="warning",
                timeout=8,
            )
            # Keep _disk_text as it was, so saving knows to back this version up
            self._warned_disk = disk
            return
        self._disk_text = disk
        if self.todo_list:
            self.todo_list.scan_notes()
        self.notify("Note updated from outside")

    def _update_info_bar(self) -> None:
        """Update the information bar."""
        status_label = self.query_one("#status-text", Label)
        file_label = self.query_one("#file-path", Label)

        status_label.update(self._get_status_text())
        file_label.update(self._get_file_path())

    def _get_status_text(self) -> str:
        """Get the status text for the info bar."""
        day_name = self.current_date.strftime("%A")
        date_str = self.current_date.strftime("%d %b %Y")
        exists = "📝" if self.note_manager.note_exists(self.current_date) else "✨"
        mode = self.editor.vim_mode if self.editor and self.editor.vim_mode else "NORMAL"
        return f"-- {mode} -- {exists} {day_name}, {date_str}"

    def _get_file_path(self) -> str:
        """Get the file path for display."""
        path = self.note_manager.get_note_path(self.current_date)
        return str(path)

    def action_save(self) -> None:
        """Save the current note."""
        self._save_current_note()
        self._content_dirty = False
        self.notify("Note saved!", severity="information")

    def action_refresh(self) -> None:
        """Refresh the current note from disk."""
        if self.editor:
            self.editor.text = self.note_manager.get_note_content(self.current_date)
            self._disk_text = self._read_disk()
            self._update_info_bar()
            if self.todo_list:
                self.todo_list.scan_notes()
            self.notify("Note refreshed!", severity="information")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "save-button":
            self.action_save()
        elif event.button.id == "refresh-button":
            self.action_refresh()

    def action_next_day(self) -> None:
        """Navigate to the next day."""
        self.current_date = self.note_manager.get_next_day(self.current_date)
        self.notify(f"→ {self.current_date.strftime('%d %b %Y')}")

    def action_prev_day(self) -> None:
        """Navigate to the previous day."""
        self.current_date = self.note_manager.get_previous_day(self.current_date)
        self.notify(f"← {self.current_date.strftime('%d %b %Y')}")

    def action_next_week(self) -> None:
        """Navigate to the next week."""
        self.current_date = self.note_manager.get_next_week(self.current_date)
        self.notify(f"⇒ {self.current_date.strftime('%d %b %Y')}")

    def action_prev_week(self) -> None:
        """Navigate to the previous week."""
        self.current_date = self.note_manager.get_previous_week(self.current_date)
        self.notify(f"⇐ {self.current_date.strftime('%d %b %Y')}")

    def action_today(self) -> None:
        """Navigate to today."""
        self.current_date = datetime.now()
        self.notify(f"Today: {self.current_date.strftime('%d %b %Y')}")

    def action_toggle_calendar(self) -> None:
        """Toggle calendar view."""
        self.show_calendar = not self.show_calendar

    def action_copy_selection(self) -> None:
        """Copy selected text to clipboard."""
        if self.editor and self.editor.selected_text:
            pyperclip.copy(self.editor.selected_text)
            self.notify("Copied to clipboard")
        else:
            self.notify("No text selected", severity="warning")

    def action_paste(self) -> None:
        """Paste text from clipboard."""
        if self.editor:
            try:
                text = pyperclip.paste()
                if text:
                    self.editor.insert(text)
                else:
                    self.notify("Clipboard is empty", severity="warning")
            except Exception:
                self.notify("Could not access clipboard", severity="error")

    def action_toggle_search(self) -> None:
        """Open search modal."""
        def handle_search_result(result: tuple[datetime, int] | None) -> None:
            if result:
                date, line_number = result
                self.current_date = date
                if self.editor:
                    self.editor.move_cursor((line_number - 1, 0))
                    self.editor.focus()
                self.notify(f"Jumped to: {date.strftime('%d %b %Y')}")

        self.push_screen(SearchModalScreen(self.note_manager), handle_search_result)

    def action_escape(self) -> None:
        """Handle escape key."""
        if self.show_calendar:
            self.show_calendar = False
        else:
            # Return focus to editor when pressing escape in todo list
            if self.editor:
                self.editor.focus()

    def action_toggle_fold_all(self) -> None:
        """Fold or unfold every note's group in the todo sidebar."""
        if self.todo_list:
            self.todo_list.toggle_all()

    def action_tab_day(self, step: int) -> None:
        """Tab / Shift+Tab: move between the days in the sidebar, never onto single todos.

        From the note, Tab goes to the first day and Shift+Tab to the last; past
        either end it comes back to the note. Elsewhere (search, reminder
        prompt) Tab moves focus as usual.
        """
        focused = self.focused
        if isinstance(focused, (GroupHeading, TodoItem)) and isinstance(focused.parent, NoteGroup):
            focused.parent.tab_day(step)
        elif focused is self.editor and self.todo_list:
            headings = list(self.todo_list.query(GroupHeading).results())
            if headings:
                headings[0 if step > 0 else -1].focus()
        elif step > 0:
            self.screen.focus_next()
        else:
            self.screen.focus_previous()

    def action_finish_todo_on_line(self) -> None:
        """Finish the todo on the current cursor line by adding strikethrough."""
        if not self.editor:
            return

        # Get current cursor position
        cursor_row, cursor_col = self.editor.cursor_location

        # Get all lines
        lines = self.editor.text.split('\n')

        # Check if cursor is within valid range
        if 0 <= cursor_row < len(lines):
            line = lines[cursor_row].strip()

            # Check if line is a ## heading
            if line.startswith('##') and not line.startswith('###'):
                # Extract the todo text
                todo_text = line[2:].strip().rstrip('#').strip()

                # Check if already finished (has strikethrough)
                if todo_text.startswith('~~') and todo_text.endswith('~~'):
                    self.notify("Todo already finished!", severity="warning")
                    return

                # Get the original line with indentation
                original_line = lines[cursor_row]
                indent = original_line[:len(original_line) - len(original_line.lstrip())]

                # Replace with strikethrough version
                lines[cursor_row] = f"{indent}## ~~{todo_text}~~"

                # Update editor text
                self.editor.text = '\n'.join(lines)

                # Save and refresh todos
                self._save_current_note()

                self.notify(f"✓ Finished: {todo_text}", severity="information")
            else:
                self.notify("Cursor is not on a ## todo line", severity="warning")

    def action_quit(self) -> None:
        """Quit the application after saving."""
        self._save_current_note()
        self.exit()

    def action_show_help(self) -> None:
        """Show help screen."""
        help_text = """
# NoteTUI - Keyboard Shortcuts

## Navigation
- **Ctrl+N**: Next day
- **Ctrl+P**: Previous day
- **Ctrl+]**: Next week
- **Ctrl+[**: Previous week
- **Ctrl+T**: Go to today

## Search & Views
- **Ctrl+F**: Search notes
- **Ctrl+K**: Toggle calendar view
- **Escape**: Close search/calendar

## Points (NORMAL mode)
- **Space**: Make line a checkbox point / check / uncheck
- **Alt+Space** or **Backspace**: Remove the checkbox, keep the text
- **p0** … **p4**: Importance (0 = mega important, 4 = not important); same again clears
- **p5**: Daily item — never ticked off, comes back every day
- **t** (or **r**): Time reminder (01.30 = every 1h30m, 13:00 = daily at 13:00)
- **n**: Notes under the point (between >> and <<)
- **s**: Sort points by importance (most important first, done ones last)

Unfinished points move to today when you open it; the old day keeps them as - [>]

## Editing
- **Ctrl+S**: Save current note
- **Ctrl+C**: Copy selected text
- **Ctrl+V**: Paste from clipboard

## Todo sidebar
- **Tab**: Jump into the sidebar
- **Space** on a date: Fold / unfold that note's todos and points
- **Enter** on a date: Open that day
- **←** / **→** on a date: Fold / unfold
- **Ctrl+O**: Fold / unfold all notes
- **↑** / **↓**: Previous / next day, **Shift+↑** / **Shift+↓**: Between that day's todos
- **Enter** on a todo: Open that day
- **Ctrl+D** on a todo: Mark it done

## Other
- **Ctrl+H**: Show this help
- **Ctrl+Q**: Quit application

## In Calendar View
- **Arrow Keys**: Navigate between days
- **Enter**: Select focused date
- **{** / **}**: Previous/Next month
- Click to select a date

---
Notes are saved to: ~/notes/
Format: DD-MMM-YYYY.md (e.g., 21-Nov-2025.md)
"""
        self.notify(help_text, timeout=10, severity="information")

    def on_calendar_date_selected(self, message: Calendar.DateSelected) -> None:
        """Handle date selection from calendar."""
        self.current_date = message.date
        self.show_calendar = False
        self.notify(f"Selected: {message.date.strftime('%d %b %Y')}")

    def on_todo_item_selected(self, message: TodoItem.Selected) -> None:
        """Handle todo item selection - jump to that date."""
        # Parse the date string (format: "DD-MMM-YYYY")
        try:
            selected_date = datetime.strptime(message.date_str, "%d-%b-%Y")
            self.current_date = selected_date
            # Return focus to editor and position cursor on line 2
            if self.editor:
                self.editor.move_cursor((1, 0))
                self.editor.focus()
            self.notify(f"Jumped to: {selected_date.strftime('%d %b %Y')}")
        except ValueError:
            self.notify("Could not parse date", severity="error")

    def on_todo_list_todo_file_updated(self, message: TodoList.TodoFileUpdated) -> None:
        """Handle todo file update - reload editor if viewing that file."""
        # Check if the updated file is the current date's file
        current_file = self.note_manager.get_note_path(self.current_date)
        if message.file_path == current_file and self.editor:
            # Save cursor position
            cursor_pos = self.editor.cursor_location
            # Reload the file content
            self.editor.text = self.note_manager.get_note_content(self.current_date)
            self._disk_text = self._read_disk()
            # Restore cursor position
            self.editor.move_cursor(cursor_pos)

def main():
    """Entry point for the application."""
    app = NoteTUI()
    app.run()


if __name__ == "__main__":
    main()
