from dataclasses import fields

from dock_scheduling.domain import (
    DockDefinition,
    JobPlan,
    JobRealization,
    OperationType,
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
from dock_scheduling.scheduling_state import (
    FreeDockView,
    SchedulingState,
    WaitingJobView,
    build_scheduling_state,
)

SCENARIO = ScenarioDefinition(
    plan=PlanSnapshot(
        jobs=(
            JobPlan("J001", 480, OperationType.UNLOAD, True, 30, "A", None),
            JobPlan("J002", 485, OperationType.LOAD, False, 20, None, "B"),
            JobPlan("J003", 490, OperationType.BOTH, False, 40, "A", "B"),
        )
    ),
    realization=RealizationDefinition(
        jobs=(
            JobRealization("J001", 495, 45),
            JobRealization("J002", 500, 25),
            JobRealization("J003", 505, 50),
        )
    ),
    docks=(DockDefinition("D01"), DockDefinition("D02")),
)


def _runtime(*jobs: JobRuntime) -> RuntimeState:
    runtime = create_runtime_state(SCENARIO)
    for job in jobs:
        runtime.jobs[job.job_id] = job
    return runtime


def _state(runtime: RuntimeState, current_time_min: int = 510) -> SchedulingState:
    return build_scheduling_state(current_time_min, SCENARIO.plan, runtime)


def test_empty_runtime_has_no_waiting_jobs_and_all_docks_free():
    state = _state(_runtime())

    assert state.current_time_min == 510
    assert state.waiting_jobs == ()
    assert set(state.free_docks) == {FreeDockView("D01"), FreeDockView("D02")}


def test_waiting_job_combines_observed_arrival_with_plan_information():
    state = _state(_runtime(JobRuntime("J001", JobStatus.WAITING, 495)))

    assert state.waiting_jobs == (
        WaitingJobView(
            job_id="J001",
            observed_arrival_min=495,
            priority=True,
            estimated_service_time_min=30,
        ),
    )


def test_jobs_in_service_or_completed_are_not_waiting():
    runtime = _runtime(
        JobRuntime("J001", JobStatus.IN_SERVICE, 495, 500, None, "D01"),
        JobRuntime("J002", JobStatus.COMPLETED, 500, 500, 525, "D02"),
        JobRuntime("J003", JobStatus.WAITING, 505),
    )

    assert [job.job_id for job in _state(runtime).waiting_jobs] == ["J003"]


def test_busy_dock_is_not_free():
    runtime = _runtime(JobRuntime("J001", JobStatus.IN_SERVICE, 495, 500, None, "D01"))
    runtime.docks["D01"].status = DockStatus.BUSY
    runtime.docks["D01"].current_job_id = "J001"

    assert _state(runtime).free_docks == (FreeDockView("D02"),)


def test_views_expose_only_observed_and_planned_fields():
    state = _state(_runtime(JobRuntime("J001", JobStatus.WAITING, 495)))

    assert [field.name for field in fields(WaitingJobView)] == [
        "job_id",
        "observed_arrival_min",
        "priority",
        "estimated_service_time_min",
    ]
    assert [field.name for field in fields(FreeDockView)] == ["dock_id"]
    assert state.waiting_jobs[0].estimated_service_time_min == 30


def test_snapshot_does_not_change_when_runtime_changes_later():
    runtime = _runtime(JobRuntime("J001", JobStatus.WAITING, 495))
    state = _state(runtime)

    runtime.jobs["J001"].status = JobStatus.IN_SERVICE
    runtime.docks["D01"].status = DockStatus.BUSY
    runtime.jobs["J002"] = JobRuntime("J002", JobStatus.WAITING, 500)

    assert state.current_time_min == 510
    assert state.waiting_jobs == (WaitingJobView("J001", 495, True, 30),)
    assert set(state.free_docks) == {FreeDockView("D01"), FreeDockView("D02")}


def test_jobs_with_same_observed_arrival_are_both_waiting():
    runtime = _runtime(
        JobRuntime("J002", JobStatus.WAITING, 500),
        JobRuntime("J001", JobStatus.WAITING, 500),
    )

    assert {job.job_id for job in _state(runtime).waiting_jobs} == {"J001", "J002"}
