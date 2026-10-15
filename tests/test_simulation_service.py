from dock_scheduling.decision import Assign
from dock_scheduling.domain import (
    DockDefinition,
    JobPlan,
    JobRealization,
    OperationType,
    PlanSnapshot,
    RealizationDefinition,
    ScenarioDefinition,
)
from dock_scheduling.event_log import EventRecord, EventType
from dock_scheduling.runtime import DockRuntime, DockStatus, JobRuntime, JobStatus
from dock_scheduling.scheduling_state import SchedulingState
from dock_scheduling.simulation import WarehouseSimulation


class _AssignJ001ToD02Scheduler:
    def schedule(self, state: SchedulingState) -> tuple[Assign, ...]:
        if "J001" in {job.job_id for job in state.waiting_jobs}:
            return (Assign("J001", "D02"),)
        return ()


ARRIVAL_MIN = 495
SERVICE_START_MIN = ARRIVAL_MIN
SERVICE_TIME_MIN = 30
SERVICE_END_MIN = SERVICE_START_MIN + SERVICE_TIME_MIN


def _started_simulation() -> WarehouseSimulation:
    scenario = ScenarioDefinition(
        plan=PlanSnapshot(
            jobs=(
                JobPlan(
                    "J001",
                    480,
                    OperationType.UNLOAD,
                    False,
                    SERVICE_TIME_MIN,
                    "A",
                    None,
                ),
            )
        ),
        realization=RealizationDefinition(
            jobs=(JobRealization("J001", ARRIVAL_MIN, SERVICE_TIME_MIN),)
        ),
        docks=(DockDefinition("D01"), DockDefinition("D02")),
    )
    simulation = WarehouseSimulation(scenario, _AssignJ001ToD02Scheduler())
    simulation.run(until_min=SERVICE_START_MIN + 1)
    return simulation


def test_service_start_puts_waiting_job_in_service_on_selected_dock():
    simulation = _started_simulation()

    assert simulation.runtime.jobs["J001"] == JobRuntime(
        "J001", JobStatus.IN_SERVICE, ARRIVAL_MIN, SERVICE_START_MIN, None, "D02"
    )
    assert simulation.runtime.docks == {
        "D01": DockRuntime("D01", DockStatus.FREE, None),
        "D02": DockRuntime("D02", DockStatus.BUSY, "J001"),
    }
    assert simulation.event_log.records[-1] == EventRecord(
        SERVICE_START_MIN, EventType.SERVICE_START, "J001", "D02"
    )


def test_job_stays_in_service_until_service_time_has_elapsed():
    simulation = _started_simulation()

    simulation.run(until_min=SERVICE_END_MIN - 1)

    assert simulation.runtime.jobs["J001"].status is JobStatus.IN_SERVICE
    assert simulation.runtime.docks["D02"] == DockRuntime(
        "D02", DockStatus.BUSY, "J001"
    )


def test_service_completes_after_actual_service_time_and_frees_dock():
    simulation = _started_simulation()

    simulation.run()

    assert simulation.runtime.jobs["J001"] == JobRuntime(
        "J001",
        JobStatus.COMPLETED,
        ARRIVAL_MIN,
        SERVICE_START_MIN,
        SERVICE_END_MIN,
        "D02",
    )
    assert simulation.runtime.docks["D02"] == DockRuntime("D02", DockStatus.FREE, None)


def test_complete_job_trace_is_arrival_service_start_service_end():
    simulation = _started_simulation()

    simulation.run()

    assert simulation.event_log.records == (
        EventRecord(ARRIVAL_MIN, EventType.JOB_ARRIVAL, "J001", None),
        EventRecord(SERVICE_START_MIN, EventType.SERVICE_START, "J001", "D02"),
        EventRecord(SERVICE_END_MIN, EventType.SERVICE_END, "J001", "D02"),
    )
