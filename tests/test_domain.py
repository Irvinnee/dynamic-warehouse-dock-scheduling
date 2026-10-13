from dataclasses import FrozenInstanceError

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


def test_scenario_definition_cannot_be_modified():
    scenario = ScenarioDefinition(
        plan=PlanSnapshot(
            jobs=(
                JobPlan(
                    job_id="J001",
                    planned_arrival_min=480,
                    operation=OperationType.UNLOAD,
                    priority=False,
                    estimated_service_time_min=30,
                    unload_section="A",
                    load_section=None,
                ),
            )
        ),
        realization=RealizationDefinition(
            jobs=(
                JobRealization(
                    job_id="J001",
                    actual_arrival_min=495,
                    actual_service_time_min=30,
                ),
            )
        ),
        docks=(DockDefinition(dock_id="D01"),),
    )

    with pytest.raises(FrozenInstanceError):
        scenario.docks = ()
    with pytest.raises(FrozenInstanceError):
        scenario.plan.jobs = ()
    with pytest.raises(FrozenInstanceError):
        scenario.realization.jobs = ()
