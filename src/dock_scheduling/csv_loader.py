import csv
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
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
from dock_scheduling.scenario_validation import validate_scenario

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

_PRIORITY_VALUES = {"true": True, "false": False}

_INTEGER_PATTERN = re.compile(r"-?[0-9]+")


class CsvParseError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__(
            "invalid CSV input:\n" + "\n".join(f"- {error}" for error in errors)
        )
        self.errors = tuple(errors)


class _FieldError(Exception):
    def __init__(self, field_name: str, value: str, expected: str) -> None:
        self.field_name = field_name
        self.value = value
        self.expected = expected


@dataclass(frozen=True)
class _TruckRow:
    truck_id: str
    planned_arrival_min: int
    priority: bool


@dataclass(frozen=True)
class _JobRow:
    truck_id: str
    sequence: int
    job: JobPlan


@dataclass(frozen=True)
class _RealizationRow:
    truck_id: str
    actual_arrival_min: int
    job: JobRealization


def load_scenario(
    plan_trucks_path: Path,
    plan_jobs_path: Path,
    realization_path: Path,
    docks: tuple[DockDefinition, ...],
    relocation_time_min: int,
) -> ScenarioDefinition:
    errors: list[str] = []
    truck_rows = _read_rows(
        plan_trucks_path, PLAN_TRUCK_FIELDS, _parse_truck_row, errors
    )
    job_rows = _read_rows(plan_jobs_path, PLAN_JOB_FIELDS, _parse_job_row, errors)
    realization_rows = _read_rows(
        realization_path, REALIZATION_FIELDS, _parse_realization_row, errors
    )
    if errors:
        raise CsvParseError(errors)

    plan = _build_plan(plan_trucks_path, truck_rows, plan_jobs_path, job_rows, errors)
    realization = _build_realization(
        realization_path, realization_rows, plan_jobs_path, job_rows, errors
    )
    if errors:
        raise CsvParseError(errors)

    scenario = ScenarioDefinition(
        plan=plan,
        realization=realization,
        docks=docks,
        relocation_time_min=relocation_time_min,
    )
    validate_scenario(scenario)
    return scenario


