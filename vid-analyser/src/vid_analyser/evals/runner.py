import asyncio
import logging
import tempfile
from difflib import SequenceMatcher
from pathlib import Path

from vid_analyser.evals.config import EvalConfig
from vid_analyser.evals.judge import EventJudge, build_judge
from vid_analyser.evals.model import TestCase
from vid_analyser.evals.report_model import CaseResult, CaseScores, EvalReport, JudgeResult
from vid_analyser.evals.store import StoreAbc
from vid_analyser.pipeline import RunConfig, run

logger = logging.getLogger(__name__)


def _normalize_plate(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.upper().replace(" ", "").replace("-", "")
    return normalized or None


def score_exact_match(expected: object, predicted: object) -> float:
    return 1.0 if expected == predicted else 0.0


def score_number_plate(expected: str | None, predicted: str | None) -> float:
    expected_norm = _normalize_plate(expected)
    predicted_norm = _normalize_plate(predicted)
    if expected_norm is None and predicted_norm is None:
        return 1.0
    if expected_norm is None or predicted_norm is None:
        return 0.0
    return SequenceMatcher(None, expected_norm, predicted_norm).ratio()


def score_events(checklist_count: int, covered_count: int, contradicted_count: int) -> float | None:
    if checklist_count == 0:
        return None
    coverage = covered_count / checklist_count
    contradiction = contradicted_count / checklist_count
    return max(0.0, coverage - contradiction)


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


async def _evaluate_case(
    *,
    case: TestCase,
    store: StoreAbc,
    run_config: RunConfig,
    config: EvalConfig,
    judge: EventJudge,
) -> CaseResult:
    temp_path: Path | None = None
    try:
        video_bytes = store.get_video(case.video_path)
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp.write(video_bytes)
            temp_path = Path(tmp.name)

        prediction = await run(
            video_path=temp_path,
            user_prompt=config.user_prompt,
            system_prompt=config.system_prompt,
            config=run_config,
        )

        ir_score = score_exact_match(case.golden.ir_mode, prediction.ir_mode)
        parking_score = score_exact_match(case.golden.parking_spot_status, prediction.parking_spot_status)
        notification_score = score_exact_match(case.golden.send_notification, prediction.send_notification)
        plate_score = score_number_plate(case.golden.number_plate, prediction.number_plate)

        judge_result: JudgeResult | None = None
        events_score: float | None = None
        if case.golden.event_checklist:
            judge_result = await judge.evaluate(
                checklist=case.golden.event_checklist,
                events_description=prediction.events_description,
            )
            events_score = score_events(
                checklist_count=len(case.golden.event_checklist),
                covered_count=len(judge_result.covered_items),
                contradicted_count=len(judge_result.contradicted_items),
            )

        components = [ir_score, parking_score, notification_score, plate_score]
        if events_score is not None:
            components.append(events_score)
        total_score = _mean(components)

        return CaseResult(
            video_path=case.video_path,
            video_hash=case.video_hash,
            golden=case.golden,
            prediction=prediction,
            scores=CaseScores(
                ir_mode=ir_score,
                parking_spot_status=parking_score,
                send_notification=notification_score,
                number_plate=plate_score,
                events_description=events_score,
                total=total_score,
            ),
            judge=judge_result,
        )
    except Exception as exc:
        return CaseResult(
            video_path=case.video_path,
            video_hash=case.video_hash,
            golden=case.golden,
            prediction=None,
            scores=None,
            judge=None,
            error=str(exc),
        )
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


async def run_eval(store: StoreAbc, config: EvalConfig) -> EvalReport:
    logger.info(
        "Starting eval run: run_id=%s max_concurrency=%s",
        config.run_id,
        config.max_concurrency,
    )
    store.save_eval_run_config(config.run_id, config.to_persistable_dict())

    cases = store.get_labelled_cases()
    logger.info("Loaded labelled cases: run_id=%s cases=%s", config.run_id, len(cases))
    if not cases:
        report = EvalReport(
            total_cases=0,
            successful_cases=0,
            failed_cases=0,
            average_total_score=None,
            cases=[],
        )
        store.save_eval_report(config.run_id, report)
        logger.info("Completed eval run with no cases: run_id=%s", config.run_id)
        return report

    run_config = config.run_config
    judge = build_judge(config.judge)
    semaphore = asyncio.Semaphore(config.max_concurrency)

    async def _worker(case: TestCase) -> CaseResult:
        async with semaphore:
            logger.info("Evaluating case: run_id=%s video_path=%s", config.run_id, case.video_path)
            result = await _evaluate_case(
                case=case,
                store=store,
                run_config=run_config,
                config=config,
                judge=judge,
            )
            try:
                store.save_eval_case_result(config.run_id, result)
            except Exception as exc:
                logger.warning(
                    "Failed to persist case result: run_id=%s video_path=%s error=%s",
                    config.run_id,
                    case.video_path,
                    exc,
                )
                if result.error:
                    result.error = f"{result.error}; failed to persist result: {exc}"
                else:
                    result.error = f"failed to persist result: {exc}"
            if result.error:
                logger.warning(
                    "Case evaluation failed: run_id=%s video_path=%s error=%s",
                    config.run_id,
                    case.video_path,
                    result.error,
                )
            else:
                logger.info(
                    "Case evaluation complete: run_id=%s video_path=%s total=%s",
                    config.run_id,
                    case.video_path,
                    result.scores.total if result.scores else None,
                )
            return result

    results = await asyncio.gather(*(_worker(case) for case in cases))

    successful = [result for result in results if result.error is None]
    failed = [result for result in results if result.error is not None]
    totals = [result.scores.total for result in successful if result.scores and result.scores.total is not None]

    report = EvalReport(
        total_cases=len(results),
        successful_cases=len(successful),
        failed_cases=len(failed),
        average_total_score=_mean(totals),
        cases=results,
    )
    store.save_eval_report(config.run_id, report)
    logger.info(
        "Completed eval run: run_id=%s total=%s successful=%s failed=%s average_total=%s",
        config.run_id,
        report.total_cases,
        report.successful_cases,
        report.failed_cases,
        report.average_total_score,
    )
    return report
