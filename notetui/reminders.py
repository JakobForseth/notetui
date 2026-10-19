"""Background service that sends desktop notifications for point reminders.

Runs independently of the TUI (as a systemd user service), so reminders keep
firing while NoteTUI is closed. Every few seconds it scans ~/notes/*.md for
unchecked points carrying a reminder:

    - [ ] !1 call the supplier @01.30   -> every 1h30m, counted from when first seen
    - [ ] !1 call the supplier @13:00   -> every day at 13:00

A reminder stops as soon as its point is checked, deleted, or loses its
reminder. Points marked as moved (- [>]) are skipped: their copy on a later
day is the one that counts. Timing state is kept in ~/.local/state/notetui/reminders.json.
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from notetui import sounds
from notetui.points import PRIORITY_LABELS, parse_point

NOTES_DIR = Path.home() / "notes"
STATE_FILE = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "notetui" / "reminders.json"
POLL_SECONDS = 20

URGENCY = {0: "critical", 1: "normal", 2: "normal", 3: "low", 4: "low", 5: "low"}


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE_FILE)


def scan_reminders(notes_dir: Path):
    """Yield (key, note_name, point) for every unchecked point with a reminder."""
    for note_file in sorted(notes_dir.glob("*.md")):
        try:
            lines = note_file.read_text().split("\n")
        except OSError:
            continue
        for line in lines:
            point = parse_point(line)
            if point and point.is_open and point.reminder:
                # No file name in the key, so a reminder keeps its timing when
                # its point carries over to the next day
                key = f"{point.text}|{point.reminder.spec}"
                yield key, note_file.stem, point


def is_due(point, entry: dict, now: float) -> bool:
    reminder = point.reminder
    last = entry.get("last")
    if reminder.daily:
        today = datetime.fromtimestamp(now)
        target = today.replace(hour=reminder.hours, minute=reminder.minutes, second=0, microsecond=0).timestamp()
        # Fire once per day after the time has passed, but not on the day the
        # reminder was added if it was added after that day's time
        return now >= target and entry["since"] < target and (last is None or last < target)
    return now >= (last or entry["since"]) + reminder.interval_seconds


def notify(note_name: str, point) -> None:
    title = f"⏰ {point.text or '(empty point)'}"
    details = []
    if point.priority is not None:
        details.append(f"!{point.priority} {PRIORITY_LABELS[point.priority]}")
    details.append(f"note {note_name}")
    details.append(point.reminder.describe())
    urgency = URGENCY.get(point.priority, "normal")
    try:
        subprocess.run(
            ["notify-send", "--app-name=NoteTUI", f"--urgency={urgency}", title, " · ".join(details)],
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"notify-send failed: {e}", file=sys.stderr)


def tick(state: dict, now: float) -> bool:
    """Check every reminder once. Returns True if the state changed."""
    changed = False
    seen = set()
    fired = []
    for key, note_name, point in scan_reminders(NOTES_DIR):
        seen.add(key)
        entry = state.get(key)
        if entry is None:
            state[key] = {"since": now, "last": None}
            changed = True
            continue
        if is_due(point, entry, now):
            notify(note_name, point)
            fired.append(point.priority)
            entry["last"] = now
            changed = True
    if fired:
        # One sound per check, even if several reminders went off: the most important one's
        sounds.play(min(fired, key=lambda p: 4 if p is None else p))
    # Forget reminders whose point was checked, removed, or edited
    for key in list(state):
        if key not in seen:
            del state[key]
            changed = True
    return changed


def main() -> None:
    if "--demo" in sys.argv[1:]:
        sounds.demo()
        return
    state = load_state()
    sounds.prepare()
    print(f"notetui-reminders watching {NOTES_DIR}", flush=True)
    while True:
        if tick(state, time.time()):
            save_state(state)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
