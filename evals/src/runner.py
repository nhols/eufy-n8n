"""Core eval runner — orchestrates test execution and scoring."""

from __future__ import annotations

import asyncio
import json
import random
import statistics
import time
from pathlib import Path

import yaml

from evals.src.judge import judge_text
from evals.src.metrics import exact_match, null_accuracy, number_plate_score
from evals.src.prompt_utils import load_and_template_prompt
from evals.src.providers.registry import get_provider
from evals.src.schemas import (
    AggregateScores,
    EvalConfig,
    EvalReport,
    FieldScores,
    JudgeDetail,
    ModelOutput,
    RunResult,
    TestCase,
    TokenUsage,
)


def load_config(config_path: str) -> EvalConfig:
    """Load an EvalConfig from a YAML file."""
    with open(config_path) as f:
        data = yaml.safe_load(f)
    return EvalConfig(**data)


def load_test_cases(test_cases_dir: str) -> list[TestCase]:
    """Load all test cases from a directory of YAML files."""
    cases = []
    tc_dir = Path(test_cases_dir)
    for path in sorted(tc_dir.glob("*.yaml")):
        if path.name.startswith("_"):
            continue  # Skip example/template files
        with open(path) as f:
            data = yaml.safe_load(f)
        cases.append(TestCase(**data))
    return cases


def score_output(
    output: ModelOutput,
    test_case: TestCase,
    config: EvalConfig,
) -> tuple[FieldScores, JudgeDetail]:
    """Score a model output against expected values and judge criteria."""
    scores = FieldScores()

    # Exact-match fields
    scores.ir_mode = exact_match(output.ir_mode.value, test_case.expected.ir_mode.value)
    scores.parking_spot_status = exact_match(
        output.parking_spot_status.value,
        test_case.expected.parking_spot_status.value,
    )
    scores.send_notification = exact_match(output.send_notification, test_case.expected.send_notification)

    # Number plate
    scores.number_plate = number_plate_score(output.number_plate, test_case.expected.number_plate)
    scores.number_plate_null_accuracy = null_accuracy(output.number_plate, test_case.expected.number_plate)

    # LLM judge for free-text fields
    judge_detail = JudgeDetail()

    if test_case.judge_criteria.events_description:
        score = judge_text(
            text=output.events_description,
            criteria=test_case.judge_criteria.events_description,
            judge_config=config.judge,
        )
        judge_detail.events_description_score = score
        scores.events_description = score

    return scores, judge_detail


async def run_single(
    config: EvalConfig,
    test_case: TestCase,
    iteration: int,
    provider_instance=None,
    max_retries: int = 3,
) -> RunResult:
    """Run a single evaluation: invoke model, score output.

    Retries up to *max_retries* times with exponential back-off when the
    model provider returns an error.
    """
    if provider_instance is None:
        provider_instance = get_provider(config.provider, config.model, config.generation_params)

    # Load video
    video_bytes = Path(test_case.video_path).read_bytes()

    # Template the system prompt
    system_prompt = load_and_template_prompt(config.system_prompt_path, test_case.metadata)

    # Call the model with retry
    output = None
    token_usage = TokenUsage()
    error = None
    latency_ms = 0.0

    for attempt in range(1, max_retries + 1):
        start = time.perf_counter()
        try:
            result = await provider_instance.generate(video_bytes, system_prompt)
            latency_ms = (time.perf_counter() - start) * 1000
            output = result.output
            token_usage = result.token_usage
            error = None
            break
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            error = str(e)
            if attempt < max_retries:
                wait = min(2 ** attempt + random.random(), 30)
                print(f"\n    retry {attempt}/{max_retries} after error: {error} (waiting {wait:.1f}s)", flush=True)
                await asyncio.sleep(wait)

    if output is None:
        # All retries exhausted — return a default output with zero scores
        output = ModelOutput(
            ir_mode="unknown",
            parking_spot_status="unknown",
            number_plate=None,
            events_description="",
            summary="",
            send_notification=False,
        )

    # Score
    scores, judge_detail = score_output(output, test_case, config)

    return RunResult(
        config_name=config.name,
        test_case_id=test_case.id,
        iteration=iteration,
        model_output=output,
        scores=scores,
        judge_detail=judge_detail,
        latency_ms=latency_ms,
        token_usage=token_usage,
        error=error,
    )


def aggregate_results(results: list[RunResult]) -> AggregateScores:
    """Compute mean and std for each field across a list of results."""
    if not results:
        return AggregateScores()

    fields = [
        "ir_mode",
        "parking_spot_status",
        "number_plate",
        "number_plate_null_accuracy",
        "events_description",
        "send_notification",
    ]

    agg = AggregateScores()
    for field in fields:
        values = [getattr(r.scores, field) for r in results]
        setattr(agg, f"{field}_mean", statistics.mean(values))
        setattr(agg, f"{field}_std", statistics.stdev(values) if len(values) > 1 else 0.0)

    return agg


