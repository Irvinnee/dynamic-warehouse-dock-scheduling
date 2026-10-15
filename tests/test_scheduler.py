import pytest

from dock_scheduling.decision import Assign
from dock_scheduling.scheduler import FCFSScheduler
from dock_scheduling.scheduling_state import (
    FreeDockView,
    SchedulingState,
    WaitingJobView,
)


def _schedule(
    jobs: tuple[WaitingJobView, ...], dock_ids: tuple[str, ...]
) -> tuple[Assign, ...]:
    state = SchedulingState(
        current_time_min=510,
        waiting_jobs=jobs,
        free_docks=tuple(FreeDockView(dock_id) for dock_id in dock_ids),
    )
    return FCFSScheduler().schedule(state)


def test_earliest_waiting_jobs_get_free_docks_in_dock_id_order():
    # J003 has priority and the shortest estimate, FCFS doesn't care
    decisions = _schedule(
        (
            WaitingJobView("J003", 500, True, 5),
            WaitingJobView("J001", 470, False, 30),
            WaitingJobView("J002", 490, False, 30),
        ),
        ("D02", "D01"),
    )

    assert decisions == (Assign("J001", "D01"), Assign("J002", "D02"))


def test_equal_arrival_is_broken_by_job_id():
    decisions = _schedule(
        (
            WaitingJobView("J002", 480, False, 30),
            WaitingJobView("J001", 480, False, 30),
        ),
        ("D01",),
    )

    assert decisions == (Assign("J001", "D01"),)


@pytest.mark.parametrize(
    ("jobs", "dock_ids"),
    [((), ("D01", "D02")), ((WaitingJobView("J001", 470, False, 30),), ())],
    ids=["no_waiting_jobs", "no_free_docks"],
)
def test_no_assignment_without_waiting_jobs_or_free_docks(jobs, dock_ids):
    assert _schedule(jobs, dock_ids) == ()
