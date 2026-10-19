"""Parsing and formatting of checkbox points.

A point is a markdown checkbox line, optionally with an importance marker:

    - [ ] !0 call the supplier
    - [x] !2 order brake pads

Importance runs from !0 (mega important) to !4 (not important at all).
!5 marks a daily item: it can't be ticked off, so it carries over to every
new day — for things to check each day.

A point can carry notes, between a >> line and a << line right under it:

    - [ ] call the supplier
      >>
      ask about the brake pads
      <<

Unfinished points move on to the next day; the day they left keeps them
marked as moved: - [>] call the supplier
"""

import re
from dataclasses import dataclass
from typing import Optional

POINT_RE = re.compile(r"^(?P<indent>\s*)- \[(?P<mark>[ xX>])\](?: (?P<body>.*))?$")
NOTES_OPEN = ">>"
NOTES_CLOSE = "<<"
BULLET_RE = re.compile(r"^(?P<indent>\s*)[-*+] (?P<body>.*)$")
PRIORITY_RE = re.compile(r"^!(?P<priority>[0-5])(?:\s+|$)")
DAILY = 5
"""Importance level of daily items: never ticked off, carried to every day."""

PRIORITY_LABELS = {
    0: "mega important",
    1: "very important",
    2: "important",
    3: "not so important",
    4: "not important at all",
    5: "daily",
}


@dataclass
class Point:
    """A parsed checkbox line."""

    indent: str
    checked: bool
    text: str
    priority: Optional[int] = None
    moved: bool = False
    """Carried over to a later day (- [>]); only that later copy counts."""

    @property
    def is_daily(self) -> bool:
        return self.priority == DAILY

    @property
    def is_open(self) -> bool:
        """Still to do here: not checked, and not moved on to a later day."""
        return not self.checked and not self.moved

    def format(self) -> str:
        mark = "x" if self.checked else ">" if self.moved else " "
        parts = []
        if self.priority is not None:
            parts.append(f"!{self.priority}")
        if self.text:
            parts.append(self.text)
        return f"{self.indent}- [{mark}] " + " ".join(parts)


def parse_point(line: str) -> Optional[Point]:
    """Parse a line into a Point, or None if it isn't a checkbox line."""
    match = POINT_RE.match(line)
    if not match:
        return None
    body = match.group("body") or ""

    priority = None
    priority_match = PRIORITY_RE.match(body)
    if priority_match:
        priority = int(priority_match.group("priority"))
        body = body[priority_match.end():]

    return Point(
        indent=match.group("indent"),
        checked=match.group("mark") in "xX",
        text=body.strip(),
        priority=priority,
        moved=match.group("mark") == ">",
    )


def to_point(line: str) -> Point:
    """Turn any line into a point, reusing an existing bullet if there is one."""
    point = parse_point(line)
    if point is not None:
        return point
    bullet = BULLET_RE.match(line)
    if bullet:
        return Point(indent=bullet.group("indent"), checked=False, text=bullet.group("body").strip())
    stripped = line.lstrip()
    return Point(indent=line[:len(line) - len(stripped)], checked=False, text=stripped.strip())


def remove_checkbox(line: str) -> str:
    """Strip the checkbox from a point, keeping its text as a plain line.

    Importance goes too, since it only means something on a point.
    """
    point = parse_point(line)
    if point is None:
        return line
    return point.indent + point.text


PRIORITY_COLORS = {0: "#e06c75", 1: "#c678dd", 2: "#e5c07b", 3: "#98c379", 4: "#61afef", 5: "bright_black"}
"""Red, purple, yellow, green, blue, then the terminal's own grey for daily
items. Fixed colours, since a terminal theme may have no real colours to
tell them apart."""


def point_spans(line: str) -> list[tuple[int, int, str]]:
    """Character ranges of a point's parts, for colouring them in the editor.

    Names: point.box, point.box.done, point.text.done, point.moved, priority.N.
    """
    match = POINT_RE.match(line)
    if not match:
        return []
    if match.group("mark") == ">":
        # Moved to a later day: the whole line fades out
        return [(len(match.group("indent")), len(line), "point.moved")]
    spans = []
    checked = match.group("mark") in "xX"
    box_start = len(match.group("indent"))
    box_end = box_start + len("- [ ]")
    spans.append((box_start, box_end, "point.box.done" if checked else "point.box"))

    body_start = match.start("body") if match.group("body") is not None else len(line)
    body_end = len(line)
    body = line[body_start:]
    priority_match = PRIORITY_RE.match(body)

    text_start = body_start
    if priority_match:
        spans.append((body_start, body_start + 2, f"priority.{priority_match.group('priority')}"))
        text_start = body_start + priority_match.end()
    if checked and body_end > text_start:
        spans.append((text_start, body_end, "point.text.done"))
    return spans


def notes_end(lines: list[str], row: int) -> int:
    """Index just past the point on `row` and its notes block, if it has one.

    The block is a >> line directly under the point, up to the next << line.
    A block that isn't closed yet doesn't count.
    """
    if row + 1 < len(lines) and lines[row + 1].strip() == NOTES_OPEN:
        for end in range(row + 2, len(lines)):
            if lines[end].strip() == NOTES_CLOSE:
                return end + 1
    return row + 1


def sort_points(lines: list[str]) -> list[str]:
    """Sort each unbroken list of points by importance, most important first.

    A point moves together with its notes block. Open points come before
    checked or moved ones; points without importance go after !4. Anything
    that isn't a point (or is indented differently) ends a list, so plain
    text never moves. Blank lines between points don't end it; after
    sorting, the points are spaced exactly one blank line apart.
    """
    result: list[str] = []
    row = 0
    while row < len(lines):
        point = parse_point(lines[row])
        if point is None:
            result.append(lines[row])
            row += 1
            continue
        # Gather the run of points at this indent, each with its notes
        entries = []
        while row < len(lines):
            entry_point = parse_point(lines[row])
            if entry_point is None or entry_point.indent != point.indent:
                break
            # Its notes, plus anything indented deeper under it (sub-points)
            end = notes_end(lines, row)
            while end < len(lines) and lines[end].strip() and \
                    len(lines[end]) - len(lines[end].lstrip()) > len(point.indent):
                end = notes_end(lines, end) if parse_point(lines[end]) else end + 1
            # Blank lines between two points stay in the list (they're
            # re-spaced below); blank lines after the last point end it
            after = end
            while after < len(lines) and not lines[after].strip():
                after += 1
            next_point = parse_point(lines[after]) if after < len(lines) else None
            if next_point is not None and next_point.indent == point.indent:
                end = after
            entries.append((entry_point, lines[row:end]))
            row = end
        entries.sort(key=lambda e: (
            not e[0].is_open,
            6 if e[0].priority is None else e[0].priority,
        ))
        for index, (_, entry_lines) in enumerate(entries):
            while entry_lines and not entry_lines[-1].strip():
                entry_lines = entry_lines[:-1]
            if index:
                result.append("")
            result.extend(entry_lines)
    return result
