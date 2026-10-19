# NoteTUI

A keyboard-driven terminal application (TUI) for daily markdown notes.

## What is NoteTUI?

NoteTUI is a terminal-based note-taking application that lets you write daily notes in markdown format. Each day gets its own file, and you can easily navigate between days using keyboard shortcuts.

### Features

- **Daily notes** - Automatic filename based on date (`DD-Mmm-YYYY.md`)
- **Markdown editor** - Syntax highlighting and line numbering
- **Fuzzy search** - Search across all notes with `Ctrl+F`
- **Calendar view** - Visual navigation between dates
- **Todo list** - Collects all `##` headings from your notes
- **Points** - Checkbox points with importance, notes, reminders and carry-over to the next day
- **Keyboard-driven** - Fast navigation without mouse
- **Norwegian language** - Dates and weekdays in Norwegian
- **Auto-save** - Notes are saved automatically when navigating
- **Terminal colours** - Uses the terminal's own ANSI palette, so it matches your terminal

## Installation

### Requirements

- Python 3.10 or newer
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### With uv (recommended)

```bash
# Install directly from GitHub
uv tool install git+https://github.com/gomoz/notetui.git

# Or clone and install locally
git clone https://github.com/gomoz/notetui.git
cd notetui
uv tool install -e .
```

### With pip

```bash
git clone https://github.com/gomoz/notetui.git
cd notetui
pip install .
```

## Usage

Start the application:

```bash
notetui
```

Notes are stored in `~/notes/`.

### Run as Web App

You can also run NoteTUI in your browser using textual-serve:

```bash
# Install textual-serve
uv add textual-serve

# Run locally (localhost only)
uv run python -c "from textual_serve.server import Server; Server('uv run notetui').serve()"

# Run with remote access (accessible from other devices)
uv run python -c "from textual_serve.server import Server; Server('uv run notetui', host='0.0.0.0').serve()"
```

Then open http://localhost:8000 in your browser.

**Note**: In web mode, use the Save and Refresh buttons at the bottom of the editor (keyboard shortcuts may be intercepted by the browser).

## Keyboard Shortcuts

### Navigation

| Key | Action |
|-----|--------|
| `Ctrl+N` | Next day |
| `Ctrl+P` | Previous day |
| `Ctrl+]` | Next week |
| `Ctrl+[` | Previous week |
| `Ctrl+T` | Go to today |

### Search & Views

| Key | Action |
|-----|--------|
| `Ctrl+F` | Search all notes |
| `Ctrl+K` | Show/hide calendar |
| `Tab` / `Shift+Tab` | Next / previous day in the todo list (back to the note past the end) |
| `Ctrl+O` | Fold / unfold all days in the todo list |
| `Escape` | Close search/calendar |

### Editing

| Key | Action |
|-----|--------|
| `Ctrl+S` | Save note |
| `Ctrl+C` | Copy selected text |
| `Ctrl+V` | Paste from clipboard |
| `Ctrl+D` | Mark todo as done (in todo list) |
| `Ctrl+Enter` | Mark todo on line as done (in editor) |

### Other

| Key | Action |
|-----|--------|
| `Ctrl+H` | Show help |
| `Ctrl+Q` | Quit |

### In calendar view

| Key | Action |
|-----|--------|
| Arrow keys | Navigate between days |
| `Enter` | Select date |
| `{` / `}` | Previous/next month |

## Todo Feature

All `##` headings in your notes are shown as todos in the side panel:

```markdown
# monday, 01 december 2025

## Buy groceries
Get milk and bread

## Call the doctor
```

Todos are grouped in one box per day, newest first. Folded days are remembered
between runs (in `~/.local/state/notetui/collapsed.json`).

- Press `Tab` / `Shift+Tab` to move between days (and back to the note)
- Press `Space` (or `←` / `→`) on a day to fold / unfold it, `Ctrl+O` for all days
- Press `↑` / `↓` to move between days, `Shift+↑` / `Shift+↓` between a day's todos
- Press `Enter` to jump to the date for a todo
- Press `Ctrl+D` to mark a todo as done (adds ~~strikethrough~~)

## Points

Checkbox points live in the note itself, as markdown checkboxes. In NORMAL mode:

| Key | Action |
|-----|--------|
| `Space` | Make the line a point / check / uncheck it |
| `Backspace` | Remove the checkbox, keep the text |
| `p0` … `p4` | Set importance (0 = mega important, 4 = not important); the same number again clears it |
| `p5` | Daily item: never ticked off, comes back every day |
| `t` (or `r`) | Set a reminder: `01.30` = every 1h30m, `13:00` = every day at 13:00 (empty removes it) |
| `n` | Write notes under the point (between `>>` and `<<` lines) |
| `s` | Sort the points by importance (open ones first) |

```markdown
- [ ] !0 call the supplier @01.30
  >>
  ask about the brake pads
  <<
- [x] !2 order brake pads
```

Open points show in the todo list, sorted by importance. When you open
today's note, unfinished points from earlier days move to it; the earlier
day keeps them marked as moved (`- [>]`), and ticking one off later also
ticks off those earlier copies.

### Reminders

Reminders are sent by a small background service, `notetui-reminders`, so
they keep coming while NoteTUI is closed. It checks `~/notes/` every 20
seconds and sends a desktop notification (`notify-send`) with a sound
(`pw-play`, PipeWire) for each due reminder on an open point. A reminder
stops once its point is checked. Linux only for now.

```bash
# After installing with uv tool (puts notetui-reminders in ~/.local/bin):
mkdir -p ~/.config/systemd/user
cp systemd/notetui-reminders.service ~/.config/systemd/user/
systemctl --user enable --now notetui-reminders

notetui-reminders --demo   # hear the sound for each importance level
```

### Adding from the command line

`notetui-add` appends a point or a line of text to the end of today's note.
A running NoteTUI picks it up within a second, without losing unsaved typing.

```bash
notetui-add "p0: call the supplier, r 13:00, n ask about the brake pads"
notetui-add "just a line of text"
notetui-add --point "order brake pads" --importance 2 --reminder 01.30
```

Comma-separated parts, in any order: `p` / `p0`…`p5` (a point, with
importance), `r` / `t` (reminder), `n` (notes under the point); anything
else is plain text. `NOTETUI_NOTES_DIR` overrides `~/notes/`.

## Search Feature

Press `Ctrl+F` to open the fuzzy search modal:

- Search across all your notes (content and headings)
- Results update as you type
- Use arrow keys to navigate results
- Press `Enter` to jump to the selected result
- Press `Escape` to close the search

## Technology

- [Textual](https://textual.textualize.io/) - Modern Python TUI framework
- Python 3.10+

## License

MIT License
