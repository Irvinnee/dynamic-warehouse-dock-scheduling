import pytest

from dock_scheduling.domain import (
    DockDefinition,
    JobPlan,
    JobRealization,
    OperationType,
    PlanSnapshot,
    RealizationDefinition,
    ScenarioDefinition,
)
from dock_scheduling.scenario_validation import (
    ScenarioValidationError,
    validate_scenario,
)


def _plan(
    job_id: str = "J001",
    planned_arrival_min: int = 480,
    operation: OperationType = OperationType.UNLOAD,
    estimated_service_time_min: int = 30,
    unload_section: str | None = "A",
    load_section: str | None = None,
) -> JobPlan:
    return JobPlan(
        job_id=job_id,
        planned_arrival_min=planned_arrival_min,
        operation=operation,
        priority=False,
        estimated_service_time_min=estimated_service_time_min,
        unload_section=unload_section,
        load_section=load_section,
    )


def _realization(
    job_id: str = "J001",
    actual_arrival_min: int = 495,
    actual_service_time_min: int = 30,
) -> JobRealization:
    return JobRealization(
        job_id=job_id,
        actual_arrival_min=actual_arrival_min,
        actual_service_time_min=actual_service_time_min,
    )


def _scenario(
    plan_jobs: tuple[JobPlan, ...] = (_plan(),),
    realization_jobs: tuple[JobRealization, ...] = (_realization(),),
    docks: tuple[DockDefinition, ...] = (DockDefinition("D01"),),
) -> ScenarioDefinition:
    return ScenarioDefinition(
        plan=PlanSnapshot(jobs=plan_jobs),
        realization=RealizationDefinition(jobs=realization_jobs),
        docks=docks,
    )


def _errors(scenario: ScenarioDefinition) -> tuple[str, ...]:
    with pytest.raises(ScenarioValidationError) as excinfo:
        validate_scenario(scenario)
    return excinfo.value.errors


def test_valid_scenario_passes():
    validate_scenario(
        _scenario(
            plan_jobs=(
                _plan(
                    "J001",
                    operation=OperationType.LOAD,
                    unload_section=None,
                    load_section="B",
                ),
                _plan("J002", operation=OperationType.UNLOAD, unload_section="A"),
                _plan(
                    "J003",
                    operation=OperationType.BOTH,
                    unload_section="A",
                    load_section="B",
                ),
            ),
            realization_jobs=(
                _realization("J001"),
                _realization("J002"),
                _realization("J003"),
            ),
            docks=(DockDefinition("D01"), DockDefinition("D02")),
        )
    )


def test_negative_planned_arrival_is_accepted():
    validate_scenario(
        _scenario(
            plan_jobs=(_plan(planned_arrival_min=-120),),
            realization_jobs=(_realization(actual_arrival_min=90),),
        )
    )


@pytest.mark.parametrize("actual_arrival_min", [1440, 1500])
def test_spill_out_arrival_is_accepted(actual_arrival_min):
    validate_scenario(
        _scenario(
            realization_jobs=(_realization(actual_arrival_min=actual_arrival_min),)
        )
    )


def test_empty_plan_job_id_is_rejected():
    errors = _errors(
        _scenario(plan_jobs=(_plan(""),), realization_jobs=(_realization(""),))
    )

    assert errors == (
        "plan job at index 0 has an empty job_id",
        "realization at index 0 has an empty job_id",
    )


def test_empty_realization_job_id_is_rejected_as_identifier_error():
    errors = _errors(
        _scenario(realization_jobs=(_realization("J001"), _realization("")))
    )

    assert errors == (
        "realization at index 1 has an empty job_id",
        "realization '': no planned job",
    )


def test_whitespace_only_plan_job_id_is_rejected():
    errors = _errors(
        _scenario(
            plan_jobs=(_plan(" "), _plan("J001")),
            realization_jobs=(_realization("J001"),),
        )
    )

    assert errors == (
        "plan job at index 0 has a whitespace-only job_id",
        "job ' ': no realization",
    )


def test_whitespace_only_realization_job_id_is_rejected():
    errors = _errors(
        _scenario(realization_jobs=(_realization("J001"), _realization("\t")))
    )

    assert errors == (
        "realization at index 1 has a whitespace-only job_id",
        "realization '\\t': no planned job",
    )


def test_duplicate_plan_job_id_is_rejected():
    errors = _errors(_scenario(plan_jobs=(_plan("J001"), _plan("J001"))))

    assert errors == ("plan: duplicate job_id 'J001'",)


def test_duplicate_realization_job_id_is_rejected():
    errors = _errors(
        _scenario(realization_jobs=(_realization("J001"), _realization("J001")))
    )

    assert errors == ("realization: duplicate job_id 'J001'",)


def test_planned_job_without_realization_is_rejected():
    errors = _errors(
        _scenario(
            plan_jobs=(_plan("J001"), _plan("J002")),
            realization_jobs=(_realization("J001"),),
        )
    )

    assert errors == ("job 'J002': no realization",)


def test_realization_without_planned_job_is_rejected():
    errors = _errors(
        _scenario(realization_jobs=(_realization("J001"), _realization("J999")))
    )

    assert errors == ("realization 'J999': no planned job",)


def test_scenario_without_docks_is_rejected():
    assert _errors(_scenario(docks=())) == ("scenario has no docks",)


def test_empty_dock_id_is_rejected():
    errors = _errors(_scenario(docks=(DockDefinition(""),)))

    assert errors == ("dock at index 0 has an empty dock_id",)


