from src.common.cities import ALLOWED_CITIES
from src.common.validators import is_valid_iso_datetime

MAX_SPEED_AVG = 200
MIN_VEHICLE_COUNT = 0


def validate_reading(reading):
    """Defense in depth: the reading should already be valid by the time it
    reaches this point (e.g. one read back from an SQS message)."""
    errors = []

    sensor_id = reading.get('sensor_id')
    if not isinstance(sensor_id, str) or not sensor_id.strip():
        errors.append('"sensor_id" cannot be empty')

    if reading.get('city') not in ALLOWED_CITIES:
        errors.append(f'Invalid "city": {reading.get("city")!r}')

    road = reading.get('road')
    if not isinstance(road, str) or not road.strip():
        errors.append('"road" cannot be empty')

    speed_avg = reading.get('speed_avg')
    if (isinstance(speed_avg, bool) or not isinstance(speed_avg,
                                                      (int, float)) or
            not 0 <= speed_avg <= MAX_SPEED_AVG):
        errors.append(f'Invalid "speed_avg": {speed_avg!r}')

    vehicle_count = reading.get('vehicle_count')
    if (not isinstance(vehicle_count, int) or isinstance(vehicle_count, bool) or
            vehicle_count < MIN_VEHICLE_COUNT):
        errors.append(f'Invalid "vehicle_count": {vehicle_count!r}')

    if not is_valid_iso_datetime(reading.get('recorded_at')):
        errors.append(f'Invalid "recorded_at": {reading.get("recorded_at")!r}')

    return errors
