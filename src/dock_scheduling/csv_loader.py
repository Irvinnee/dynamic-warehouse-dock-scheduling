import csv
import re
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from dock_scheduling.domain import (
    DockDefinition,
    JobPlan,
    JobRealization,
    OperationType,
    PlanSnapshot,
    RealizationDefinition,
    ScenarioDefinition,
)
from dock_scheduling.scenario_validation import validate_scenario

PLAN_FIELDS = (
    "job_id",
    "planned_arrival_min",
    "operation",
    "priority",
    "estimated_service_time_min",
    "unload_section",
    "load_section",
)
REALIZATION_FIELDS = ("job_id", "actual_arrival_min", "actual_service_time_min")

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


def load_scenario(
    plan_path: Path,
    realization_path: Path,
    docks: tuple[DockDefinition, ...],
) -> ScenarioDefinition:
    errors: list[str] = []
    plan_jobs = _read_rows(plan_path, PLAN_FIELDS, _parse_job_plan, errors)
    realization_jobs = _read_rows(
        realization_path, REALIZATION_FIELDS, _parse_job_realization, errors
    )
    if errors:
        raise CsvParseError(errors)

    scenario = ScenarioDefinition(
        plan=PlanSnapshot(jobs=plan_jobs),
        realization=RealizationDefinition(jobs=realization_jobs),
        docks=docks,
    )
    validate_scenario(scenario)
    return scenario


def _read_rows[T](
    path: Path,
    fields: tuple[str, ...],
    parse_row: Callable[[dict[str, str]], T],
    errors: list[str],
) -> tuple[T, ...]:
    parsed: list[T] = []
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
            return ()

        for row in reader:
            location = f"{path} line {reader.line_num}"
            if None in row or None in row.values():
                errors.append(
                    f"{location}: expected {len(fields)} cells per row, "
                    "row has a different number"
                )
                continue
            try:
                parsed.append(parse_row(row))
            except _FieldError as error:
                errors.append(
                    f"{location}, field {error.field_name!r}: invalid value "
                    f"{error.value!r}, expected {error.expected}"
                )
    return tuple(parsed)


def _parse_job_plan(row: dict[str, str]) -> JobPlan:
    return JobPlan(
        job_id=row["job_id"],
        planned_arrival_min=_parse_integer(row, "planned_arrival_min"),
        operation=_parse_operation(row),
        priority=_parse_priority(row),
        estimated_service_time_min=_parse_integer(row, "estimated_service_time_min"),
        unload_section=row["unload_section"] or None,
        load_section=row["load_section"] or None,
    )


def _parse_job_realization(row: dict[str, str]) -> JobRealization:
    return JobRealization(
        job_id=row["job_id"],
        actual_arrival_min=_parse_integer(row, "actual_arrival_min"),
        actual_service_time_min=_parse_integer(row, "actual_service_time_min"),
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
