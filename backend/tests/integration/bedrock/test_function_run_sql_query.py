from src.run_sql_query.handler import handler


def test_run_sql_query_valid_select_converts_dates_and_decimals():
    # ARRANGE / ACT
    response = handler(
        {
            'sql': "SELECT '2026-01-01'::date AS d, 1.5::numeric AS n"
        }, None)

    # ASSERT
    assert response['columns'] == ['d', 'n']
    assert response['rows'] == [['2026-01-01', 1.5]]


def test_run_sql_query_accepts_with_statements():
    # ARRANGE / ACT
    response = handler({
        'sql': 'WITH t AS (SELECT 1 AS x) SELECT * FROM t'
    }, None)

    # ASSERT
    assert response['columns'] == ['x']
    assert response['rows'] == [[1]]


def test_run_sql_query_requires_sql_parameter():
    # ARRANGE / ACT
    response = handler({}, None)

    # ASSERT
    assert response == {
        'error': 'Missing required "sql" parameter'
    }


def test_run_sql_query_rejects_non_select_statements():
    # ARRANGE / ACT
    response = handler({
        'sql': 'DELETE FROM cities'
    }, None)

    # ASSERT
    assert response == {
        'error': 'Only SELECT/WITH statements are allowed'
    }


def test_run_sql_query_appends_limit_when_missing():
    # ARRANGE / ACT
    response = handler({
        'sql': 'SELECT * FROM generate_series(1, 5) AS n'
    }, None)

    # ASSERT
    assert response['rows'] == [[1], [2], [3]]


def test_run_sql_query_caps_limit_above_max_rows():
    # ARRANGE / ACT
    response = handler(
        {
            'sql': 'SELECT * FROM generate_series(1, 10) AS n LIMIT 100'
        }, None)

    # ASSERT
    assert response['rows'] == [[1], [2], [3]]


def test_run_sql_query_keeps_limit_within_bounds():
    # ARRANGE / ACT
    response = handler(
        {
            'sql': 'SELECT * FROM generate_series(1, 10) AS n LIMIT 2'
        }, None)

    # ASSERT
    assert response['rows'] == [[1], [2]]


def test_run_sql_query_returns_error_and_recovers_after_invalid_sql():
    # ARRANGE / ACT
    failed_response = handler({
        'sql': 'SELECT * FROM not_a_real_table'
    }, None)
    recovered_response = handler({
        'sql': 'SELECT 1 AS n'
    }, None)

    # ASSERT
    assert failed_response['error'].startswith('Query failed:')
    assert recovered_response['rows'] == [[1]]
