#!/usr/bin/env python3
"""Bootstrap an eval test set from real videos.

Scans a directory of MP4 files (from eufy-ws), matches each video's timestamp
against bookings from bookings.json, runs the model to generate initial labels,
and writes one YAML test case per video. You then review and correct the AI
outputs to create ground-truth labels.

Usage:
    python -m evals.bootstrap \
        --videos-dir local_files \
        --bookings evals/bookings.json \
        --config evals/configs/baseline.yaml \
        --output evals/test_cases \
        --limit 100
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import click
import yaml

from evals.src.prompt_utils import load_and_template_prompt
from evals.src.providers.registry import get_provider
from evals.src.runner import load_config
from evals.src.schemas import Booking, ModelOutput, TestCaseMetadata


def parse_video_datetime(filename: str) -> datetime:
    """Extract datetime from a eufy video filename like 20260206224241.mp4."""
    stem = Path(filename).stem
    return datetime.strptime(stem, "%Y%m%d%H%M%S")


def format_datetime_for_prompt(dt: datetime) -> str:
    """Format datetime the way n8n injects it: DD/MM/YYYY, HH:MM:SS."""
    return dt.strftime("%d/%m/%Y, %H:%M:%S")


def load_bookings(bookings_path: str) -> list[dict]:
    """Load bookings from the JustPark API dump (bookings.json)."""
    with open(bookings_path) as f:
        data = json.load(f)

    if isinstance(data, dict) and "items" in data:
        return data["items"]
    if isinstance(data, list):
        return data
    raise ValueError(f"Unexpected bookings format in {bookings_path}")


def parse_booking_datetime(date_str: str) -> datetime:
    """Parse a JustPark datetime string like '2026-02-10T14:30:00+00:00'."""
    # Handle various timezone offset formats
    return datetime.fromisoformat(date_str)


def get_bookings_for_date(all_bookings: list[dict], video_dt: datetime) -> list[Booking]:
    """Find bookings that overlap with the video's recording date.

    A booking overlaps if the video datetime falls between
    start_date and end_date (inclusive).
    """
    matched = []
    video_date = video_dt.date()

    for b in all_bookings:
        try:
            start = parse_booking_datetime(b["start_date"])
            end = parse_booking_datetime(b["end_date"])
        except (KeyError, ValueError):
            continue

        # Check if the video date falls within the booking period
        if start.date() <= video_date <= end.date():
            # Extract driver name (first name + last initial)
            driver = b.get("driver", {}).get("data", {})
            first = driver.get("first_name", "")
            last = driver.get("last_name", "")
            driver_name = f"{first} {last[0]}" if first and last else first or "Unknown"

            # Extract vehicle info
            vehicle = b.get("vehicle", {}).get("data", {})

            # Format times in the n8n injection format
            start_fmt = start.strftime("%d/%m/%Y, %H:%M:%S")
            end_fmt = end.strftime("%d/%m/%Y, %H:%M:%S")

            matched.append(
                Booking(
                    driver_name=driver_name,
                    start_time=start_fmt,
                    end_time=end_fmt,
                    vehicle_make=vehicle.get("make", "Unknown"),
                    vehicle_model=vehicle.get("model", "Unknown"),
                    vehicle_colour=vehicle.get("colour", "Unknown").title(),
                    vehicle_registration=vehicle.get("registration", "Unknown"),
                )
            )

    return matched


def make_test_case_id(filename: str) -> str:
    """Generate a readable test case ID from a video filename."""
    dt = parse_video_datetime(filename)
    return dt.strftime("%Y%m%d-%H%M%S")


def build_test_case_yaml(
    video_filename: str,
    video_dest: str,
    metadata: TestCaseMetadata,
    model_output: ModelOutput | None,
    error: str | None = None,
) -> dict:
    """Build the YAML-serializable dict for a test case."""
    tc = {
        "id": make_test_case_id(video_filename),
        "video_path": video_dest,
        "metadata": {
            "local_datetime": metadata.local_datetime,
            "bookings": [b.model_dump() for b in metadata.bookings],
        },
    }

    if model_output and not error:
        # Pre-fill expected from model output — user will review/correct these
        tc["expected"] = {
            "ir_mode": model_output.ir_mode.value,
            "parking_spot_status": model_output.parking_spot_status.value,
            "number_plate": model_output.number_plate,
            "send_notification": model_output.send_notification,
        }
        # Pre-fill judge criteria from model's free-text output
        tc["judge_criteria"] = {
            "events_description": ["TODO: add criteria based on video content"],
            "summary": ["TODO: add criteria based on video content"],
        }
        # Include model's text output as comments for reference during review
        tc["_model_events_description"] = model_output.events_description
        tc["_model_summary"] = model_output.summary
    else:
        tc["expected"] = {
            "ir_mode": "unknown",
            "parking_spot_status": "unknown",
            "number_plate": None,
            "send_notification": False,
        }
        tc["judge_criteria"] = {
            "events_description": ["TODO"],
            "summary": ["TODO"],
        }
        if error:
            tc["_error"] = error

    return tc


@click.command()
@click.option(
    "--videos-dir",
    "-v",
    default="local_files",
    show_default=True,
    help="Directory containing source MP4 files.",
)
@click.option(
    "--bookings",
    "-b",
    default="evals/bookings.json",
    show_default=True,
    help="Path to the JustPark bookings JSON dump.",
)
@click.option(
    "--config",
    "-c",
    required=True,
    help="Eval config YAML (used for provider/model/prompt settings).",
)
@click.option(
    "--output",
    "-o",
    default="evals/test_cases",
    show_default=True,
    help="Directory to write test case YAML files.",
)
@click.option(
    "--videos-output",
    default="evals/videos",
    show_default=True,
    help="Directory to copy videos to.",
)
@click.option(
    "--limit",
    "-n",
    default=100,
    show_default=True,
    help="Maximum number of videos to process.",
)
@click.option(
    "--skip-existing/--overwrite",
    default=True,
    show_default=True,
    help="Skip videos that already have a test case YAML.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be done without calling the model or writing files.",
)
def main(
    videos_dir: str,
    bookings: str,
    config: str,
    output: str,
    videos_output: str,
    limit: int,
    skip_existing: bool,
    dry_run: bool,
) -> None:
    """Bootstrap eval test cases from real doorbell videos."""
    # Load config
    eval_config = load_config(config)
    print(f"Config: {eval_config.name} ({eval_config.provider}/{eval_config.model})")

    # Find MP4 files
    mp4s = sorted(Path(videos_dir).glob("*.mp4"))
    print(f"Found {len(mp4s)} MP4 files in {videos_dir}")

    # Load bookings
    all_bookings = load_bookings(bookings)
    print(f"Loaded {len(all_bookings)} bookings from {bookings}")

    # Filter/limit
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)
    videos_out = Path(videos_output)
    videos_out.mkdir(parents=True, exist_ok=True)

    to_process = []
    for mp4 in mp4s:
        tc_id = make_test_case_id(mp4.name)
        yaml_path = output_dir / f"{tc_id}.yaml"
        if skip_existing and yaml_path.exists():
            print(f"  Skipping {mp4.name} — {yaml_path.name} already exists")
            continue
        to_process.append(mp4)
        if len(to_process) >= limit:
            break

    print(f"\nWill process {len(to_process)} videos")

    if dry_run:
        for mp4 in to_process:
            dt = parse_video_datetime(mp4.name)
            day_bookings = get_bookings_for_date(all_bookings, dt)
            print(f"  {mp4.name} → {format_datetime_for_prompt(dt)}, {len(day_bookings)} booking(s)")
        return

    # Initialise provider
    provider = get_provider(eval_config.provider, eval_config.model, eval_config.generation_params)

    async def process_one(idx: int, mp4: Path, sem: asyncio.Semaphore) -> tuple[bool, str | None]:
        """Process a single video under a concurrency semaphore. Returns (success, error)."""
        async with sem:
            dt = parse_video_datetime(mp4.name)
            day_bookings = get_bookings_for_date(all_bookings, dt)

            metadata = TestCaseMetadata(
                local_datetime=format_datetime_for_prompt(dt),
                bookings=day_bookings,
            )

            tc_id = make_test_case_id(mp4.name)
            print(f"  [{idx}/{len(to_process)}] {mp4.name} ({len(day_bookings)} booking(s))...", end=" ", flush=True)

            # Copy video
            dest_video = videos_out / mp4.name
            if not dest_video.exists():
                shutil.copy2(mp4, dest_video)

            # Call model (offload blocking IO to a thread)
            model_output = None
            error = None
            try:
                video_bytes = mp4.read_bytes()
                system_prompt = load_and_template_prompt(eval_config.system_prompt_path, metadata)
                model_output = await asyncio.to_thread(provider.generate, video_bytes, system_prompt)
                print("OK")
            except Exception as e:
                error = str(e)
                print(f"ERROR: {error}")

            # Build and save test case YAML
            tc_dict = build_test_case_yaml(
                video_filename=mp4.name,
                video_dest=str(dest_video),
                metadata=metadata,
                model_output=model_output,
                error=error,
            )

            yaml_path = output_dir / f"{tc_id}.yaml"
            with open(yaml_path, "w") as f:
                yaml.dump(tc_dict, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

            return (error is None, error)

    async def run_all() -> tuple[int, int]:
        sem = asyncio.Semaphore(10)
        tasks = [process_one(i, mp4, sem) for i, mp4 in enumerate(to_process, 1)]
        results = await asyncio.gather(*tasks)
        ok = sum(1 for success, _ in results if success)
        errs = sum(1 for success, _ in results if not success)
        return ok + errs, errs

    processed, errors = asyncio.run(run_all())

    print(f"\nDone! Processed {processed} videos ({errors} errors)")
    print(f"Test cases written to {output_dir}/")
    print(f"Videos copied to {videos_out}/")
    print(f"\nNext steps:")
    print(f"  1. Review each YAML in {output_dir}/ — correct 'expected' values")
    print(f"  2. Replace TODO judge_criteria with specific criteria for each case")
    print(f"  3. Remove _model_* reference fields once you've reviewed them")
    print(f"  4. Run: make eval CONFIG={config}")


if __name__ == "__main__":
    main()
