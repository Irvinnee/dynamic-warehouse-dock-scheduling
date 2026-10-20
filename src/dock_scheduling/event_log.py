from dataclasses import dataclass
from enum import Enum


class EventType(Enum):
    TRUCK_ARRIVAL = "TRUCK_ARRIVAL"
    RELOCATION_START = "RELOCATION_START"
    JOB_START = "JOB_START"
    JOB_END = "JOB_END"


@dataclass(frozen=True)
class EventRecord:
    time_min: int
    event_type: EventType
    truck_id: str
    job_id: str | None
    dock_id: str | None


class EventLog:
    def __init__(self) -> None:
        self._records: list[EventRecord] = []

    def record(
        self,
        time_min: int,
        event_type: EventType,
        truck_id: str,
        job_id: str | None = None,
        dock_id: str | None = None,
    ) -> None:
        self._records.append(
            EventRecord(time_min, event_type, truck_id, job_id, dock_id)
        )

    @property
    def records(self) -> tuple[EventRecord, ...]:
        return tuple(self._records)
