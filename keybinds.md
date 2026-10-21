# NoteTUI - Vim Keybindings

## Modes

| Key | Action | Key | Action |
|-----|--------|-----|--------|
| `i` | INSERT before cursor | `A` | INSERT at end of line |
| `a` | INSERT after cursor | `I` | INSERT at first non-whitespace |
| `o` | New line below, INSERT | `O` | New line above, INSERT |
| `Escape` | Back to NORMAL | | |

## Movement (NORMAL)

| Key | Action | Key | Action |
|-----|--------|-----|--------|
| `h`/`l` | Left / Right | `0` | Start of line |
| `j`/`k` | Down / Up | `$` | End of line |
| `w` | Next word | `gg` | Top of file |
| `b` | Previous word | `G` | Bottom of file |
| `e` | End of word | `Tab` | Next day in todo list |

## Editing (NORMAL)

| Key | Action | Key | Action |
|-----|--------|-----|--------|
| `x` | Delete char | `dd` | Delete line |
| `u` | Undo | `Ctrl+R` | Redo |

## App Shortcuts (both modes)

| Key | Action | Key | Action |
|-----|--------|-----|--------|
| `Ctrl+S` | Save | `Ctrl+F` | Search notes |
| `Ctrl+N` | Next day | `Ctrl+K` | Toggle calendar |
| `Ctrl+P` | Previous day | `Ctrl+C` | Copy selection (on a todo: the whole todo) |
| `Ctrl+]` | Next week | `Ctrl+V` | Paste |
| `Ctrl+[` | Previous week | `Ctrl+H` | Help |
| `Ctrl+T` | Go to today | `Ctrl+Q` | Quit |

## Mouse

| Action | Result |
|--------|--------|
| Double-click a todo | Jump to it in the note |
| Double-click `MYMAS-1234` / `AUTEL-123` (note or todo list) | Open the issue in the browser |
