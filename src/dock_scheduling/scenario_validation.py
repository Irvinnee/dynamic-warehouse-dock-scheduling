from collections import Counter
from collections.abc import Iterable

from dock_scheduling.domain import ScenarioDefinition


class ScenarioValidationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__(
            "invalid scenario:\n" + "\n".join(f"- {error}" for error in errors)
        )
        self.errors = tuple(errors)


def validate_scenario(scenario: ScenarioDefinition) -> None:
    errors: list[str] = []
    trucks = scenario.plan.trucks
    plan_jobs = [job for truck in trucks for job in truck.jobs]
    truck_realizations = scenario.realization.trucks
    job_realizations = scenario.realization.jobs

    for index, truck in enumerate(trucks):
        if problem := _identifier_problem(truck.truck_id):
            errors.append(f"truck at index {index} has {problem} truck_id")
        for job_index, job in enumerate(truck.jobs):
            if problem := _identifier_problem(job.job_id):
                errors.append(
                    f"truck {truck.truck_id!r} job at index {job_index} has "
                    f"{problem} job_id"
                )
    for index, truck_realization in enumerate(truck_realizations):
        if problem := _identifier_problem(truck_realization.truck_id):
            errors.append(f"truck realization at index {index} has {problem} truck_id")
    for index, job_realization in enumerate(job_realizations):
        if problem := _identifier_problem(job_realization.job_id):
            errors.append(f"job realization at index {index} has {problem} job_id")

    errors.extend(
        f"plan: duplicate truck_id {truck_id!r}"
        for truck_id in _duplicates(truck.truck_id for truck in trucks)
    )
    errors.extend(
        f"plan: duplicate job_id {job_id!r}"
        for job_id in _duplicates(job.job_id for job in plan_jobs)
    )
    errors.extend(
        f"realization: duplicate truck_id {truck_id!r}"
        for truck_id in _duplicates(
            realization.truck_id for realization in truck_realizations
        )
    )
    errors.extend(
        f"realization: duplicate job_id {job_id!r}"
        for job_id in _duplicates(
            realization.job_id for realization in job_realizations
        )
    )

    _check_realization_coverage(
        "truck",
        (truck.truck_id for truck in trucks),
        (realization.truck_id for realization in truck_realizations),
        errors,
    )
    _check_realization_coverage(
        "job",
        (job.job_id for job in plan_jobs),
        (realization.job_id for realization in job_realizations),
        errors,
    )

    if not scenario.docks:
        errors.append("scenario has no docks")
    for index, dock in enumerate(scenario.docks):
        if problem := _identifier_problem(dock.dock_id):
            errors.append(f"dock at index {index} has {problem} dock_id")
    errors.extend(
        f"duplicate dock_id {dock_id!r}"
        for dock_id in _duplicates(dock.dock_id for dock in scenario.docks)
    )
    if scenario.relocation_time_min < 0:
        errors.append(
            f"relocation_time_min must be >= 0, got {scenario.relocation_time_min}"
        )

    for truck in trucks:
        if not truck.jobs:
            errors.append(f"truck {truck.truck_id!r}: no jobs")
    for job in plan_jobs:
        if not job.section:
            errors.append(f"job {job.job_id!r}: section must be non-empty")
        if job.estimated_service_time_min <= 0:
            errors.append(
                f"job {job.job_id!r}: estimated_service_time_min must be > 0, "
                f"got {job.estimated_service_time_min}"
            )

    for truck_realization in truck_realizations:
        if truck_realization.actual_arrival_min < 0:
            errors.append(
                f"truck {truck_realization.truck_id!r}: actual_arrival_min must be "
                f">= 0, got {truck_realization.actual_arrival_min}"
            )
    for job_realization in job_realizations:
        if job_realization.actual_service_time_min <= 0:
            errors.append(
                f"job {job_realization.job_id!r}: actual_service_time_min must be "
                f"> 0, got {job_realization.actual_service_time_min}"
            )

    if errors:
        raise ScenarioValidationError(errors)


def _identifier_problem(identifier: str) -> str | None:
    if not identifier:
        return "an empty"
    if identifier.isspace():
        return "a whitespace-only"
    return None


def _duplicates(ids: Iterable[str]) -> list[str]:
    return [id_ for id_, count in Counter(ids).items() if count > 1]


def _check_realization_coverage(
    kind: str,
    planned_ids: Iterable[str],
    realized_ids: Iterable[str],
    errors: list[str],
) -> None:
    planned = dict.fromkeys(planned_ids)
    realized = dict.fromkeys(realized_ids)
    errors.extend(
        f"{kind} {id_!r}: no realization" for id_ in planned if id_ not in realized
    )
    errors.extend(
        f"{kind} realization {id_!r}: no planned {kind}"
        for id_ in realized
        if id_ not in planned
    )
