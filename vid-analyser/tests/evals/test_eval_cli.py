import json
import os
import subprocess
import sys
from pathlib import Path


def test_cli_loads_config_and_writes_report(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    store_root.mkdir(parents=True, exist_ok=True)
    (store_root / "videos").mkdir(parents=True, exist_ok=True)
    (store_root / "golden").mkdir(parents=True, exist_ok=True)

    config_path = tmp_path / "eval_config.json"
    config_path.write_text(
        json.dumps(
            {
                "run_id": "cli-test-run",
                "run_config": {
                    "provider": {"kind": "gemini", "model": "analysis-model"},
                    "overlay_zones": [],
                    "enable_person_id": False,
                },
                "user_prompt": "What is in the video?",
                "system_prompt": "system",
                "judge": {
                    "provider": {"kind": "gemini", "model": "judge-model"},
                    "system_prompt": "Judge checklist coverage and contradictions.",
                },
            }
        ),
        encoding="utf-8",
    )
    out_path = tmp_path / "report.json"

    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    cmd = [
        sys.executable,
        "scripts/eval_run.py",
        "--store-root",
        str(store_root),
        "--config",
        str(config_path),
        "--out",
        str(out_path),
    ]
    proc = subprocess.run(
        cmd,
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stderr
    assert out_path.exists()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["total_cases"] == 0
    assert payload["successful_cases"] == 0
    assert payload["failed_cases"] == 0

    run_dir = store_root / "eval_runs" / "cli-test-run"
    assert (run_dir / "config.json").exists()
    assert (run_dir / "report.json").exists()
