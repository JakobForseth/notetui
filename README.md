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
