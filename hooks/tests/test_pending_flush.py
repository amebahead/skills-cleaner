"""Tests for hooks/_pending_flush.py.

Reproduces the cross-turn pollution bug (multiple user-prompted skills
ending up nested as root + sub_skills) and asserts the fixed behavior:
each user-source pending entry becomes its own log entry, while
claude-source entries that follow a root within the same turn are
recorded as sub_skills.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HOOKS_DIR = Path(__file__).resolve().parent.parent
FLUSH_SCRIPT = HOOKS_DIR / "_pending_flush.py"


def write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def run_flush(pending_path: Path, log_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(FLUSH_SCRIPT), str(pending_path), str(log_path)],
        capture_output=True,
        text=True,
        check=True,
    )


def read_log(log_path: Path) -> list[dict]:
    if not log_path.exists():
        return []
    return [json.loads(l) for l in log_path.read_text().splitlines() if l.strip()]


class PendingFlushTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.pending = self.tmp_path / "pending.jsonl"
        self.log = self.tmp_path / "log.jsonl"
        self.transcript = self.tmp_path / "transcript.jsonl"
        self.transcript.write_text("")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _transcript(self, records: list[dict]) -> None:
        write_jsonl(self.transcript, records)

    def test_two_user_prompts_become_two_log_entries(self) -> None:
        """Bug 3: when prompt hook accumulates entries from two different
        user-prompt turns, flushing must produce two top-level log entries —
        not one entry with the second skill nested as a sub_skill.
        """
        self._transcript([
            {"type": "user", "timestamp": "2026-04-28T10:00:00Z",
             "message": {"content": [{"type": "text", "text": "/list-skills"}]}},
            {"type": "assistant", "timestamp": "2026-04-28T10:00:01Z",
             "message": {"model": "claude-opus-4-7",
                         "usage": {"output_tokens": 500, "input_tokens": 10,
                                   "cache_read_input_tokens": 1000,
                                   "cache_creation_input_tokens": 0}}},
            {"type": "user", "timestamp": "2026-04-28T10:00:30Z",
             "message": {"content": [{"type": "text", "text": "/profile-skills"}]}},
            {"type": "assistant", "timestamp": "2026-04-28T10:00:31Z",
             "message": {"model": "claude-opus-4-7",
                         "usage": {"output_tokens": 700, "input_tokens": 12,
                                   "cache_read_input_tokens": 2000,
                                   "cache_creation_input_tokens": 0}}},
        ])

        write_jsonl(self.pending, [
            {"skill": "list-skills", "session": "s1",
             "transcript": str(self.transcript),
             "ts": "2026-04-28T10:00:00Z", "source": "user"},
            {"skill": "profile-skills", "session": "s1",
             "transcript": str(self.transcript),
             "ts": "2026-04-28T10:00:30Z", "source": "user"},
        ])

        run_flush(self.pending, self.log)

        entries = read_log(self.log)
        self.assertEqual(len(entries), 2,
                         f"expected two top-level entries, got: {entries}")
        self.assertEqual(entries[0]["skill"], "list-skills")
        self.assertEqual(entries[1]["skill"], "profile-skills")
        self.assertNotIn("sub_skills", entries[0])
        self.assertNotIn("sub_skills", entries[1])

    def test_claude_subskills_within_one_turn_stay_nested(self) -> None:
        """Same-turn claude-tool invocations must remain root + sub_skills."""
        self._transcript([
            {"type": "user", "timestamp": "2026-04-28T10:00:00Z",
             "message": {"content": [{"type": "text", "text": "build something"}]}},
            {"type": "assistant", "timestamp": "2026-04-28T10:00:01Z",
             "message": {"model": "claude-opus-4-7",
                         "usage": {"output_tokens": 100, "input_tokens": 1,
                                   "cache_read_input_tokens": 0,
                                   "cache_creation_input_tokens": 0}}},
            {"type": "assistant", "timestamp": "2026-04-28T10:00:30Z",
             "message": {"model": "claude-opus-4-7",
                         "usage": {"output_tokens": 200, "input_tokens": 2,
                                   "cache_read_input_tokens": 0,
                                   "cache_creation_input_tokens": 0}}},
        ])

        write_jsonl(self.pending, [
            {"skill": "brainstorming", "session": "s1",
             "transcript": str(self.transcript),
             "ts": "2026-04-28T10:00:01Z", "source": "claude"},
            {"skill": "writing-plans", "session": "s1",
             "transcript": str(self.transcript),
             "ts": "2026-04-28T10:00:20Z", "source": "claude"},
        ])

        run_flush(self.pending, self.log)

        entries = read_log(self.log)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["skill"], "brainstorming")
        self.assertIn("sub_skills", entries[0])
        self.assertEqual(len(entries[0]["sub_skills"]), 1)
        self.assertEqual(entries[0]["sub_skills"][0]["skill"], "writing-plans")

    def test_user_then_claude_in_same_turn_nests(self) -> None:
        """If user types /skill1 and Claude in the same turn invokes Skill(skill2),
        skill2 is a sub_skill of skill1 — the user-source boundary only splits
        when a SECOND user-source entry appears."""
        self._transcript([
            {"type": "user", "timestamp": "2026-04-28T10:00:00Z",
             "message": {"content": [{"type": "text", "text": "/list-skills"}]}},
            {"type": "assistant", "timestamp": "2026-04-28T10:00:05Z",
             "message": {"model": "claude-opus-4-7",
                         "usage": {"output_tokens": 300, "input_tokens": 5,
                                   "cache_read_input_tokens": 0,
                                   "cache_creation_input_tokens": 0}}},
        ])

        write_jsonl(self.pending, [
            {"skill": "list-skills", "session": "s1",
             "transcript": str(self.transcript),
             "ts": "2026-04-28T10:00:00Z", "source": "user"},
            {"skill": "some-helper", "session": "s1",
             "transcript": str(self.transcript),
             "ts": "2026-04-28T10:00:03Z", "source": "claude"},
        ])

        run_flush(self.pending, self.log)

        entries = read_log(self.log)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["skill"], "list-skills")
        self.assertIn("sub_skills", entries[0])
        self.assertEqual(entries[0]["sub_skills"][0]["skill"], "some-helper")

    def test_pending_file_removed_after_flush(self) -> None:
        write_jsonl(self.pending, [
            {"skill": "list-skills", "session": "s1",
             "transcript": str(self.transcript),
             "ts": "2026-04-28T10:00:00Z", "source": "user"},
        ])

        run_flush(self.pending, self.log)

        self.assertFalse(self.pending.exists(),
                         "pending file must be removed after flush")
        # No leftover .processing file either
        leftovers = list(self.tmp_path.glob("pending.jsonl*"))
        self.assertEqual(leftovers, [],
                         f"unexpected leftover files: {leftovers}")

    def test_missing_pending_is_noop(self) -> None:
        """Calling flush when pending doesn't exist is a no-op (no crash)."""
        run_flush(self.pending, self.log)  # pending doesn't exist
        self.assertEqual(read_log(self.log), [])

    def test_durations_use_per_group_boundaries(self) -> None:
        """For two separate user-prompt turns, the first group's last
        segment must end at its turn boundary (not at the second group's
        much-later prompt time, which would inflate duration)."""
        self._transcript([
            {"type": "user", "timestamp": "2026-04-28T10:00:00Z",
             "message": {"content": [{"type": "text", "text": "/list-skills"}]}},
            {"type": "assistant", "timestamp": "2026-04-28T10:00:02Z",
             "message": {"model": "claude-opus-4-7",
                         "usage": {"output_tokens": 100, "input_tokens": 1,
                                   "cache_read_input_tokens": 0,
                                   "cache_creation_input_tokens": 0}}},
            {"type": "user", "timestamp": "2026-04-28T10:05:00Z",  # 5 minutes later
             "message": {"content": [{"type": "text", "text": "/profile-skills"}]}},
            {"type": "assistant", "timestamp": "2026-04-28T10:05:02Z",
             "message": {"model": "claude-opus-4-7",
                         "usage": {"output_tokens": 200, "input_tokens": 2,
                                   "cache_read_input_tokens": 0,
                                   "cache_creation_input_tokens": 0}}},
        ])

        write_jsonl(self.pending, [
            {"skill": "list-skills", "session": "s1",
             "transcript": str(self.transcript),
             "ts": "2026-04-28T10:00:00Z", "source": "user"},
            {"skill": "profile-skills", "session": "s1",
             "transcript": str(self.transcript),
             "ts": "2026-04-28T10:05:00Z", "source": "user"},
        ])

        run_flush(self.pending, self.log)

        entries = read_log(self.log)
        self.assertEqual(len(entries), 2)
        # First turn duration must NOT span the 5-minute idle gap.
        # Reasonable upper bound: a few seconds (turn ended at 10:00:02Z).
        self.assertLess(entries[0]["duration_ms"], 60_000,
                        f"first turn duration leaked into idle gap: {entries[0]['duration_ms']}ms")


if __name__ == "__main__":
    unittest.main()
