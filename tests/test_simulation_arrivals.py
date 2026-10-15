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
from dock_scheduling.runtime import JobRuntime, JobStatus
from dock_scheduling.simulation import WarehouseSimulation


def _scenario(arrivals: dict[str, int]) -> ScenarioDefinition:
    return ScenarioDefinition(
        plan=PlanSnapshot(
            jobs=tuple(
                JobPlan(job_id, 480, OperationType.UNLOAD, False, 30, "A", None)
                for job_id in arrivals
            )
        ),
        realization=RealizationDefinition(
            jobs=tuple(
                JobRealization(job_id, actual_arrival_min, 30)
                for job_id, actual_arrival_min in arrivals.items()
            )
        ),
        docks=(DockDefinition("D01"),),
    )


def test_runtime_has_no_job_records_before_run():
    simulation = WarehouseSimulation(_scenario({"J001": 495}))

    assert simulation.runtime.jobs == {}
    assert simulation.event_log.records == ()


def test_job_is_admitted_as_waiting_at_actual_arrival_minute():
    simulation = WarehouseSimulation(_scenario({"J001": 495}))

    simulation.run()

    assert simulation.runtime.jobs == {
        "J001": JobRuntime("J001", JobStatus.WAITING, 495, None, None, None)
    }
    assert simulation.event_log.records == (
        EventRecord(495, EventType.JOB_ARRIVAL, "J001", None),
    )


def test_jobs_arriving_at_same_minute_are_all_admitted():
    simulation = WarehouseSimulation(_scenario({"J001": 600, "J002": 600}))

    simulation.run()

    assert {
        job_id: job.observed_arrival_min
        for job_id, job in simulation.runtime.jobs.items()
    } == {"J001": 600, "J002": 600}
    assert {record.job_id for record in simulation.event_log.records} == {
        "J001",
        "J002",
    }
    assert {record.time_min for record in simulation.event_log.records} == {600}


def test_spill_out_job_is_not_admitted():
    simulation = WarehouseSimulation(
        _scenario({"J001": 0, "J002": 1439, "J003": 1440, "J004": 1500})
    )

    simulation.run()

    assert set(simulation.runtime.jobs) == {"J001", "J002"}
    assert {record.job_id for record in simulation.event_log.records} == {
        "J001",
        "J002",
    }


def test_runs_of_same_scenario_have_independent_state():
    scenario = _scenario({"J001": 495})
    first = WarehouseSimulation(scenario)
    first.run()

    second = WarehouseSimulation(scenario)

    assert second.runtime.jobs == {}
    assert second.event_log.records == ()
    second.run()
    assert second.runtime.jobs == first.runtime.jobs
    assert second.runtime.jobs["J001"] is not first.runtime.jobs["J001"]
    assert len(first.event_log.records) == 1
