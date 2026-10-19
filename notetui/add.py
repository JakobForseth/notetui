"""Add a point or a line of text to today's note from the command line.

    notetui-add "p0: sjekk dette, r 13:00, n sjekk disse detaljene"

Parts are separated by commas and can come in any order:

    p / point          a point (no importance)
    p0 … p5 / point0   a point with importance 0–4, or 5 for a daily item
    r / t / time       a reminder: 13:00 = every day at 13:00, 01.30 = every 1h30m
    n / note           notes under the point
    anything else      plain text (a point instead, if a reminder or note is given)

A ':' after the keyword is optional (p0: text). The entry is appended to the
end of today's note; a running NoteTUI picks it up within a second.
"""

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from notetui.notes import NoteManager
from notetui.points import NOTES_CLOSE, NOTES_OPEN, Point, parse_reminder

POINT_PART = re.compile(r"^(?:point|p)(?P<priority>[0-5])?\s*:?\s+(?P<text>.+)$", re.IGNORECASE | re.DOTALL)
REMINDER_PART = re.compile(r"^(?:time|r|t)\s*:?\s*(?P<spec>\d{1,2}[.:]\d{2})$", re.IGNORECASE)
NOTE_PART = re.compile(r"^(?:note|n)\s*:?\s+(?P<text>.+)$", re.IGNORECASE | re.DOTALL)

class AddError(ValueError):
    pass


def parse_parts(raw: str) -> dict:
    """Parse the free-form input into point text, importance, reminder, notes and plain text.

    A comma part that doesn't start with a keyword continues the text before it
    (so text may contain commas); after a reminder, it's text of its own.
    """
    entry = {"point": None, "priority": None, "reminder": None, "note": None, "text": []}
    last = None  # where the previous part's text went: "point", "note" or "text"
    for part in raw.strip().split(","):
        part = part.strip()
        if not part:
            continue
        if match := POINT_PART.match(part):
            if entry["point"] is not None:
                raise AddError("only one point per command (run it again for the next one)")
            entry["point"] = match.group("text").strip()
            if match.group("priority") is not None:
                entry["priority"] = int(match.group("priority"))
            last = "point"
        elif match := REMINDER_PART.match(part):
            reminder = parse_reminder(match.group("spec"))
            if reminder is None:
                raise AddError(f"'{match.group('spec')}' isn't a valid time (use 13:00 or 01.30)")
            entry["reminder"] = reminder
            last = None
        elif match := NOTE_PART.match(part):
            entry["note"] = match.group("text").strip()
            last = "note"
        elif last in ("point", "note"):
            entry[last] += ", " + part
        elif last == "text":
            entry["text"][-1] += ", " + part
        else:
            entry["text"].append(part)
            last = "text"
    return entry


def build_lines(entry: dict) -> list[str]:
    """The note lines for a parsed entry."""
    plain = ", ".join(entry["text"])
    is_point = entry["point"] is not None or entry["reminder"] or entry["note"] or entry["priority"] is not None
    if not is_point:
        if not plain:
            raise AddError("nothing to add")
        return [plain]
    text = entry["point"] if entry["point"] is not None else plain
    if not text:
        raise AddError("the point needs some text")
    point = Point(indent="", checked=False, text=text, priority=entry["priority"], reminder=entry["reminder"])
    lines = [point.format()]
    if entry["note"]:
        lines += [f"  {NOTES_OPEN}", *(f"  {line}" for line in entry["note"].split("\n")), f"  {NOTES_CLOSE}"]
    return lines


def append_to_today(note_manager: NoteManager, new_lines: list[str], today: datetime) -> Path:
    """Append to the end of today's note, one blank line after what's there."""
    lines = note_manager.get_note_content(today).rstrip("\n").split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    lines += ["", *new_lines, ""]
    note_manager.save_note_content(today, "\n".join(lines))
    return note_manager.get_note_path(today)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="notetui-add",
        description="Add a point or text to today's note.",
        epilog='Free-form: notetui-add "p0: sjekk dette, r 13:00, n sjekk disse detaljene"',
    )
    parser.add_argument("input", nargs="*", help="free-form input (see module docstring)")
    parser.add_argument("--point", help="point text")
    parser.add_argument("--importance", type=int, choices=range(6), help="importance 0–4, 5 = daily item")
    parser.add_argument("--reminder", help="13:00 (daily) or 01.30 (interval)")
    parser.add_argument("--note", help="notes under the point")
    parser.add_argument("--text", help="plain text line")
    parser.add_argument("--notes-dir", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()

    try:
        entry = parse_parts(" ".join(args.input))
        # Explicit flags override the free-form parts
        if args.point is not None:
            entry["point"] = args.point
        if args.importance is not None:
            entry["priority"] = args.importance
        if args.reminder is not None:
            entry["reminder"] = parse_reminder(args.reminder)
            if entry["reminder"] is None:
                raise AddError(f"'{args.reminder}' isn't a valid time (use 13:00 or 01.30)")
        if args.note is not None:
            entry["note"] = args.note
        if args.text is not None:
            entry["text"].append(args.text)
        new_lines = build_lines(entry)
    except AddError as e:
        print(f"notetui-add: {e}", file=sys.stderr)
        sys.exit(2)

    notes_dir = args.notes_dir
    if notes_dir is None and (env := os.environ.get("NOTETUI_NOTES_DIR")):
        notes_dir = Path(env)
    path = append_to_today(NoteManager(notes_dir), new_lines, datetime.now())
    print(f"Added to {path}:")
    print("\n".join(new_lines))


if __name__ == "__main__":
    main()
