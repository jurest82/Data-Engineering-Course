import datetime as dt


def is_valid_iso_datetime(value):
    if not isinstance(value, str):
        return False
    try:
        dt.datetime.fromisoformat(value)
        return True
    except ValueError:
        return False
