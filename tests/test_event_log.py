from dock_scheduling.event_log import EventLog, EventRecord, EventType


def test_job_arrival_is_recorded_without_dock():
    event_log = EventLog()

    event_log.record(495, EventType.JOB_ARRIVAL, "J001")

    assert event_log.records == (EventRecord(495, EventType.JOB_ARRIVAL, "J001", None),)


def test_service_events_are_recorded_with_dock():
    event_log = EventLog()

    event_log.record(495, EventType.SERVICE_START, "J001", "D01")
    event_log.record(525, EventType.SERVICE_END, "J001", "D01")

    assert event_log.records == (
        EventRecord(495, EventType.SERVICE_START, "J001", "D01"),
        EventRecord(525, EventType.SERVICE_END, "J001", "D01"),
    )


def test_records_keep_append_order_for_simultaneous_events():
    event_log = EventLog()

    event_log.record(520, EventType.SERVICE_END, "J001", "D01")
    event_log.record(520, EventType.JOB_ARRIVAL, "J002")
    event_log.record(520, EventType.SERVICE_START, "J002", "D01")

    assert [(record.event_type, record.job_id) for record in event_log.records] == [
        (EventType.SERVICE_END, "J001"),
        (EventType.JOB_ARRIVAL, "J002"),
        (EventType.SERVICE_START, "J002"),
    ]
