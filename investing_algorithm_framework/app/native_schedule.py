from datetime import datetime, timezone


class NativeScheduleUnsupported(ValueError):
    pass


def load_native_schedule():
    import iaf_confluence_native as native

    if getattr(native, 'EVENT_SCHEDULE_SEMANTICS_VERSION', None) != \
            'event-schedule-v1':
        raise NativeScheduleUnsupported('Incompatible native event scheduler')
    runner = getattr(native, 'run_event_schedule', None)
    if not callable(runner):
        raise NativeScheduleUnsupported(
            'Native event scheduler is unavailable'
        )
    return runner


def prepare_native_schedule(times, backend):
    if backend == 'python':
        return None, None

    try:
        runner = load_native_schedule()
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        timestamps = []
        for value in times:
            if type(value) is not datetime:
                raise NativeScheduleUnsupported(
                    'Native event schedule requires datetime keys'
                )
            try:
                normalized = value.replace(tzinfo=timezone.utc) \
                    if value.utcoffset() is None \
                    else value.astimezone(timezone.utc)
            except (OverflowError, ValueError) as exc:
                raise NativeScheduleUnsupported(
                    'Native event timestamp cannot be normalized to UTC'
                ) from exc
            delta = normalized - epoch
            timestamp = ((delta.days * 86400 + delta.seconds) * 1000000
                         + delta.microseconds)
            if timestamps and timestamp <= timestamps[-1]:
                raise NativeScheduleUnsupported(
                    'Native event schedule requires increasing UTC times'
                )
            timestamps.append(timestamp)
        return runner, timestamps
    except (ImportError, NativeScheduleUnsupported):
        if backend == 'rust':
            raise
        return None, None
