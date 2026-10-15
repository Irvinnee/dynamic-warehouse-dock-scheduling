from dataclasses import dataclass

from dock_scheduling.runtime import DockStatus, JobStatus, RuntimeState


@dataclass(frozen=True)
class Assign:
    job_id: str
    dock_id: str


class InvalidDecisionError(ValueError):
    pass


def validate_decision(decision: Assign, runtime: RuntimeState) -> None:
    job = runtime.jobs.get(decision.job_id)
    if job is None:
        raise InvalidDecisionError(f"job {decision.job_id!r} is not in the system")
    dock = runtime.docks.get(decision.dock_id)
    if dock is None:
        raise InvalidDecisionError(f"dock {decision.dock_id!r} does not exist")
    if job.status is not JobStatus.WAITING:
        raise InvalidDecisionError(
            f"job {decision.job_id!r} is {job.status.value}, expected WAITING"
        )
    if dock.status is not DockStatus.FREE:
        raise InvalidDecisionError(
            f"dock {decision.dock_id!r} is {dock.status.value}, expected FREE"
        )
    if dock.current_job_id is not None:
        raise InvalidDecisionError(
            f"dock {decision.dock_id!r} already holds job {dock.current_job_id!r}"
        )
    for other_dock in runtime.docks.values():
        if other_dock.current_job_id == decision.job_id:
            raise InvalidDecisionError(
                f"job {decision.job_id!r} is already active on dock "
                f"{other_dock.dock_id!r}"
            )


def validate_batch(decisions: tuple[Assign, ...], runtime: RuntimeState) -> None:
    seen_job_ids: set[str] = set()
    seen_dock_ids: set[str] = set()
    for decision in decisions:
        validate_decision(decision, runtime)
        if decision.job_id in seen_job_ids:
            raise InvalidDecisionError(
                f"job {decision.job_id!r} is assigned more than once in the batch"
            )
        if decision.dock_id in seen_dock_ids:
            raise InvalidDecisionError(
                f"dock {decision.dock_id!r} is assigned more than once in the batch"
            )
        seen_job_ids.add(decision.job_id)
        seen_dock_ids.add(decision.dock_id)
