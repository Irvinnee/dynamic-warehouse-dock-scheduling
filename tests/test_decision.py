import copy
from dataclasses import fields

import pytest

from dock_scheduling.decision import Assign, InvalidDecisionError, validate_decision
from dock_scheduling.domain import (
    DockDefinition,
    PlanSnapshot,
    RealizationDefinition,
    ScenarioDefinition,
)
from dock_scheduling.runtime import (
    DockStatus,
    JobRuntime,
    JobStatus,
    RuntimeState,
    create_runtime_state,
)


def _runtime() -> RuntimeState:
    runtime = create_runtime_state(
        ScenarioDefinition(
            plan=PlanSnapshot(jobs=()),
            realization=RealizationDefinition(jobs=()),
            docks=(DockDefinition("D01"), DockDefinition("D02")),
        )
    )
    runtime.jobs["J001"] = JobRuntime("J001", JobStatus.WAITING, 495)
    return runtime


def _rejection(decision: Assign, runtime: RuntimeState) -> str:
    with pytest.raises(InvalidDecisionError) as excinfo:
        validate_decision(decision, runtime)
    return str(excinfo.value)


def test_assign_carries_only_job_and_dock_ids():
    assert [field.name for field in fields(Assign)] == ["job_id", "dock_id"]


def test_waiting_job_on_free_dock_is_accepted():
    validate_decision(Assign("J001", "D01"), _runtime())


def test_job_not_in_system_is_rejected():
    assert (
        _rejection(Assign("J999", "D01"), _runtime())
        == "job 'J999' is not in the system"
    )


def test_unknown_dock_is_rejected():
    assert _rejection(Assign("J001", "D99"), _runtime()) == "dock 'D99' does not exist"


@pytest.mark.parametrize("status", [JobStatus.IN_SERVICE, JobStatus.COMPLETED])
def test_job_that_is_not_waiting_is_rejected(status):
    runtime = _runtime()
    runtime.jobs["J001"].status = status

    assert (
        _rejection(Assign("J001", "D01"), runtime)
        == f"job 'J001' is {status.value}, expected WAITING"
    )


def test_busy_dock_is_rejected():
    runtime = _runtime()
    runtime.jobs["J002"] = JobRuntime(
        "J002", JobStatus.IN_SERVICE, 480, 490, None, "D01"
    )
    runtime.docks["D01"].status = DockStatus.BUSY
    runtime.docks["D01"].current_job_id = "J002"

    assert (
        _rejection(Assign("J001", "D01"), runtime)
        == "dock 'D01' is BUSY, expected FREE"
    )


def test_free_dock_that_still_holds_a_job_is_rejected():
    runtime = _runtime()
    runtime.docks["D01"].current_job_id = "J002"

    assert (
        _rejection(Assign("J001", "D01"), runtime)
        == "dock 'D01' already holds job 'J002'"
    )


def test_job_already_active_on_another_dock_is_rejected():
    runtime = _runtime()
    runtime.docks["D02"].status = DockStatus.BUSY
    runtime.docks["D02"].current_job_id = "J001"

    assert (
        _rejection(Assign("J001", "D01"), runtime)
        == "job 'J001' is already active on dock 'D02'"
    )


@pytest.mark.parametrize(
    "decision", [Assign("J999", "D01"), Assign("J001", "D99"), Assign("J002", "D02")]
)
def test_rejected_decision_does_not_change_runtime(decision):
    runtime = _runtime()
    runtime.jobs["J002"] = JobRuntime("J002", JobStatus.COMPLETED, 480, 490, 520, "D02")
    before = copy.deepcopy(runtime)

    with pytest.raises(InvalidDecisionError):
        validate_decision(decision, runtime)

    assert runtime == before
