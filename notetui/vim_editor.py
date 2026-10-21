"""Vim-style modal editing for TextArea."""

import dataclasses
from pathlib import Path

from rich.style import Style
from textual.message import Message
from textual.widgets import TextArea
from textual.widgets.text_area import TextAreaTheme
from textual.reactive import reactive

from notetui.links import ISSUE_KEY, issue_at, issue_url
from notetui.points import (
    NOTES_CLOSE,
    NOTES_OPEN,
    PRIORITY_COLORS,
    notes_end,
    parse_point,
    point_spans,
    remove_checkbox,
    sort_points,
    to_point,
)

# Ghostty's colours for the current Omarchy theme
OMARCHY_GHOSTTY_THEME = Path.home() / ".local/state/omarchy/current/theme/ghostty.conf"


def darker_terminal_background(factor: float = 0.65) -> str | None:
    """The terminal's background colour, darkened, or None if it can't be found.

    Read at startup, so it follows Omarchy theme changes the next time the app opens.
    """
    try:
        for line in OMARCHY_GHOSTTY_THEME.read_text().splitlines():
            key, _, value = line.partition("=")
            value = value.strip()
            if key.strip() == "background" and len(value) == 7 and value.startswith("#"):
                rgb = [int(value[i:i + 2], 16) for i in (1, 3, 5)]
                return "#" + "".join(f"{round(c * factor):02x}" for c in rgb)
    except (OSError, ValueError):
        pass
    return None


# Editor colours, as ANSI names so they follow the terminal
NOTE_THEME = TextAreaTheme(
    name="notetui",
    syntax_styles={
        "heading": Style(color="blue", bold=True),
        "point.box": Style(color="bright_black"),
        "point.box.done": Style(color="green"),
        "point.text.done": Style(color="bright_black", strike=True),
        "reminder": Style(color="blue", italic=True),
        "point.moved": Style(color="bright_black", italic=True),
        "notes.marker": Style(color="bright_black"),
        "notes.text": Style(italic=True),
        "issue": Style(color="cyan", underline=True),
        **{
            f"priority.{level}": Style(color="black", bgcolor=color, bold=True)
            for level, color in PRIORITY_COLORS.items()
        },
    },
)


