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
from dock_scheduling.runtime import JobStatus
from dock_scheduling.simulation import WarehouseSimulation

SERVICE_TIME_MIN = 30


def _scenario(arrivals: dict[str, int]) -> ScenarioDefinition:
    return ScenarioDefinition(
        plan=PlanSnapshot(
            jobs=tuple(
                JobPlan(
                    job_id, 0, OperationType.UNLOAD, False, SERVICE_TIME_MIN, "A", None
                )
                for job_id in arrivals
            )
        ),
        realization=RealizationDefinition(
            jobs=tuple(
                JobRealization(job_id, arrival_min, SERVICE_TIME_MIN)
                for job_id, arrival_min in arrivals.items()
            )
        ),
        docks=(DockDefinition("D01"),),
    )


def test_job_arrives_at_its_actual_arrival_minute():
    simulation = WarehouseSimulation(_scenario({"J001": 495}))

    simulation.run()

    job = simulation.runtime.jobs["J001"]
    assert (job.status, job.observed_arrival_min) == (JobStatus.WAITING, 495)
    assert simulation.event_log.records == (
        EventRecord(495, EventType.JOB_ARRIVAL, "J001", None),
    )


def test_service_ends_after_actual_service_time_and_frees_the_dock():
    simulation = WarehouseSimulation(_scenario({"J001": 495}))
    simulation.run(until_min=500)

    simulation.start_service("J001", "D01")
    simulation.run()

    job = simulation.runtime.jobs["J001"]
    assert (job.status, job.service_start_min, job.service_end_min) == (
        JobStatus.COMPLETED,
        500,
        530,
    )
    assert simulation.runtime.docks["D01"].current_job_id is None
    assert [record.event_type for record in simulation.event_log.records] == [
        EventType.JOB_ARRIVAL,
        EventType.SERVICE_START,
        EventType.SERVICE_END,
    ]


def test_arrivals_at_or_after_cutoff_are_ignored():
    simulation = WarehouseSimulation(
        _scenario({"J001": 0, "J002": 1439, "J003": 1440, "J004": 1500})
    )

    simulation.run()

    assert set(simulation.runtime.jobs) == {"J001", "J002"}
