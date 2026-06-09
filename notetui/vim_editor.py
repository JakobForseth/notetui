"""Vim-style modal editing for TextArea."""

from textual.message import Message
from textual.widgets import TextArea
from textual.reactive import reactive


class VimTextArea(TextArea):
    """TextArea subclass with vim-style normal/insert modes."""

    class ModeChanged(Message):
        """Posted when vim mode changes."""

        def __init__(self, mode: str) -> None:
            super().__init__()
            self.mode = mode

    vim_mode: reactive[str] = reactive("NORMAL")

    def watch_vim_mode(self, new_mode: str) -> None:
        """Post message when mode changes."""
        self.post_message(self.ModeChanged(new_mode))

    def on_mount(self) -> None:
        """Start in normal mode."""
        self._pending_key: str | None = None
        self._enter_normal_mode()

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

        # Multi-key starters
        elif character == "g":
            self._pending_key = "g"
        elif character == "d":
            self._pending_key = "d"

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