class VimTextArea(TextArea):
    """TextArea subclass with vim-style normal/insert modes."""

    class ModeChanged(Message):
        """Posted when vim mode changes."""

        def __init__(self, mode: str) -> None:
            super().__init__()
            self.mode = mode

    class PointChanged(Message):
        """Posted after a point was toggled, prioritised, sorted or un-pointed."""

        def __init__(self, description: str, toggled_text: str | None = None, checked: bool = False) -> None:
            super().__init__()
            self.description = description
            self.toggled_text = toggled_text
            """Set when a point was checked/unchecked, so earlier copies can follow."""
            self.checked = checked

    class ReminderRequested(Message):
        """Posted when the user asks to set a reminder on the current line."""

        def __init__(self, row: int) -> None:
            super().__init__()
            self.row = row

    vim_mode: reactive[str] = reactive("NORMAL")

    def watch_vim_mode(self, new_mode: str) -> None:
        """Post message when mode changes."""
        self.post_message(self.ModeChanged(new_mode))

    def on_mount(self) -> None:
        """Start in normal mode."""
        self._pending_key: str | None = None
        # Slightly darker than the terminal so the note stands out. It has to be
        # the theme's base style: TextArea resets its own background otherwise.
        theme = NOTE_THEME
        background = darker_terminal_background()
        if background:
            theme = dataclasses.replace(theme, base_style=Style(color="default", bgcolor=background))
        self.register_theme(theme)
        self.theme = theme.name
        self._enter_normal_mode()

    def _build_highlight_map(self) -> None:
        """Colour headings and the parts of each point (box, importance, reminder, notes).

        There's no tree-sitter here, so this replaces the markdown highlighting
        TextArea would otherwise do. Highlight columns are UTF-8 byte offsets.
        """
        super()._build_highlight_map()
        highlights = self._highlights
        lines = self.text.split("\n")
        row = 0
        while row < len(lines):
            line = lines[row]
            if line.startswith("#"):
                highlights[row].append((0, None, "heading"))
                row += 1
                continue
            for start, end, name in point_spans(line):
                highlights[row].append(
                    (len(line[:start].encode()), len(line[:end].encode()), name)
                )
            end = notes_end(lines, row) if parse_point(line) else row + 1
            if end > row + 1:
                # The point's notes: faint >> and << lines, italic text between
                highlights[row + 1].append((0, None, "notes.marker"))
                for note_row in range(row + 2, end - 1):
                    highlights[note_row].append((0, None, "notes.text"))
                highlights[end - 1].append((0, None, "notes.marker"))
            row = end
        # Issue keys look like links; double-click opens them (see _on_click)
        for row, line in enumerate(lines):
            for match in ISSUE_KEY.finditer(line):
                highlights[row].append(
                    (len(line[:match.start()].encode()), len(line[:match.end()].encode()), "issue")
                )

    def _on_click(self, event) -> None:
        """Double-click on an issue key (MYMAS-1234) opens it in the browser."""
        if event.chain >= 2:
            row, column = self.get_target_document_location(event)
            key = issue_at(self.document.get_line(row), column)
            if key:
                event.stop()
                self.app.open_url(issue_url(key))

    def _enter_normal_mode(self) -> None:
        """Switch to normal mode."""
        self.vim_mode = "NORMAL"
        self.read_only = True

    def _enter_insert_mode(self) -> None:
        """Switch to insert mode."""
        self.vim_mode = "INSERT"
        self.read_only = False

    def _on_key(self, event) -> None:
        """Intercept keys for vim modal behavior."""
        key = event.key

        # Handle ctrl+r for redo in normal mode
        if key == "ctrl+r" and self.vim_mode == "NORMAL":
            event.stop()
            event.prevent_default()
            self.read_only = False
            self.action_redo()
            self.read_only = True
            return

        # Alt+Space removes the checkbox (only reaches us on terminals that send it
        # distinctly; most send plain Space, so Backspace does the same in NORMAL mode)
        if key == "alt+space" and self.vim_mode == "NORMAL":
            event.stop()
            event.prevent_default()
            self._remove_checkbox()
            return

        # Never intercept ctrl+ combos or tab — let them bubble to app bindings
        if key.startswith("ctrl+") or key in ("tab", "shift+tab"):
            return

        if self.vim_mode == "NORMAL":
            event.stop()
            event.prevent_default()
            self._handle_normal_key(key, event.character)
        else:
            # INSERT mode
            if key == "escape":
                event.stop()
                event.prevent_default()
                self._enter_normal_mode()
            else:
                # Let TextArea handle it normally
                super()._on_key(event)

    def _handle_normal_key(self, key: str, character: str | None) -> None:
        """Process a key press in normal mode."""
        # Handle pending multi-key commands
        if self._pending_key is not None:
            self._handle_pending(key, character)
            return

        # Single-key motions
        if key == "escape":
            return  # Already in normal mode

        # Mode switching
        if character == "i":
            self._enter_insert_mode()
        elif character == "a":
            self.action_cursor_right()
            self._enter_insert_mode()
        elif character == "A":
            self.action_cursor_line_end()
            self._enter_insert_mode()
        elif character == "I":
            self._move_to_first_non_whitespace()
            self._enter_insert_mode()
        elif character == "o":
            self.action_cursor_line_end()
            self.read_only = False
            self.insert("\n")
            self._enter_insert_mode()
        elif character == "O":
            self.action_cursor_line_start()
            self.read_only = False
            self.insert("\n")
            self.action_cursor_up()
            self._enter_insert_mode()

        # Movement
        elif key == "h" or key == "left":
            self.action_cursor_left()
        elif key == "j" or key == "down":
            self.action_cursor_down()
        elif key == "k" or key == "up":
            self.action_cursor_up()
        elif key == "l" or key == "right":
            self.action_cursor_right()
        elif character == "w":
            self.action_cursor_word_right()
        elif character == "b":
            self.action_cursor_word_left()
        elif character == "e":
            self.action_cursor_word_right()
            self.action_cursor_left()
        elif character == "0" or key == "home":
            self.action_cursor_line_start()
        elif character == "$" or key == "end":
            self.action_cursor_line_end()
        elif character == "G":
            self._move_to_bottom()

        # Points
        elif key == "space":
            self._toggle_point()
        elif key == "backspace":
            self._remove_checkbox()
        elif character in ("t", "r"):  # t for time; r (reminder) still works
            self.post_message(self.ReminderRequested(self.cursor_location[0]))
        elif character == "n":
            self._edit_notes()
        elif character == "s":
            self._sort_points()

        # Multi-key starters
        elif character == "g":
            self._pending_key = "g"
        elif character == "d":
            self._pending_key = "d"
        elif character == "p":
            self._pending_key = "p"

        # Editing
        elif character == "x":
            self.read_only = False
            self.action_delete_right()
            self.read_only = True
        elif character == "u":
            self.read_only = False
            self.action_undo()
            self.read_only = True

    def _handle_pending(self, key: str, character: str | None) -> None:
        """Handle the second key of a multi-key command."""
        pending = self._pending_key
        self._pending_key = None

        if pending == "g" and character == "g":
            self.move_cursor((0, 0))
        elif pending == "d" and character == "d":
            self._delete_current_line()
        elif pending == "p" and character is not None and character in "012345":
            self._set_priority(int(character))

    def _replace_line(self, row: int, new_line: str) -> None:
        """Replace one line, keeping the cursor at the same spot in the text."""
        old_line = self.document.get_line(row)
        cursor_row, cursor_col = self.cursor_location
        self.read_only = False
        self.replace(new_line, (row, 0), (row, len(old_line)), maintain_selection_offset=False)
        self.read_only = self.vim_mode == "NORMAL"
        if cursor_row == row:
            shift = len(new_line) - len(old_line)
            self.move_cursor((row, max(0, min(len(new_line), cursor_col + shift))))
        else:
            self.move_cursor((cursor_row, cursor_col))

    def _toggle_point(self) -> None:
        """Space: make the line a point, or check/uncheck an existing point."""
        row, _ = self.cursor_location
        line = self.document.get_line(row)
        point = parse_point(line)
        if point is None:
            point = to_point(line)
            self._replace_line(row, point.format())
            if not point.text:
                # Empty line became an empty point: start typing its text
                self.move_cursor((row, len(point.format())))
                self._enter_insert_mode()
                return
            self.post_message(self.PointChanged("Point added"))
        elif point.moved:
            self.app.notify("This point moved on to a later day — tick it off there", severity="warning")
        elif point.is_daily:
            self.app.notify("↻ Daily item — it comes back every day, nothing to tick off")
        else:
            point.checked = not point.checked
            self._replace_line(row, point.format())
            self.post_message(self.PointChanged(
                "✓ Done" if point.checked else "Unchecked", point.text, point.checked
            ))

    def _sort_points(self) -> None:
        """s: sort the note's points by importance, most important first."""
        lines = self.text.split("\n")
        sorted_lines = sort_points(lines)
        if sorted_lines == lines:
            self.app.notify("Points are already sorted by importance")
            return
        row, column = self.cursor_location
        current = lines[row]
        self.read_only = False
        self.replace("\n".join(sorted_lines), (0, 0), self.document.end)
        self.read_only = True
        # Keep the cursor on the line it was on
        new_row = sorted_lines.index(current) if current in sorted_lines else row
        self.move_cursor((new_row, min(column, len(current))))
        self.post_message(self.PointChanged("Sorted by importance"))

    def _edit_notes(self) -> None:
        """n: start typing notes under the point (adds a >> << block if there isn't one)."""
        row, _ = self.cursor_location
        line = self.document.get_line(row)
        if parse_point(line) is None:
            self._replace_line(row, to_point(line).format())
            line = self.document.get_line(row)
        point = parse_point(line)
        indent = point.indent + "  "
        lines = self.text.split("\n")
        end = notes_end(lines, row)
        self.read_only = False
        if end == row + 1:
            self.insert(f"\n{indent}{NOTES_OPEN}\n{indent}\n{indent}{NOTES_CLOSE}", (row, len(line)))
            self.move_cursor((row + 2, len(indent)))
        else:
            # Already has notes: continue after the last one, or on an empty last line
            last = end - 2
            if lines[last].strip() and lines[last].strip() != NOTES_OPEN:
                self.insert(f"{indent}\n", (end - 1, 0))
                last = end - 1
            self.move_cursor((last, len(self.document.get_line(last))))
        self._enter_insert_mode()

    def _remove_checkbox(self) -> None:
        """Alt+Space / Backspace: turn a point back into a plain line."""
        row, _ = self.cursor_location
        line = self.document.get_line(row)
        if parse_point(line) is None:
            return
        self._replace_line(row, remove_checkbox(line))
        self.post_message(self.PointChanged("Checkbox removed"))

    def _set_priority(self, priority: int) -> None:
        """p0–p4: set importance; the same number again clears it."""
        row, _ = self.cursor_location
        point = to_point(self.document.get_line(row))
        if point.priority == priority:
            point.priority = None
            description = "Importance cleared"
        else:
            point.priority = priority
            description = f"Importance {priority}"
        self._replace_line(row, point.format())
        self.post_message(self.PointChanged(description))

    def set_reminder(self, row: int, reminder) -> None:
        """Set (or with None, clear) the reminder on a line, making it a point."""
        point = to_point(self.document.get_line(row))
        point.reminder = reminder
        self._replace_line(row, point.format())

    def _move_to_first_non_whitespace(self) -> None:
        """Move cursor to first non-whitespace character on current line."""
        row, _ = self.cursor_location
        lines = self.text.split("\n")
        if row < len(lines):
            line = lines[row]
            col = len(line) - len(line.lstrip())
            self.move_cursor((row, col))

    def _move_to_bottom(self) -> None:
        """Move cursor to the last line."""
        lines = self.text.split("\n")
        last_row = max(0, len(lines) - 1)
        self.move_cursor((last_row, 0))

    def _delete_current_line(self) -> None:
        """Delete the current line."""
        self.read_only = False
        row, _ = self.cursor_location
        lines = self.text.split("\n")
        if row < len(lines):
            lines.pop(row)
            self.text = "\n".join(lines)
            # Keep cursor at same row or move up if at end
            new_row = min(row, max(0, len(lines) - 1))
            self.move_cursor((new_row, 0))
        self.read_only = True
