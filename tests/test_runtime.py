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
    DockRuntime,
    DockStatus,
    JobRuntime,
    JobStatus,
    create_runtime_state,
)


def _scenario() -> ScenarioDefinition:
    return ScenarioDefinition(
        plan=PlanSnapshot(
            jobs=(
                JobPlan("J001", 480, OperationType.UNLOAD, False, 30, "A", None),
                JobPlan("J002", 490, OperationType.LOAD, False, 20, None, "B"),
            )
        ),
        realization=RealizationDefinition(
            jobs=(JobRealization("J001", 495, 30), JobRealization("J002", 500, 20))
        ),
        docks=(DockDefinition("D02"), DockDefinition("D01")),
    )


def test_new_runtime_state_has_every_scenario_dock_free():
    runtime = create_runtime_state(_scenario())

    assert runtime.docks == {
        "D01": DockRuntime("D01", DockStatus.FREE, None),
        "D02": DockRuntime("D02", DockStatus.FREE, None),
    }


def test_new_runtime_state_has_no_job_records_before_arrival():
    runtime = create_runtime_state(_scenario())

    assert runtime.jobs == {}
    assert runtime.waiting_job_ids == []


def test_waiting_job_ids_contains_exactly_the_waiting_jobs():
    runtime = create_runtime_state(_scenario())
    runtime.jobs["J002"] = JobRuntime("J002", JobStatus.WAITING, 470)
    runtime.jobs["J003"] = JobRuntime(
        "J003", JobStatus.IN_SERVICE, 480, 485, None, "D01"
    )
    runtime.jobs["J001"] = JobRuntime("J001", JobStatus.WAITING, 495)

    assert sorted(runtime.waiting_job_ids) == ["J001", "J002"]


def test_runtime_states_from_same_scenario_are_independent():
    scenario = _scenario()
    original_scenario = _scenario()
    first = create_runtime_state(scenario)
    second = create_runtime_state(scenario)

    first.jobs["J001"] = JobRuntime(
        "J001", JobStatus.IN_SERVICE, 495, service_start_min=495, assigned_dock_id="D01"
    )
    first.docks["D01"].status = DockStatus.BUSY
    first.docks["D01"].current_job_id = "J001"

    assert second.jobs == {}
    assert second.docks["D01"] == DockRuntime("D01", DockStatus.FREE, None)
    assert scenario == original_scenario
