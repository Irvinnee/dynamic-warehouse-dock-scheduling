from dataclasses import dataclass
from statistics import fmean

from dock_scheduling.runtime import RuntimeState


@dataclass(frozen=True)
class SimulationMetrics:
    mean_job_waiting_time_min: float
    max_job_waiting_time_min: int
    mean_truck_turnaround_time_min: float
    makespan_min: int
    total_relocation_time_min: int


def calculate_metrics(runtime: RuntimeState) -> SimulationMetrics:
    trucks = list(runtime.trucks.values())
    jobs = list(runtime.jobs.values())
    unfinished = [truck.truck_id for truck in trucks if truck.completed_min is None]
    if unfinished:
        raise ValueError(
            f"metrics need a finished run, unfinished trucks: {unfinished}"
        )
    if not trucks:
        return SimulationMetrics(0.0, 0, 0.0, 0, 0)

    waiting_times = [job.assigned_min - job.eligible_since_min for job in jobs]
    return SimulationMetrics(
        mean_job_waiting_time_min=fmean(waiting_times),
        max_job_waiting_time_min=max(waiting_times),
        mean_truck_turnaround_time_min=fmean(
            truck.completed_min - truck.observed_arrival_min for truck in trucks
        ),
        makespan_min=max(truck.completed_min for truck in trucks),
        total_relocation_time_min=sum(
            job.service_start_min - job.assigned_min for job in jobs
        ),
    )
