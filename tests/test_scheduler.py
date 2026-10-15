import pytest

from dock_scheduling.decision import Assign
from dock_scheduling.scheduler import FCFSScheduler
from dock_scheduling.scheduling_state import (
    FreeDockView,
    SchedulingState,
    WaitingJobView,
)


def _waiting(
    job_id: str,
    observed_arrival_min: int,
    priority: bool = False,
    estimated_service_time_min: int = 30,
) -> WaitingJobView:
    return WaitingJobView(
        job_id, observed_arrival_min, priority, estimated_service_time_min
    )


def _schedule(
    waiting_jobs: tuple[WaitingJobView, ...], dock_ids: tuple[str, ...]
) -> tuple[Assign, ...]:
    state = SchedulingState(
        current_time_min=510,
        waiting_jobs=waiting_jobs,
        free_docks=tuple(FreeDockView(dock_id) for dock_id in dock_ids),
    )
    return FCFSScheduler().schedule(state)


def test_earliest_arrivals_are_paired_with_docks_in_dock_id_order():
    decisions = _schedule(
        (_waiting("J003", 500), _waiting("J001", 470), _waiting("J002", 490)),
        ("D02", "D01"),
    )

    assert decisions == (Assign("J001", "D01"), Assign("J002", "D02"))


def test_equal_arrival_is_broken_by_job_id():
    decisions = _schedule((_waiting("J002", 480), _waiting("J001", 480)), ("D01",))

    assert decisions == (Assign("J001", "D01"),)


def test_priority_and_estimated_service_time_are_ignored():
    decisions = _schedule(
        (
            _waiting("J001", 490, priority=True, estimated_service_time_min=10),
            _waiting("J002", 470, priority=False, estimated_service_time_min=120),
        ),
        ("D01",),
    )

    assert decisions == (Assign("J002", "D01"),)


def test_single_job_takes_first_dock_by_dock_id():
    decisions = _schedule((_waiting("J001", 470),), ("D03", "D01", "D02"))

    assert decisions == (Assign("J001", "D01"),)


def test_dock_ids_are_compared_as_strings():
    decisions = _schedule((_waiting("J001", 470),), ("D2", "D10"))

    assert decisions == (Assign("J001", "D10"),)


@pytest.mark.parametrize(
    ("waiting_jobs", "dock_ids"),
    [
        ((), ("D01", "D02")),
        ((_waiting("J001", 470),), ()),
    ],
    ids=["no_waiting_jobs", "no_free_docks"],
)
def test_no_assignment_when_jobs_or_docks_are_missing(waiting_jobs, dock_ids):
    assert _schedule(waiting_jobs, dock_ids) == ()
