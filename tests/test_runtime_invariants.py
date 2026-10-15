from dock_scheduling.domain import (
    DockDefinition,
    JobPlan,
    JobRealization,
    OperationType,
    PlanSnapshot,
    RealizationDefinition,
    ScenarioDefinition,
)
from dock_scheduling.runtime import DockStatus, JobRuntime, JobStatus, RuntimeState
from dock_scheduling.scheduler import FCFSScheduler
from dock_scheduling.simulation import WarehouseSimulation

WAITING = JobStatus.WAITING
IN_SERVICE = JobStatus.IN_SERVICE
COMPLETED = JobStatus.COMPLETED


def _scenario(jobs: dict[str, tuple[int, int]]) -> ScenarioDefinition:
    return ScenarioDefinition(
        plan=PlanSnapshot(
            jobs=tuple(
                JobPlan(job_id, 0, OperationType.UNLOAD, False, service_min, "A", None)
                for job_id, (_, service_min) in jobs.items()
            )
        ),
        realization=RealizationDefinition(
            jobs=tuple(
                JobRealization(job_id, arrival_min, service_min)
                for job_id, (arrival_min, service_min) in jobs.items()
            )
        ),
        docks=(DockDefinition("D01"), DockDefinition("D02")),
    )


def _assert_runtime_consistent(runtime: RuntimeState) -> None:
    for dock in runtime.docks.values():
        if dock.status is DockStatus.FREE:
            assert dock.current_job_id is None
        else:
            assert dock.current_job_id in runtime.jobs
            job = runtime.jobs[dock.current_job_id]
            assert job.status is IN_SERVICE
            assert job.assigned_dock_id == dock.dock_id

    for job in runtime.jobs.values():
        holding_docks = [
            dock for dock in runtime.docks.values() if dock.current_job_id == job.job_id
        ]
        if job.status is WAITING:
            assert holding_docks == []
            assert job.service_start_min is None
            assert job.service_end_min is None
            assert job.assigned_dock_id is None
        elif job.status is IN_SERVICE:
            assert len(holding_docks) == 1
            assert holding_docks[0].status is DockStatus.BUSY
            assert holding_docks[0].dock_id == job.assigned_dock_id
            assert job.service_start_min is not None
            assert job.service_end_min is None
            assert job.service_start_min >= job.observed_arrival_min
        else:
            assert holding_docks == []
            assert job.service_start_min is not None
            assert job.service_end_min is not None
            assert job.assigned_dock_id is not None
            assert (
                job.observed_arrival_min <= job.service_start_min <= job.service_end_min
            )


def _statuses(runtime: RuntimeState) -> dict[str, JobStatus]:
    return {job_id: job.status for job_id, job in runtime.jobs.items()}


def _dock_jobs(runtime: RuntimeState) -> dict[str, str | None]:
    return {dock_id: dock.current_job_id for dock_id, dock in runtime.docks.items()}


def test_runtime_stays_consistent_through_batch_waiting_and_dock_reuse():
    simulation = WarehouseSimulation(
        _scenario(
            {
                "J001": (100, 40),
                "J002": (100, 30),
                "J003": (110, 20),
                "J004": (120, 10),
            }
        ),
        FCFSScheduler(),
    )
    runtime = simulation.runtime

    simulation.run(until_min=101)
    _assert_runtime_consistent(runtime)
    assert _statuses(runtime) == {"J001": IN_SERVICE, "J002": IN_SERVICE}
    assert _dock_jobs(runtime) == {"D01": "J001", "D02": "J002"}

    simulation.run(until_min=111)
    _assert_runtime_consistent(runtime)
    assert _statuses(runtime)["J003"] is WAITING
    assert _dock_jobs(runtime) == {"D01": "J001", "D02": "J002"}

    simulation.run(until_min=121)
    _assert_runtime_consistent(runtime)
    assert _statuses(runtime)["J003"] is WAITING
    assert _statuses(runtime)["J004"] is WAITING
    assert _dock_jobs(runtime) == {"D01": "J001", "D02": "J002"}

    simulation.run(until_min=131)
    _assert_runtime_consistent(runtime)
    assert _statuses(runtime)["J002"] is COMPLETED
    assert _dock_jobs(runtime) == {"D01": "J001", "D02": "J003"}

    simulation.run(until_min=141)
    _assert_runtime_consistent(runtime)
    assert _statuses(runtime)["J001"] is COMPLETED
    assert _dock_jobs(runtime) == {"D01": "J004", "D02": "J003"}

    simulation.run(until_min=151)
    _assert_runtime_consistent(runtime)
    assert set(_statuses(runtime).values()) == {COMPLETED}
    assert _dock_jobs(runtime) == {"D01": None, "D02": None}

    assert runtime.jobs == {
        job_id: JobRuntime(
            job_id=job_id,
            status=COMPLETED,
            observed_arrival_min=arrival_min,
            service_start_min=start_min,
            service_end_min=end_min,
            assigned_dock_id=dock_id,
        )
        for job_id, arrival_min, start_min, end_min, dock_id in [
            ("J001", 100, 100, 140, "D01"),
            ("J002", 100, 100, 130, "D02"),
            ("J003", 110, 130, 150, "D02"),
            ("J004", 120, 140, 150, "D01"),
        ]
    }
