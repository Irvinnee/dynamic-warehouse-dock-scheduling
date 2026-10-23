import csv
import re
from pathlib import Path

from dock_scheduling.domain import (
    DockDefinition,
    JobPlan,
    JobRealization,
    OperationType,
    PlanSnapshot,
    RealizationDefinition,
    ScenarioDefinition,
    TruckPlan,
    TruckRealization,
)
from dock_scheduling.scenario_validation import (
    InvalidScenarioError,
    validate_plan,
    validate_scenario,
)

PLAN_TRUCK_FIELDS = ("truck_id", "planned_arrival_min", "priority")
PLAN_JOB_FIELDS = (
    "job_id",
    "truck_id",
    "sequence",
    "operation",
    "section",
    "estimated_service_time_min",
)
REALIZATION_FIELDS = (
    "truck_id",
    "job_id",
    "actual_arrival_min",
    "actual_service_time_min",
)

_INTEGER = re.compile(r"-?[0-9]+")
_BOOLEANS = {"true": True, "false": False}
_OPERATIONS = {operation.value: operation for operation in OperationType}

# (where, row), where is e.g. "plan_jobs.csv line 4"
type _Rows = list[tuple[str, dict[str, str]]]


def load_scenario(
    plan_trucks_path: Path,
    plan_jobs_path: Path,
    realization_path: Path,
    docks: tuple[DockDefinition, ...],
    relocation_time_min: int,
) -> ScenarioDefinition:
    plan = _build_plan(
        _read_csv(plan_trucks_path, PLAN_TRUCK_FIELDS),
        _read_csv(plan_jobs_path, PLAN_JOB_FIELDS),
    )
    # realization rows are matched by job_id, so ids have to be unique first
    validate_plan(plan)
    scenario = ScenarioDefinition(
        plan=plan,
        realization=_build_realization(
            _read_csv(realization_path, REALIZATION_FIELDS), plan
        ),
        docks=docks,
        relocation_time_min=relocation_time_min,
    )
    validate_scenario(scenario)
    return scenario


def _read_csv(path: Path, fields: tuple[str, ...]) -> _Rows:
    # utf-8-sig handles the BOM Excel likes to add
    with path.open(encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        header = reader.fieldnames or []
        if sorted(header) != sorted(fields):
            raise InvalidScenarioError(
                f"{path.name}: expected columns {', '.join(fields)}, "
                f"got {', '.join(header)}"
            )
        rows = []
        for row in reader:
            where = f"{path.name} line {reader.line_num}"
            # DictReader puts extra cells under None and fills missing ones with None
            if None in row or None in row.values():
                raise InvalidScenarioError(f"{where}: expected {len(fields)} values")
            rows.append((where, row))
    return rows


def _build_plan(truck_rows: _Rows, job_rows: _Rows) -> PlanSnapshot:
    truck_ids = {row["truck_id"] for _, row in truck_rows}
    jobs_by_truck: dict[str, list[tuple[int, JobPlan]]] = {}
    for where, row in job_rows:
        if row["truck_id"] not in truck_ids:
            raise InvalidScenarioError(
                f"job {row['job_id']!r} references unknown truck {row['truck_id']!r}"
            )
        job = JobPlan(
            job_id=row["job_id"],
            operation=_parse_choice(where, row, "operation", _OPERATIONS),
            section=row["section"],
            estimated_service_time_min=_parse_int(
                where, row, "estimated_service_time_min"
            ),
        )
        sequence = _parse_int(where, row, "sequence")
        jobs_by_truck.setdefault(row["truck_id"], []).append((sequence, job))

    trucks = []
    for where, row in truck_rows:
        truck_id = row["truck_id"]
        jobs = sorted(jobs_by_truck.get(truck_id, []), key=lambda item: item[0])
        sequences = [sequence for sequence, _ in jobs]
        if sequences != list(range(1, len(jobs) + 1)):
            raise InvalidScenarioError(
                f"truck {truck_id!r}: job sequence must be 1..{len(jobs)}, "
                f"got {sequences}"
            )
        trucks.append(
            TruckPlan(
                truck_id=truck_id,
                planned_arrival_min=_parse_int(where, row, "planned_arrival_min"),
                priority=_parse_choice(where, row, "priority", _BOOLEANS),
                jobs=tuple(job for _, job in jobs),
            )
        )
    return PlanSnapshot(trucks=tuple(trucks))


def _build_realization(rows: _Rows, plan: PlanSnapshot) -> RealizationDefinition:
    truck_by_job = {
        job.job_id: truck.truck_id for truck in plan.trucks for job in truck.jobs
    }
    arrival_by_truck: dict[str, int] = {}
    jobs = []
    for where, row in rows:
        truck_id = row["truck_id"]
        job_id = row["job_id"]
        arrival_min = _parse_int(where, row, "actual_arrival_min")
        first_arrival_min = arrival_by_truck.setdefault(truck_id, arrival_min)
        if arrival_min != first_arrival_min:
            raise InvalidScenarioError(
                f"truck {truck_id!r}: actual_arrival_min {arrival_min} differs "
                f"from {first_arrival_min}"
            )
        # unknown job ids are left for validate_scenario
        planned_truck_id = truck_by_job.get(job_id, truck_id)
        if planned_truck_id != truck_id:
            raise InvalidScenarioError(
                f"job {job_id!r} belongs to truck {planned_truck_id!r}, "
                f"got {truck_id!r}"
            )
        jobs.append(
            JobRealization(job_id, _parse_int(where, row, "actual_service_time_min"))
        )

    return RealizationDefinition(
        trucks=tuple(
            TruckRealization(truck_id, arrival_min)
            for truck_id, arrival_min in arrival_by_truck.items()
        ),
        jobs=tuple(jobs),
    )


def _parse_int(where: str, row: dict[str, str], field: str) -> int:
    if not _INTEGER.fullmatch(row[field]):
        raise InvalidScenarioError(f"{where}: invalid {field} {row[field]!r}")
    return int(row[field])


def _parse_choice[T](
    where: str, row: dict[str, str], field: str, values: dict[str, T]
) -> T:
    if row[field] not in values:
        raise InvalidScenarioError(
            f"{where}: invalid {field} {row[field]!r}, expected one of {list(values)}"
        )
    return values[row[field]]
