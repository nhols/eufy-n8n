#!/usr/bin/env python3
"""Delete test cases (and their videos) that still have TODO in events_description."""

from pathlib import Path

import yaml

TEST_CASES_DIR = Path("evals/test_cases")

deleted = 0
for tc_path in sorted(TEST_CASES_DIR.glob("*.yaml")):
    with open(tc_path) as f:
        tc = yaml.safe_load(f)

    criteria = tc.get("judge_criteria", {}).get("events_description", [])
    if any("TODO" in str(s) for s in criteria):
        # Delete video
        video = Path(tc.get("video_path", ""))
        if video.exists():
            video.unlink()
            print(f"  Deleted video: {video}")

        # Delete test case
        tc_path.unlink()
        print(f"  Deleted case:  {tc_path}")
        deleted += 1

print(f"\nRemoved {deleted} unreviewed test cases.")
