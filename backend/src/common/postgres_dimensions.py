def get_city_id(connection, name):
    with connection.cursor() as cursor:
        cursor.execute('SELECT id FROM cities WHERE name = %s', (name, ))
        row = cursor.fetchone()
    if row is None:
        raise ValueError(f'Unknown city: {name!r}')
    return row[0]


def get_severity_id(connection, code):
    with connection.cursor() as cursor:
        cursor.execute('SELECT id FROM severities WHERE code = %s', (code, ))
        row = cursor.fetchone()
    if row is None:
        raise ValueError(f'Unknown severity: {code!r}')
    return row[0]


def upsert_road_id(connection, city_id, name):
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            INSERT INTO roads (city_id, name) VALUES (%s, %s)
            ON CONFLICT (city_id, name) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
            ''', (city_id, name))
        return cursor.fetchone()[0]


def upsert_sensor_id(connection, sensor_id):
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            INSERT INTO sensors (id) VALUES (%s)
            ON CONFLICT (id) DO NOTHING
            ''', (sensor_id, ))
    return sensor_id
