#!/usr/bin/env python3
"""Process the per-session pending file and append one or more log entries.

Called from BOTH the Stop hook (after assistant turn ends) and the
UserPromptSubmit hook (before adding a new entry, to flush stale state
left over when the previous turn's Stop didn't fire).

Behavior:
  * Atomically renames the pending file to ``<pending>.processing`` so
    concurrent prompt hooks can recreate ``<pending>`` cleanly.
  * Splits pending entries at every ``source: "user"`` boundary — each
    such entry starts a NEW log group (= one turn). Entries with
    ``source: "claude"`` that follow a root within the same group
    become its sub_skills.
  * Computes per-segment tokens and duration_ms for each group using
    the session's transcript file (path is stored on each entry).
  * Removes the processing file when done.

Usage:
  python3 _pending_flush.py <pending_path> <log_path>
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone


TOKEN_FIELDS = (
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "output_tokens",
)


def parse_ts(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def read_jsonl(path):
    try:
        with open(path) as f:
            lines = f.readlines()
    except OSError:
        return []
    out = []
    for l in lines:
        l = l.strip()
        if not l:
            continue
        try:
            out.append(json.loads(l))
        except json.JSONDecodeError:
            pass
    return out


def collect_assistants(entries):
    """Return assistant entries (with parsed ts, model, token counters)
    and the user-text index list for turn boundaries, derived from
    already-loaded transcript entries.

    Streaming-chunk dedup: Claude Code transcripts emit one entry per
    streamed content block, all sharing the same ``message.id`` and
    repeating the FINAL ``usage`` totals on each chunk. We keep only the
    first occurrence per id so token counters aren't multiplied by chunk
    count.

    Tool-injected user entries (Skill output, etc.) are skipped from the
    user-text turn-boundary list. They're identified by ``isMeta`` or
    ``sourceToolUseID`` — without this, a Skill tool result looks like a
    new user prompt and incorrectly truncates the turn window."""
    # Indices of user-text messages — used to bound a group to its turn.
    user_text_idx = []
    for i, e in enumerate(entries):
        if e.get("type") != "user":
            continue
        if e.get("isMeta") or e.get("sourceToolUseID"):
            continue
        content = e.get("message", {}).get("content", "")
        if isinstance(content, str) and content.strip():
            user_text_idx.append(i)
        elif isinstance(content, list) and any(
            isinstance(b, dict) and b.get("type") == "text" for b in content
        ):
            user_text_idx.append(i)

    assistants = []
    seen_msg_ids = set()
    for i, e in enumerate(entries):
        if e.get("type") != "assistant":
            continue
        msg = e.get("message", {}) or {}
        msg_id = msg.get("id") or ""
        if msg_id:
            if msg_id in seen_msg_ids:
                continue
            seen_msg_ids.add(msg_id)
        usage = msg.get("usage", {}) or {}
        rec = {
            "idx": i,
            "ts": parse_ts(e.get("timestamp", "")),
            "model": msg.get("model", "") or "",
        }
        for f in TOKEN_FIELDS:
            rec[f] = usage.get(f, 0) or 0
        assistants.append(rec)
    return assistants, user_text_idx


def group_pending(pending):
    """Split pending entries into groups. A new group starts every time we
    hit a ``source: "user"`` entry (after the first entry). Entries are
    expected to already be sorted by timestamp."""
    groups = []
    current = []
    for entry in pending:
        if entry.get("source") == "user" and current:
            groups.append(current)
            current = [entry]
        else:
            current.append(entry)
    if current:
        groups.append(current)
    return groups


def empty_segment():
    s = {"model": ""}
    for f in TOKEN_FIELDS:
        s[f] = 0
    return s


def find_segment_idx(ts, boundaries):
    """Largest i such that boundaries[i] <= ts; defaults to 0."""
    idx = 0
    for i, b in enumerate(boundaries):
        if b is not None and ts is not None and b <= ts:
            idx = i
        else:
            break
    return idx


def turn_end_ts(group_first_ts, assistants, user_text_idx, transcript_entries):
    """Return the latest assistant timestamp in the same turn as
    ``group_first_ts``. The turn is bounded by the user-text message that
    started it and the next user-text message (or end-of-transcript).
    Returns None when the transcript yields no info."""
    if group_first_ts is None or not transcript_entries:
        return None

    # Walk user-text indices forward; the boundary is the latest one whose
    # parsed timestamp is <= group_first_ts.
    turn_start_idx = None
    for i in user_text_idx:
        ts = parse_ts(transcript_entries[i].get("timestamp", ""))
        if ts is not None and ts <= group_first_ts:
            turn_start_idx = i
        else:
            break

    if turn_start_idx is None:
        # Group's prompt isn't reflected in the transcript yet — fall back
        # to using the entire assistant tail.
        turn_start_idx = -1

    next_user_idx = None
    for i in user_text_idx:
        if i > turn_start_idx:
            next_user_idx = i
            break

    last_ts = None
    for a in assistants:
        if a["idx"] <= turn_start_idx:
            continue
        if next_user_idx is not None and a["idx"] >= next_user_idx:
            break
        if a["ts"] is not None:
            last_ts = a["ts"]
    return last_ts


def assistants_in_window(assistants, start_idx, end_idx):
    """Return assistants whose transcript index falls in (start_idx, end_idx)
    where end_idx may be None for "no upper bound". start_idx is exclusive."""
    out = []
    for a in assistants:
        if start_idx is not None and a["idx"] <= start_idx:
            continue
        if end_idx is not None and a["idx"] >= end_idx:
            break
        out.append(a)
    return out


def turn_window(group_first_ts, user_text_idx, transcript_entries):
    """Return (turn_start_idx, next_user_idx) for the turn containing
    ``group_first_ts``. ``turn_start_idx`` is the index of the user-text
    that started the turn (exclusive lower bound for assistants).
    ``next_user_idx`` is the index of the following user-text message
    (exclusive upper bound) or None if this is the latest turn."""
    turn_start_idx = -1
    for i in user_text_idx:
        ts = parse_ts(transcript_entries[i].get("timestamp", ""))
        if ts is not None and group_first_ts is not None and ts <= group_first_ts:
            turn_start_idx = i
        else:
            break
    next_user_idx = None
    for i in user_text_idx:
        if i > turn_start_idx:
            next_user_idx = i
            break
    return turn_start_idx, next_user_idx


def process_group(group, entries, assistants, user_text_idx, now):
    """Build a log entry (root + optional sub_skills) for one turn group."""
    boundaries = [parse_ts(p.get("ts", "")) for p in group]
    group_first_ts = boundaries[0]
    turn_start_idx, next_user_idx = turn_window(
        group_first_ts, user_text_idx, entries
    )
    turn_assistants = assistants_in_window(assistants, turn_start_idx, next_user_idx)

    segments = [empty_segment() for _ in group]
    for a in turn_assistants:
        if a["ts"] is None:
            continue
        idx = find_segment_idx(a["ts"], boundaries)
        seg = segments[idx]
        for f in TOKEN_FIELDS:
            seg[f] += a[f]
        if a["model"] and not seg["model"]:
            seg["model"] = a["model"]

    # End boundary for the last segment: the latest assistant ts in this
    # turn (so an idle gap before the next prompt does not inflate the
    # duration). If no transcript info, fall back to ``now``.
    last_asst_ts = max(
        (a["ts"] for a in turn_assistants if a["ts"] is not None),
        default=None,
    )
    last_end = last_asst_ts or now

    def segment_duration_ms(i):
        start = boundaries[i]
        if start is None:
            return 0
        if i + 1 < len(boundaries):
            end = boundaries[i + 1]
        else:
            end = last_end
        if end is None:
            return 0
        return max(0, int((end - start).total_seconds() * 1000))

    def segment_record(i, base):
        rec = dict(base)
        rec["model"] = segments[i]["model"]
        rec["duration_ms"] = segment_duration_ms(i)
        for f in TOKEN_FIELDS:
            rec[f] = segments[i][f]
        return rec

    root = group[0]
    entry = segment_record(0, {
        "skill": root.get("skill", ""),
        "ts": root.get("ts", ""),
        "session": root.get("session", ""),
        "source": root.get("source", "claude"),
    })

    if len(group) > 1:
        sub_skills = []
        for i in range(1, len(group)):
            sub_skills.append(segment_record(i, {
                "skill": group[i].get("skill", ""),
                "ts": group[i].get("ts", ""),
                "source": group[i].get("source", "claude"),
            }))
        entry["sub_skills"] = sub_skills
    return entry


def main():
    if len(sys.argv) < 3:
        print("usage: _pending_flush.py <pending_path> <log_path>", file=sys.stderr)
        sys.exit(2)
    pending_path = sys.argv[1]
    log_path = sys.argv[2]

    processing_path = pending_path + ".processing"
    try:
        os.rename(pending_path, processing_path)
    except FileNotFoundError:
        return
    except OSError:
        return

    pending = []
    for d in read_jsonl(processing_path):
        if d.get("skill"):
            pending.append(d)

    try:
        if not pending:
            return

        pending.sort(key=lambda e: parse_ts(e.get("ts", ""))
                     or datetime.fromtimestamp(0, tz=timezone.utc))

        now = datetime.now(timezone.utc)
        groups = group_pending(pending)
        transcript_path = pending[0].get("transcript", "")
        entries = read_jsonl(transcript_path) if transcript_path else []
        assistants, user_text_idx = collect_assistants(entries)

        with open(log_path, "a") as out:
            for grp in groups:
                entry = process_group(grp, entries, assistants, user_text_idx, now)
                out.write(json.dumps(entry) + "\n")
    finally:
        try:
            os.remove(processing_path)
        except OSError:
            pass


if __name__ == "__main__":
    main()
