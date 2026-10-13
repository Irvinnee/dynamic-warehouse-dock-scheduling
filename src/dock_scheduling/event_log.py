from dataclasses import dataclass
from enum import Enum


class EventType(Enum):
    JOB_ARRIVAL = "JOB_ARRIVAL"
    SERVICE_START = "SERVICE_START"
    SERVICE_END = "SERVICE_END"


@dataclass(frozen=True)
class EventRecord:
    time_min: int
    event_type: EventType
    job_id: str
    dock_id: str | None


class EventLog:
    """In-memory trace of one simulation run, in append order.

    Runtime timestamps in JobRuntime stay authoritative for metrics.
    """

    def __init__(self) -> None:
        self._records: list[EventRecord] = []

    def record(
        self,
        time_min: int,
        event_type: EventType,
        job_id: str,
        dock_id: str | None = None,
    ) -> None:
        self._records.append(EventRecord(time_min, event_type, job_id, dock_id))

    @property
    def records(self) -> tuple[EventRecord, ...]:
        return tuple(self._records)
