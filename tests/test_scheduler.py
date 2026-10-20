import pytest

from dock_scheduling.decision import Assign
from dock_scheduling.domain import OperationType
from dock_scheduling.scheduler import FCFSScheduler
from dock_scheduling.scheduling_state import (
    EligibleJobView,
    FreeDockView,
    SchedulingState,
)


def _job(
    job_id: str,
    eligible_since_min: int,
    previous_dock_id: str | None = None,
    priority: bool = False,
    estimated_service_time_min: int = 30,
) -> EligibleJobView:
    return EligibleJobView(
        job_id=job_id,
        truck_id="T" + job_id.removeprefix("J"),
        operation=OperationType.UNLOAD,
        section="A",
        priority=priority,
        estimated_service_time_min=estimated_service_time_min,
        eligible_since_min=eligible_since_min,
        previous_dock_id=previous_dock_id,
    )


def _schedule(
    jobs: tuple[EligibleJobView, ...], dock_ids: tuple[str, ...]
) -> tuple[Assign, ...]:
    state = SchedulingState(
        current_time_min=510,
        eligible_jobs=jobs,
        free_docks=tuple(FreeDockView(dock_id) for dock_id in dock_ids),
    )
    return FCFSScheduler().schedule(state)


def test_earliest_eligible_jobs_get_free_docks_in_dock_id_order():
    # J003 has priority and the shortest estimate, FCFS doesn't care
    decisions = _schedule(
        (
            _job("J003", 500, priority=True, estimated_service_time_min=5),
            _job("J001", 470),
            _job("J002", 490),
        ),
        ("D02", "D01"),
    )

    assert decisions == (Assign("J001", "D01"), Assign("J002", "D02"))


def test_equal_eligible_since_is_broken_by_job_id():
    decisions = _schedule((_job("J002", 480), _job("J001", 480)), ("D01",))

    assert decisions == (Assign("J001", "D01"),)


@pytest.mark.parametrize(
    ("jobs", "dock_ids"),
    [((), ("D01", "D02")), ((_job("J001", 470),), ())],
    ids=["no_eligible_jobs", "no_free_docks"],
)
def test_no_assignment_without_eligible_jobs_or_free_docks(jobs, dock_ids):
    assert _schedule(jobs, dock_ids) == ()


@pytest.mark.parametrize(
    ("dock_ids", "expected_dock_id"),
    [(("D01", "D02"), "D02"), (("D03", "D01"), "D01")],
    ids=["previous_dock_free", "previous_dock_busy"],
)
def test_previous_dock_is_reused_when_free(dock_ids, expected_dock_id):
    decisions = _schedule((_job("J002", 470, previous_dock_id="D02"),), dock_ids)

    assert decisions == (Assign("J002", expected_dock_id),)


def test_previous_dock_preference_does_not_override_fcfs_selection():
    earlier = _job("J001", 470)
    later_with_preference = _job("J102", 480, previous_dock_id="D01")

    # both get picked, so the earlier job can't steal the later one's dock
    assert _schedule((earlier, later_with_preference), ("D01", "D02")) == (
        Assign("J001", "D02"),
        Assign("J102", "D01"),
    )
    # just one dock, the earlier job gets it even though the later one was there
    assert _schedule((earlier, later_with_preference), ("D01",)) == (
        Assign("J001", "D01"),
    )
