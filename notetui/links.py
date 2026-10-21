"""Jira issue keys in notes (MYMAS-1234), opened in the browser on double-click."""

import re

JIRA_BROWSE = "https://mymechanic.atlassian.net/browse/"
ISSUE_KEY = re.compile(r"\b(?:MYMAS|AUTEL)-\d+\b")


def issue_url(key: str) -> str:
    return JIRA_BROWSE + key


def issue_at(line: str, column: int) -> str | None:
    """The issue key under `column` in `line`, or None."""
    for match in ISSUE_KEY.finditer(line):
        if match.start() <= column <= match.end():
            return match.group()
    return None
