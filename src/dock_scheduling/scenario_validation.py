from collections import Counter
from collections.abc import Iterable

from dock_scheduling.domain import JobPlan, OperationType, ScenarioDefinition


class ScenarioValidationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__(
            "invalid scenario:\n" + "\n".join(f"- {error}" for error in errors)
        )
        self.errors = tuple(errors)


def validate_scenario(scenario: ScenarioDefinition) -> None:
    errors: list[str] = []
    plan_jobs = scenario.plan.jobs
    realization_jobs = scenario.realization.jobs

    for index, job in enumerate(plan_jobs):
        if not job.job_id:
            errors.append(f"plan job at index {index} has an empty job_id")
    plan_duplicates = _duplicates(job.job_id for job in plan_jobs)
    realization_duplicates = _duplicates(job.job_id for job in realization_jobs)
    errors.extend(f"plan: duplicate job_id {job_id!r}" for job_id in plan_duplicates)
    errors.extend(
        f"realization: duplicate job_id {job_id!r}" for job_id in realization_duplicates
    )

    plan_by_id = {job.job_id: job for job in plan_jobs}
    realized_ids = dict.fromkeys(job.job_id for job in realization_jobs)
    for job_id in plan_by_id:
        if job_id not in realized_ids:
            errors.append(f"job {job_id!r}: no realization")
    for job_id in realized_ids:
        if job_id not in plan_by_id:
            errors.append(f"realization {job_id!r}: no planned job")
    # A duplicated job_id has no unambiguous plan and realization pair to compare.
    ambiguous_ids = set(plan_duplicates) | set(realization_duplicates)

    if not scenario.docks:
        errors.append("scenario has no docks")
    for index, dock in enumerate(scenario.docks):
        if not dock.dock_id:
            errors.append(f"dock at index {index} has an empty dock_id")
    errors.extend(
        f"duplicate dock_id {dock_id!r}"
        for dock_id in _duplicates(dock.dock_id for dock in scenario.docks)
    )

    for job in plan_jobs:
        _check_sections(job, errors)
        if job.estimated_service_time_min <= 0:
            errors.append(
                f"job {job.job_id!r}: estimated_service_time_min must be > 0, "
                f"got {job.estimated_service_time_min}"
            )

    for realization in realization_jobs:
        if realization.actual_arrival_min < 0:
            errors.append(
                f"job {realization.job_id!r}: actual_arrival_min must be >= 0, "
                f"got {realization.actual_arrival_min}"
            )
        if realization.actual_service_time_min <= 0:
            errors.append(
                f"job {realization.job_id!r}: actual_service_time_min must be > 0, "
                f"got {realization.actual_service_time_min}"
            )
        planned = plan_by_id.get(realization.job_id)
        if (
            planned is not None
            and realization.job_id not in ambiguous_ids
            and realization.actual_service_time_min
            != planned.estimated_service_time_min
        ):
            errors.append(
                f"job {realization.job_id!r}: actual_service_time_min "
                f"{realization.actual_service_time_min} must equal "
                f"estimated_service_time_min {planned.estimated_service_time_min} in V1"
            )

    if errors:
        raise ScenarioValidationError(errors)


def _duplicates(ids: Iterable[str]) -> list[str]:
    return [id_ for id_, count in Counter(ids).items() if count > 1]


def _check_sections(job: JobPlan, errors: list[str]) -> None:
    sections = {
        "load_section": (
            job.load_section,
            job.operation in (OperationType.LOAD, OperationType.BOTH),
        ),
        "unload_section": (
            job.unload_section,
            job.operation in (OperationType.UNLOAD, OperationType.BOTH),
        ),
    }
    for field_name, (value, required) in sections.items():
        if required and not value:
            errors.append(
                f"job {job.job_id!r}: {job.operation.value} requires a non-empty "
                f"{field_name}"
            )
        elif not required and value is not None:
            errors.append(
                f"job {job.job_id!r}: {job.operation.value} must not define "
                f"{field_name}"
            )