def _read_rows[T](
    path: Path,
    fields: tuple[str, ...],
    parse_row: Callable[[dict[str, str]], T],
    errors: list[str],
) -> list[tuple[int, T]]:
    parsed: list[tuple[int, T]] = []
    with path.open(encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        header = reader.fieldnames or []
        missing = [field for field in fields if field not in header]
        unexpected = [field for field in header if field not in fields]
        duplicated = [field for field, count in Counter(header).items() if count > 1]
        if missing or unexpected or duplicated:
            errors.append(
                f"{path}: header must contain each of {list(fields)} exactly once, "
                f"missing {missing}, unexpected {unexpected}, duplicated {duplicated}"
            )
            return []

        for row in reader:
            location = f"{path} line {reader.line_num}"
            if None in row or None in row.values():
                errors.append(
                    f"{location}: expected {len(fields)} cells per row, "
                    "row has a different number"
                )
                continue
            try:
                parsed.append((reader.line_num, parse_row(row)))
            except _FieldError as error:
                errors.append(
                    f"{location}, field {error.field_name!r}: invalid value "
                    f"{error.value!r}, expected {error.expected}"
                )
    return parsed


def _build_plan(
    plan_trucks_path: Path,
    truck_rows: list[tuple[int, _TruckRow]],
    plan_jobs_path: Path,
    job_rows: list[tuple[int, _JobRow]],
    errors: list[str],
) -> PlanSnapshot:
    known_truck_ids = {truck_row.truck_id for _, truck_row in truck_rows}
    rows_by_truck: dict[str, list[tuple[int, _JobRow]]] = {}
    for line, job_row in job_rows:
        if job_row.truck_id not in known_truck_ids:
            errors.append(
                f"{plan_jobs_path} line {line}: truck_id {job_row.truck_id!r} "
                f"is not defined in {plan_trucks_path}"
            )
            continue
        rows_by_truck.setdefault(job_row.truck_id, []).append((line, job_row))
    for truck_id, rows in rows_by_truck.items():
        _check_sequence(plan_jobs_path, truck_id, rows, errors)

    return PlanSnapshot(
        trucks=tuple(
            TruckPlan(
                truck_id=truck_row.truck_id,
                planned_arrival_min=truck_row.planned_arrival_min,
                priority=truck_row.priority,
                jobs=tuple(
                    job_row.job
                    for _, job_row in sorted(
                        rows_by_truck.get(truck_row.truck_id, []),
                        key=lambda line_and_row: line_and_row[1].sequence,
                    )
                ),
            )
            for _, truck_row in truck_rows
        )
    )


def _check_sequence(
    path: Path, truck_id: str, rows: list[tuple[int, _JobRow]], errors: list[str]
) -> None:
    lines_by_sequence: dict[int, list[int]] = {}
    for line, job_row in rows:
        lines_by_sequence.setdefault(job_row.sequence, []).append(line)
    repeated = {
        sequence: lines
        for sequence, lines in lines_by_sequence.items()
        if len(lines) > 1
    }
    for sequence, lines in repeated.items():
        errors.append(
            f"{path} lines {', '.join(map(str, lines))}: truck {truck_id!r} "
            f"repeats sequence {sequence}"
        )
    sequences = sorted(lines_by_sequence)
    if not repeated and sequences != list(range(1, len(rows) + 1)):
        errors.append(
            f"{path}: truck {truck_id!r} sequence must be contiguous from 1 to "
            f"{len(rows)}, got {sequences}"
        )


def _build_realization(
    realization_path: Path,
    realization_rows: list[tuple[int, _RealizationRow]],
    plan_jobs_path: Path,
    job_rows: list[tuple[int, _JobRow]],
    errors: list[str],
) -> RealizationDefinition:
    # a duplicated job_id can belong to several trucks, validation reports that,
    # here a row just has to match one of them
    planned_trucks_by_job: dict[str, set[str]] = {}
    for _, job_row in job_rows:
        planned_trucks_by_job.setdefault(job_row.job.job_id, set()).add(
            job_row.truck_id
        )

    first_arrival_by_truck: dict[str, tuple[int, int]] = {}
    for line, realization_row in realization_rows:
        truck_id = realization_row.truck_id
        first_arrival_min, first_line = first_arrival_by_truck.setdefault(
            truck_id, (realization_row.actual_arrival_min, line)
        )
        if realization_row.actual_arrival_min != first_arrival_min:
            errors.append(
                f"{realization_path} line {line}: truck {truck_id!r} "
                f"actual_arrival_min {realization_row.actual_arrival_min} differs "
                f"from {first_arrival_min} on line {first_line}"
            )
        job_id = realization_row.job.job_id
        planned_trucks = planned_trucks_by_job.get(job_id)
        if planned_trucks is not None and truck_id not in planned_trucks:
            planned = " or ".join(repr(planned) for planned in sorted(planned_trucks))
            errors.append(
                f"{realization_path} line {line}: job {job_id!r} belongs to truck "
                f"{planned} in {plan_jobs_path}, got {truck_id!r}"
            )

    return RealizationDefinition(
        trucks=tuple(
            TruckRealization(truck_id, arrival_min)
            for truck_id, (arrival_min, _) in first_arrival_by_truck.items()
        ),
        jobs=tuple(realization_row.job for _, realization_row in realization_rows),
    )


def _parse_truck_row(row: dict[str, str]) -> _TruckRow:
    return _TruckRow(
        truck_id=row["truck_id"],
        planned_arrival_min=_parse_integer(row, "planned_arrival_min"),
        priority=_parse_priority(row),
    )


def _parse_job_row(row: dict[str, str]) -> _JobRow:
    return _JobRow(
        truck_id=row["truck_id"],
        sequence=_parse_integer(row, "sequence"),
        job=JobPlan(
            job_id=row["job_id"],
            operation=_parse_operation(row),
            section=row["section"],
            estimated_service_time_min=_parse_integer(
                row, "estimated_service_time_min"
            ),
        ),
    )


def _parse_realization_row(row: dict[str, str]) -> _RealizationRow:
    return _RealizationRow(
        truck_id=row["truck_id"],
        actual_arrival_min=_parse_integer(row, "actual_arrival_min"),
        job=JobRealization(
            job_id=row["job_id"],
            actual_service_time_min=_parse_integer(row, "actual_service_time_min"),
        ),
    )


def _parse_integer(row: dict[str, str], field_name: str) -> int:
    value = row[field_name]
    if not _INTEGER_PATTERN.fullmatch(value):
        raise _FieldError(field_name, value, "an integer")
    return int(value)


def _parse_operation(row: dict[str, str]) -> OperationType:
    value = row["operation"]
    try:
        return OperationType(value)
    except ValueError:
        expected = " or ".join(operation.value for operation in OperationType)
        raise _FieldError("operation", value, expected) from None


def _parse_priority(row: dict[str, str]) -> bool:
    value = row["priority"]
    if value not in _PRIORITY_VALUES:
        raise _FieldError("priority", value, "true or false")
    return _PRIORITY_VALUES[value]
