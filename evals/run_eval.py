#!/usr/bin/env python3
"""CLI entry point for running evaluations.

Usage:
    python -m evals.run_eval --config evals/configs/baseline.yaml
    python -m evals.run_eval --config evals/configs/baseline.yaml --test-cases evals/test_cases/ --output evals/results/
"""

from __future__ import annotations

import click

from evals.src.runner import load_config, load_test_cases, print_summary, run_eval


@click.command()
@click.option(
    "--config",
    "-c",
    required=True,
    help="Path to eval config YAML file.",
)
@click.option(
    "--test-cases",
    "-t",
    default="evals/test_cases",
    show_default=True,
    help="Directory containing test case YAML files.",
)
@click.option(
    "--output",
    "-o",
    default="evals/results",
    show_default=True,
    help="Directory to save result JSON files.",
)
@click.option(
    "--iterations",
    "-n",
    default=None,
    type=int,
    help="Override the number of iterations from the config.",
)
@click.option(
    "--max-concurrent",
    default=10,
    type=int,
    show_default=True,
    help="Maximum number of test cases to run concurrently.",
)
@click.option(
    "--max-retries",
    default=3,
    type=int,
    show_default=True,
    help="Maximum retries per model call on error.",
)
def main(config: str, test_cases: str, output: str, iterations: int | None, max_concurrent: int, max_retries: int) -> None:
    """Run an evaluation of a video-analysis model configuration."""
    import asyncio

    print(f"Loading config from {config}...")
    eval_config = load_config(config)

    if iterations is not None:
        eval_config.iterations = iterations
        print(f"  Overriding iterations to {iterations}")

    print(f"Loading test cases from {test_cases}...")
    cases = load_test_cases(test_cases)
    print(f"  Found {len(cases)} test case(s)")

    if not cases:
        print("No test cases found. Add YAML files to the test cases directory.")
        return

    print(f"\nRunning eval: {eval_config.name}")
    print(f"  Provider: {eval_config.provider}")
    print(f"  Model: {eval_config.model}")
    print(f"  Iterations: {eval_config.iterations}")
    print(f"  System prompt: {eval_config.system_prompt_path}")
    print(f"  Max concurrent: {max_concurrent}")
    print(f"  Max retries: {max_retries}")
    print()

    report = asyncio.run(run_eval(eval_config, cases, output, max_concurrent, max_retries))
    print_summary(report)


if __name__ == "__main__":
    main()
