from collections.abc import Iterable

from dock_scheduling.domain import PlanSnapshot, ScenarioDefinition


class InvalidScenarioError(ValueError):
    pass


def validate_plan(plan: PlanSnapshot) -> None:
    jobs = [job for truck in plan.trucks for job in truck.jobs]
    _check_ids("truck_id", [truck.truck_id for truck in plan.trucks])
    _check_ids("job_id", [job.job_id for job in jobs])
    for truck in plan.trucks:
        if not truck.jobs:
            raise InvalidScenarioError(f"truck {truck.truck_id!r}: no jobs")
    for job in jobs:
        if not job.section:
            raise InvalidScenarioError(f"job {job.job_id!r}: section must be non-empty")
        if job.estimated_service_time_min <= 0:
            raise InvalidScenarioError(
                f"job {job.job_id!r}: estimated_service_time_min must be > 0, "
                f"got {job.estimated_service_time_min}"
            )


def validate_scenario(scenario: ScenarioDefinition) -> None:
    plan = scenario.plan
    realization = scenario.realization
    validate_plan(plan)

    if not scenario.docks:
        raise InvalidScenarioError("scenario has no docks")
    _check_ids("dock_id", [dock.dock_id for dock in scenario.docks])
    if scenario.relocation_time_min < 0:
        raise InvalidScenarioError(
            f"relocation_time_min must be >= 0, got {scenario.relocation_time_min}"
        )

    _check_realization_ids(
        "truck",
        [truck.truck_id for truck in plan.trucks],
        [truck.truck_id for truck in realization.trucks],
    )
    _check_realization_ids(
        "job",
        [job.job_id for truck in plan.trucks for job in truck.jobs],
        [job.job_id for job in realization.jobs],
    )
    for truck in realization.trucks:
        if truck.actual_arrival_min < 0:
            raise InvalidScenarioError(
                f"truck {truck.truck_id!r}: actual_arrival_min must be >= 0, "
                f"got {truck.actual_arrival_min}"
            )
    for job in realization.jobs:
        if job.actual_service_time_min <= 0:
            raise InvalidScenarioError(
                f"job {job.job_id!r}: actual_service_time_min must be > 0, "
                f"got {job.actual_service_time_min}"
            )


def _check_ids(name: str, ids: Iterable[str]) -> None:
    seen: set[str] = set()
    for id_ in ids:
        if not id_.strip():
            raise InvalidScenarioError(f"{name} must not be blank, got {id_!r}")
        if id_ in seen:
            raise InvalidScenarioError(f"duplicate {name} {id_!r}")
        seen.add(id_)


def _check_realization_ids(
    kind: str, planned_ids: list[str], realized_ids: list[str]
) -> None:
    realized: set[str] = set()
    for id_ in realized_ids:
        if id_ in realized:
            raise InvalidScenarioError(f"{kind} {id_!r}: more than one realization")
        realized.add(id_)
    for id_ in planned_ids:
        if id_ not in realized:
            raise InvalidScenarioError(f"{kind} {id_!r}: no realization")
    planned = set(planned_ids)
    for id_ in realized_ids:
        if id_ not in planned:
            raise InvalidScenarioError(f"{kind} realization {id_!r}: no planned {kind}")
