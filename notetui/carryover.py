"""Carry unfinished points over to today's note.

Every open point (- [ ]) in an earlier day's note moves to today, together
with its importance, reminder and notes block. The earlier day keeps the
point marked as moved (- [>]) so its history stays readable, while only
today's copy shows in the sidebar and sends reminders. Checked points stay
where they are.
"""

from datetime import datetime
from pathlib import Path

from notetui.notes import NoteManager
from notetui.points import notes_end, parse_point


def carry_over(note_manager: NoteManager, today: datetime) -> int:
    """Move open points from earlier days into today's note. Returns how many moved."""
    today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
    earlier = []
    for note_file in note_manager.notes_dir.glob("*.md"):
        try:
            file_date = datetime.strptime(note_file.stem, "%d-%b-%Y")
        except ValueError:
            continue
        if file_date < today_start:
            earlier.append((file_date, note_file))
    earlier.sort()

    carried: list[str] = []
    count = 0
    for _, note_file in earlier:
        try:
            lines = note_file.read_text().split("\n")
        except OSError:
            continue
        changed = False
        row = 0
        while row < len(lines):
            point = parse_point(lines[row])
            if point is None or not point.is_open:
                row += 1
                continue
            end = notes_end(lines, row)
            # Take the point and its notes, shifted to the left margin,
            # one blank line apart from the previous carried point
            if carried:
                carried.append("")
            carried.extend(
                line[len(point.indent):] if line.startswith(point.indent) else line.lstrip()
                for line in lines[row:end]
            )
            point.moved = True
            lines[row] = point.format()
            changed = True
            count += 1
            row = end
        if changed:
            note_file.write_text("\n".join(lines))

    if not carried:
        return 0

    # Today's points go right under its title line
    lines = note_manager.get_note_content(today).split("\n")
    insert_at = 0
    if lines and lines[0].startswith("#"):
        insert_at = 1
        if len(lines) > 1 and not lines[1].strip():
            insert_at = 2
        else:
            carried.insert(0, "")
    if insert_at < len(lines) and lines[insert_at].strip():
        carried.append("")
    lines[insert_at:insert_at] = carried
    note_manager.save_note_content(today, "\n".join(lines))
    return count


def sync_earlier_copies(notes_dir: Path, before: datetime, text: str, done: bool) -> list[Path]:
    """Tick off (or un-tick) the copies a carried-over point left on earlier days.

    Checking a point turns its moved copies (- [>]) on earlier days into
    checked ones; unchecking turns them back into moved. Copies are matched by
    the point's text. Returns the files that changed.
    """
    day_start = before.replace(hour=0, minute=0, second=0, microsecond=0)
    changed_files = []
    for note_file in notes_dir.glob("*.md"):
        try:
            if datetime.strptime(note_file.stem, "%d-%b-%Y") >= day_start:
                continue
            lines = note_file.read_text().split("\n")
        except (ValueError, OSError):
            continue
        changed = False
        for row, line in enumerate(lines):
            point = parse_point(line)
            if point is None or point.text != text:
                continue
            if done and point.moved:
                point.moved, point.checked = False, True
            elif not done and point.checked:
                point.moved, point.checked = True, False
            else:
                continue
            lines[row] = point.format()
            changed = True
        if changed:
            note_file.write_text("\n".join(lines))
            changed_files.append(note_file)
    return changed_files