def test_whitespace_only_dock_id_is_rejected():
    errors = _errors(_scenario(docks=(DockDefinition("  "),)))

    assert errors == ("dock at index 0 has a whitespace-only dock_id",)


def test_duplicate_dock_id_is_rejected():
    errors = _errors(_scenario(docks=(DockDefinition("D01"), DockDefinition("D01"))))

    assert errors == ("duplicate dock_id 'D01'",)


@pytest.mark.parametrize(
    ("operation", "unload_section", "load_section", "expected_errors"),
    [
        (OperationType.LOAD, None, None, ["LOAD requires a non-empty load_section"]),
        (OperationType.LOAD, None, "", ["LOAD requires a non-empty load_section"]),
        (OperationType.LOAD, "A", "B", ["LOAD must not define unload_section"]),
        (OperationType.LOAD, "", "B", ["LOAD must not define unload_section"]),
        (
            OperationType.UNLOAD,
            None,
            None,
            ["UNLOAD requires a non-empty unload_section"],
        ),
        (
            OperationType.UNLOAD,
            "",
            None,
            ["UNLOAD requires a non-empty unload_section"],
        ),
        (OperationType.UNLOAD, "A", "B", ["UNLOAD must not define load_section"]),
        (OperationType.UNLOAD, "A", "", ["UNLOAD must not define load_section"]),
        (OperationType.BOTH, "A", None, ["BOTH requires a non-empty load_section"]),
        (OperationType.BOTH, None, "B", ["BOTH requires a non-empty unload_section"]),
        (
            OperationType.BOTH,
            "",
            "",
            [
                "BOTH requires a non-empty load_section",
                "BOTH requires a non-empty unload_section",
            ],
        ),
    ],
)
def test_invalid_section_combination_is_rejected(
    operation, unload_section, load_section, expected_errors
):
    errors = _errors(
        _scenario(
            plan_jobs=(
                _plan(
                    operation=operation,
                    unload_section=unload_section,
                    load_section=load_section,
                ),
            )
        )
    )

    assert errors == tuple(f"job 'J001': {message}" for message in expected_errors)


def test_negative_actual_arrival_is_rejected():
    errors = _errors(_scenario(realization_jobs=(_realization(actual_arrival_min=-1),)))

    assert errors == ("job 'J001': actual_arrival_min must be >= 0, got -1",)


@pytest.mark.parametrize("service_time_min", [0, -5])
def test_non_positive_estimated_service_time_is_rejected(service_time_min):
    errors = _errors(
        _scenario(
            plan_jobs=(_plan(estimated_service_time_min=service_time_min),),
            realization_jobs=(_realization(actual_service_time_min=service_time_min),),
        )
    )

    assert (
        f"job 'J001': estimated_service_time_min must be > 0, got {service_time_min}"
        in errors
    )


@pytest.mark.parametrize("service_time_min", [0, -5])
def test_non_positive_actual_service_time_is_rejected(service_time_min):
    errors = _errors(
        _scenario(
            plan_jobs=(_plan(estimated_service_time_min=service_time_min),),
            realization_jobs=(_realization(actual_service_time_min=service_time_min),),
        )
    )

    assert (
        f"job 'J001': actual_service_time_min must be > 0, got {service_time_min}"
        in errors
    )


def test_actual_service_time_different_from_estimate_is_rejected():
    errors = _errors(
        _scenario(
            plan_jobs=(_plan(estimated_service_time_min=30),),
            realization_jobs=(_realization(actual_service_time_min=45),),
        )
    )

    expected = (
        "job 'J001': actual_service_time_min 45 must equal "
        "estimated_service_time_min 30 in V1"
    )
    assert errors == (expected,)


def test_independent_errors_are_collected_together():
    errors = _errors(
        _scenario(
            plan_jobs=(_plan("J001", unload_section=None),),
            realization_jobs=(_realization("J001", actual_arrival_min=-10),),
            docks=(),
        )
    )

    assert set(errors) == {
        "scenario has no docks",
        "job 'J001': UNLOAD requires a non-empty unload_section",
        "job 'J001': actual_arrival_min must be >= 0, got -10",
    }


def test_duplicated_plan_job_without_realization_is_reported_once():
    errors = _errors(
        _scenario(
            plan_jobs=(_plan("J001"), _plan("J002"), _plan("J002")),
            realization_jobs=(_realization("J001"),),
        )
    )

    assert errors == (
        "plan: duplicate job_id 'J002'",
        "job 'J002': no realization",
    )


def test_duplicated_realization_without_planned_job_is_reported_once():
    errors = _errors(
        _scenario(
            realization_jobs=(
                _realization("J001"),
                _realization("J999"),
                _realization("J999"),
            )
        )
    )

    assert errors == (
        "realization: duplicate job_id 'J999'",
        "realization 'J999': no planned job",
    )


def test_service_time_mismatch_is_not_reported_for_duplicated_plan_job_id():
    errors = _errors(
        _scenario(
            plan_jobs=(
                _plan("J001", estimated_service_time_min=30),
                _plan("J001", estimated_service_time_min=45),
            ),
            realization_jobs=(_realization("J001", actual_service_time_min=30),),
        )
    )

    assert errors == ("plan: duplicate job_id 'J001'",)


def test_service_time_mismatch_is_not_reported_for_duplicated_realization_job_id():
    errors = _errors(
        _scenario(
            plan_jobs=(_plan("J001", estimated_service_time_min=30),),
            realization_jobs=(
                _realization("J001", actual_service_time_min=30),
                _realization("J001", actual_service_time_min=45),
            ),
        )
    )

    assert errors == ("realization: duplicate job_id 'J001'",)
