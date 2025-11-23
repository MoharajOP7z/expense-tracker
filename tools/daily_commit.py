#!/usr/bin/env python3
"""
tools/daily_commit.py

Creates docs/progress/YYYY-MM-DD.md with a polished template.
Optional: automatically git add/commit/push with --git.

Usage:
    python tools/daily_commit.py            # just create today's file
    python tools/daily_commit.py --git      # create + git add/commit/push
    python tools/daily_commit.py --git --no-push  # create + git commit only
    python tools/daily_commit.py --message "daily log: custom message"
"""

import os
import sys
import argparse
import subprocess
from datetime import date, timedelta

# ----------------------------
# Config
# ----------------------------
LOG_DIR = os.path.join("docs", "progress")
TODAY = date.today()
FNAME = f"{TODAY.isoformat()}.md"
FILE_PATH = os.path.join(LOG_DIR, FNAME)

# ----------------------------
# Helpers
# ----------------------------
def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def list_logs():
    """Return sorted list of YYYY-MM-DD filenames (without path)."""
    if not os.path.isdir(LOG_DIR):
        return []
    files = [f for f in os.listdir(LOG_DIR) if f.endswith(".md")]
    files_sorted = sorted(files)
    return files_sorted

def compute_day_number(logs):
    """Return Day N based on count of existing logs. Day 1 if none exist."""
    return len(logs) + 1

def yesterday_exists():
    y = TODAY - timedelta(days=1)
    return os.path.exists(os.path.join(LOG_DIR, f"{y.isoformat()}.md"))

def compute_streak(logs):
    """Compute simple consecutive-day streak up to today (checks backwards)."""
    streak = 0
    cur = TODAY
    while True:
        curfn = os.path.join(LOG_DIR, f"{cur.isoformat()}.md")
        if os.path.exists(curfn):
            streak += 1
            cur = cur - timedelta(days=1)
        else:
            break
    return streak

# ----------------------------
# Template (editable)
# ----------------------------
def make_template(day_number, streak):
    return f"""# Daily Progress — {TODAY.isoformat()}

## 🚀 Summary (Day {day_number})
- Short description of today's major outcome.

---

## ✅ Completed Today
- <Add items completed today>

---

## 📁 Files Changed
- <list files changed / commits / PRs>

---

## ⚠️ Issues / Blockers
- <blocking issues>

---

## 🎯 Next (short-term)
1. <next immediate step>
2. <next step 2>
3. <optional stretch>

---

## 🧾 Meta
- Day number: {day_number}
- Streak (consecutive days including today): {streak}
- Created by: tools/daily_commit.py
"""

# ----------------------------
# Git helpers
# ----------------------------
def run_cmd(cmd, cwd=None):
    try:
        cp = subprocess.run(cmd, shell=False, check=True, capture_output=True, cwd=cwd, text=True)
        return (True, cp.stdout.strip())
    except subprocess.CalledProcessError as e:
        return (False, e.stderr.strip() or str(e))

def git_add_commit_push(file_path, commit_message="daily log", do_push=True):
    ok, out = run_cmd(["git", "add", file_path])
    if not ok:
        return (False, f"git add failed: {out}")
    ok, out = run_cmd(["git", "commit", "-m", commit_message])
    if not ok:
        # If commit fails because nothing to commit, return success
        if "nothing to commit" in out.lower() or "no changes added to commit" in out.lower():
            return (True, "No changes to commit.")
        return (False, f"git commit failed: {out}")
    if do_push:
        ok, out = run_cmd(["git", "push"])
        if not ok:
            return (False, f"git push failed: {out}")
        return (True, out)
    return (True, out)

# ----------------------------
# Main
# ----------------------------
def main(argv):
    parser = argparse.ArgumentParser(description="Create daily progress file and optionally git commit/push it.")
    parser.add_argument("--git", action="store_true", help="Run git add/commit/push after creating the file.")
    parser.add_argument("--no-push", action="store_true", help="When used with --git, commit but do not push.")
    parser.add_argument("--message", type=str, default=None, help="Custom commit message (if --git).")
    parser.add_argument("--force", action="store_true", help="If today's file exists, overwrite it.")
    args = parser.parse_args(argv)

    ensure_dir(LOG_DIR)

    logs = list_logs()
    daynum = compute_day_number(logs)
    streak = compute_streak(logs)

    if os.path.exists(FILE_PATH) and not args.force:
        print(f"Log already exists: {FILE_PATH}")
        print("Use --force to overwrite.")
        return 0

    # Write file
    template = make_template(daynum, streak)
    with open(FILE_PATH, "w", encoding="utf-8") as fh:
        fh.write(template)

    print(f"Created log: {FILE_PATH}")
    print(f"Day number: {daynum}, Streak: {streak}")

    if args.git:
        commit_msg = args.message if args.message else f"daily log: {TODAY.isoformat()}"
        ok, out = git_add_commit_push(FILE_PATH, commit_message=commit_msg, do_push=(not args.no_push))
        if ok:
            print("Git: success.")
            if out:
                print(out)
        else:
            print("Git: failed.")
            print(out)

    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
