"""Parser tests. No database involved -- the parser is pure by design, so these
run without any fixture beyond the raw bytes."""

from datetime import datetime

from app.parsers.csv_1c import parse_feed
from tests.conftest import make_feed


def test_parses_a_clean_row_into_a_record():
    result = parse_feed(make_feed({}))

    assert len(result.records) == 1
    assert result.errors == []
    rec = result.records[0]
    assert rec.vin == "XW8ZZZ61ZJG000001"
    assert rec.brand == "Toyota"
    assert rec.model == "Camry"
    assert rec.year == 2019


def test_strips_non_breaking_space_thousands_separator():
    result = parse_feed(make_feed({"Пробег": "120\xa0500", "Цена": "14 200 000"}))

    assert result.records[0].mileage_km == 120500
    assert result.records[0].price_kzt == 14_200_000


def test_reads_comma_as_decimal_separator():
    result = parse_feed(make_feed({"ОбъемДвигателя": "2,5"}))

    assert result.records[0].engine_volume_l == 2.5


def test_parses_russian_date_format():
    result = parse_feed(make_feed({"ДатаВыгрузки": "09.09.2026 06:00:00"}))

    assert result.records[0].exported_at == datetime(2026, 9, 9, 6, 0, 0)


def test_rejects_row_with_blank_vin():
    result = parse_feed(make_feed({"VIN": ""}))

    assert result.records == []
    assert len(result.errors) == 1
    assert "vin" in result.errors[0].reason.lower()


def test_rejects_vin_that_is_not_17_characters():
    result = parse_feed(make_feed({"VIN": "XW8ZZZ61ZJG"}))

    assert result.records == []
    assert len(result.errors) == 1


def test_rejects_non_numeric_mileage():
    result = parse_feed(make_feed({"Пробег": "н/д"}))

    assert result.records == []
    assert len(result.errors) == 1
    assert "Пробег" in result.errors[0].reason


def test_one_bad_row_does_not_discard_the_good_rows():
    """The whole point of collecting errors instead of raising: a single
    malformed line from a partner must not cost us the other 119."""
    feed = make_feed(
        {"VIN": "XW8ZZZ61ZJG000001"},
        {"VIN": ""},
        {"VIN": "XW8ZZZ61ZJG000003"},
    )

    result = parse_feed(feed)

    assert [r.vin for r in result.records] == ["XW8ZZZ61ZJG000001", "XW8ZZZ61ZJG000003"]
    assert len(result.errors) == 1


def test_error_reports_the_line_number_of_the_bad_row():
    feed = make_feed({}, {"VIN": ""})

    result = parse_feed(feed)

    # Line 1 is the header, line 2 the first data row, so the bad row is line 3.
    assert result.errors[0].line == 3


def test_optional_fields_may_be_empty():
    result = parse_feed(make_feed({"Дефекты": "", "Цвет": "", "Город": ""}))

    assert result.errors == []
    assert result.records[0].defects is None
    assert result.records[0].color is None