async def run_eval(
    config: EvalConfig,
    test_cases: list[TestCase],
    output_dir: str = "evals/results",
    max_concurrent: int = 10,
    max_retries: int = 3,
) -> EvalReport:
    """Run a full evaluation: all test cases × all iterations.

    Args:
        config: The eval configuration.
        test_cases: List of test cases to evaluate.
        output_dir: Directory to save the result JSON.
        max_concurrent: Maximum number of concurrent test case runs.
        max_retries: Maximum retries per model call on error.

    Returns:
        The completed EvalReport.
    """
    provider_instance = get_provider(config.provider, config.model, config.generation_params)

    all_results: list[RunResult] = []
    total = len(test_cases) * config.iterations
    completed = 0
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _run_item(tc: TestCase, iteration: int) -> RunResult:
        nonlocal completed
        async with semaphore:
            result = await run_single(config, tc, iteration, provider_instance, max_retries)

        completed += 1
        status = "OK" if result.error is None else f"ERROR: {result.error}"
        tokens_info = ""
        if result.token_usage.total_tokens > 0:
            tokens_info = f" | tokens: {result.token_usage.input_tokens}in/{result.token_usage.output_tokens}out"
        print(
            f"  [{completed}/{total}] {tc.id} (iter {iteration}/{config.iterations}) "
            f"{status} ({result.latency_ms:.0f}ms{tokens_info})",
            flush=True,
        )
        return result

    tasks = [
        _run_item(tc, iteration)
        for tc in test_cases
        for iteration in range(1, config.iterations + 1)
    ]
    all_results = await asyncio.gather(*tasks)

    # Aggregate per test case
    per_case_agg: dict[str, AggregateScores] = {}
    for tc in test_cases:
        tc_results = [r for r in all_results if r.test_case_id == tc.id]
        per_case_agg[tc.id] = aggregate_results(tc_results)

    # Overall aggregate
    overall = aggregate_results(all_results)

    # Sum token usage
    total_input_tokens = sum(r.token_usage.input_tokens for r in all_results)
    total_output_tokens = sum(r.token_usage.output_tokens for r in all_results)
    total_tokens = sum(r.token_usage.total_tokens for r in all_results)

    report = EvalReport(
        config=config,
        results=all_results,
        aggregate_scores=per_case_agg,
        overall_scores=overall,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        total_tokens=total_tokens,
    )

    # Save to disk
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    filename = f"{config.name}_{report.timestamp.replace(':', '-')}.json"
    filepath = out_path / filename
    filepath.write_text(report.model_dump_json(indent=2))
    print(f"\n  Results saved to {filepath}")

    return report


def print_summary(report: EvalReport) -> None:
    """Print a CLI summary table of the eval results."""
    print(f"\n{'=' * 60}")
    print(f"  Eval: {report.config.name}")
    print(f"  Model: {report.config.provider}/{report.config.model}")
    print(f"  Test cases: {len(report.aggregate_scores)}")
    print(f"  Iterations: {report.config.iterations}")
    print(f"{'=' * 60}")

    # Overall scores
    o = report.overall_scores
    print(f"\n  {'Field':<28} {'Mean':>8} {'Std':>8}")
    print(f"  {'-' * 44}")
    fields = [
        ("ir_mode", o.ir_mode_mean, o.ir_mode_std),
        ("parking_spot_status", o.parking_spot_status_mean, o.parking_spot_status_std),
        ("number_plate", o.number_plate_mean, o.number_plate_std),
        ("number_plate_null_acc", o.number_plate_null_accuracy_mean, o.number_plate_null_accuracy_std),
        ("events_description", o.events_description_mean, o.events_description_std),
        ("send_notification", o.send_notification_mean, o.send_notification_std),
    ]
    for name, mean, std in fields:
        print(f"  {name:<28} {mean:>8.3f} {std:>8.3f}")

    # Per test case
    print(f"\n  Per test case:")
    print(f"  {'Test Case':<28} {'Mean Score':>10}")
    print(f"  {'-' * 40}")
    for tc_id, agg in report.aggregate_scores.items():
        all_means = [
            agg.ir_mode_mean,
            agg.parking_spot_status_mean,
            agg.number_plate_mean,
            agg.send_notification_mean,
        ]
        # Include text field only if it was scored
        if agg.events_description_mean > 0:
            all_means.append(agg.events_description_mean)
        avg = statistics.mean(all_means) if all_means else 0.0
        print(f"  {tc_id:<28} {avg:>10.3f}")

    # Errors
    errors = [r for r in report.results if r.error is not None]
    if errors:
        print(f"\n  ⚠ {len(errors)} errors encountered:")
        for e in errors[:5]:
            print(f"    - {e.test_case_id} iter {e.iteration}: {e.error}")
        if len(errors) > 5:
            print(f"    ... and {len(errors) - 5} more")

    # Token usage
    if report.total_tokens > 0:
        print(f"\n  Token usage:")
        print(f"    Input tokens:  {report.total_input_tokens:,}")
        print(f"    Output tokens: {report.total_output_tokens:,}")
        print(f"    Total tokens:  {report.total_tokens:,}")

    print()
