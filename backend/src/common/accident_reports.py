import datetime as dt

REQUIRED_COLUMNS = [
    'fecha',
    'hora',
    'ciudad',
    'via',
    'severidad',
    'vehiculos_involucrados',
    'nombre_persona_involucrada',
    'cedula_persona_involucrada',
]

ALLOWED_CITIES = {'Bogotá', 'Medellín', 'Cali', 'Barranquilla'}
ALLOWED_SEVERITIES = {'leve', 'moderado', 'grave', 'fatal'}
MAX_VEHICLES_INVOLVED = 20
MIN_INVOLVED_PERSON_ID_LENGTH = 6
MAX_INVOLVED_PERSON_ID_LENGTH = 10
MAX_ROWS = 300


class WorkbookValidationError(Exception):

    def __init__(self, errors):
        super().__init__('; '.join(errors))
        self.errors = errors


def validate_workbook(worksheet):
    header = _read_header(worksheet)
    data_rows = list(worksheet.iter_rows(min_row=2))
    if not data_rows:
        raise WorkbookValidationError(['File has no data rows'])
    if len(data_rows) > MAX_ROWS:
        raise WorkbookValidationError(
            [f'File has {len(data_rows)} rows, maximum is {MAX_ROWS}'])

    rows = []
    errors = []
    for row_number, row in enumerate(data_rows, start=2):
        try:
            rows.append(_parse_row(row, header, row_number))
        except WorkbookValidationError as error:
            errors.extend(error.errors)

    if errors:
        raise WorkbookValidationError(errors)
    return rows


def _read_header(worksheet):
    header_row = next(worksheet.iter_rows(min_row=1, max_row=1))
    header = {}
    for index, cell in enumerate(header_row):
        if cell.value is not None:
            header[str(cell.value).strip()] = index

    missing = [column for column in REQUIRED_COLUMNS if column not in header]
    if missing:
        raise WorkbookValidationError(
            [f'Missing required column(s): {", ".join(missing)}'])
    return header


def _parse_row(row, header, row_number):
    errors = []

    def cell(column):
        return row[header[column]].value

    occurred_date = _coerce_date(cell('fecha'))
    if occurred_date is None:
        errors.append(f'Row {row_number}: invalid "fecha"')

    occurred_time = _coerce_time(cell('hora'))
    if occurred_time is None:
        errors.append(f'Row {row_number}: invalid "hora"')

    city = cell('ciudad')
    city = city.strip() if isinstance(city, str) else city
    if city not in ALLOWED_CITIES:
        errors.append(f'Row {row_number}: invalid "ciudad": {city!r}')

    road = cell('via')
    road = road.strip() if isinstance(road, str) else None
    if not road:
        errors.append(f'Row {row_number}: "via" cannot be empty')

    severity = cell('severidad')
    severity = severity.strip().lower() if isinstance(severity,
                                                      str) else severity
    if severity not in ALLOWED_SEVERITIES:
        errors.append(f'Row {row_number}: invalid "severidad": {severity!r}')

    vehicles_involved = _coerce_int(cell('vehiculos_involucrados'))
    if (vehicles_involved is None or
            not 1 <= vehicles_involved <= MAX_VEHICLES_INVOLVED):
        errors.append('Row {}: invalid "vehiculos_involucrados": {!r}'.format(
            row_number, cell('vehiculos_involucrados')))

    involved_person_name = cell('nombre_persona_involucrada')
    involved_person_name = (involved_person_name.strip() if isinstance(
        involved_person_name, str) else None)
    if not involved_person_name:
        errors.append(
            f'Row {row_number}: "nombre_persona_involucrada" cannot be empty')

    involved_person_id = _coerce_involved_person_id(
        cell('cedula_persona_involucrada'))
    if involved_person_id is None:
        errors.append(
            'Row {}: invalid "cedula_persona_involucrada": {!r}'.format(
                row_number, cell('cedula_persona_involucrada')))

    if errors:
        raise WorkbookValidationError(errors)

    return {
        'occurred_at':
            dt.datetime.combine(occurred_date, occurred_time).isoformat(),
        'city':
            city,
        'road':
            road,
        'severity':
            severity,
        'vehicles_involved':
            vehicles_involved,
        'involved_person_name':
            involved_person_name,
        'involved_person_id':
            involved_person_id,
    }


def _coerce_date(value):
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        try:
            return dt.datetime.strptime(value.strip(), '%Y-%m-%d').date()
        except ValueError:
            return None
    return None


def _coerce_time(value):
    if isinstance(value, dt.datetime):
        return value.time()
    if isinstance(value, dt.time):
        return value
    if isinstance(value, str):
        try:
            return dt.datetime.strptime(value.strip(), '%H:%M').time()
        except ValueError:
            return None
    return None


def _coerce_int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _coerce_involved_person_id(value):
    as_int = _coerce_int(value)
    text = str(as_int) if as_int is not None else (
        value.strip() if isinstance(value, str) else None)
    if not text or not text.isdigit():
        return None
    if not MIN_INVOLVED_PERSON_ID_LENGTH <= len(
            text) <= MAX_INVOLVED_PERSON_ID_LENGTH:
        return None
    return text
