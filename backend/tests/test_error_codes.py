"""Rejection codes are a contract, not an implementation detail.

The UI renders each rejection in the reader's language by looking the code up
in its own dictionary. Renaming a code silently degrades the Kazakh UI to an
untranslated string, so the set is pinned here.
"""

import pytest

from app.parsers.csv_1c import REASON_TEMPLATES, parse_feed
from tests.conftest import make_feed

# Every code the frontend dictionary must cover.
EXPECTED_CODES = {
    "vin_empty",
    "vin_length",
    "vin_charset",
    "field_empty",
    "field_not_number",
    "year_out_of_range",
    "file_empty",
    "missing_columns",
    "unhandled",
}


def test_the_set_of_rejection_codes_is_stable():
    assert set(REASON_TEMPLATES) == EXPECTED_CODES


@pytest.mark.parametrize(
    "overrides,expected_code",
    [
        ({"VIN": ""}, "vin_empty"),
        ({"VIN": "XW8ZZZ61ZJG"}, "vin_length"),
        ({"VIN": "XW8ZZZ61ZJG00000I"}, "vin_charset"),
        ({"Цена": ""}, "field_empty"),
        ({"Пробег": "abc"}, "field_not_number"),
        ({"ГодВыпуска": "19999"}, "year_out_of_range"),
    ],
)
def test_each_rejection_carries_its_code(overrides: dict[str, str], expected_code: str):
    result = parse_feed(make_feed(overrides))

    assert [e.code for e in result.errors] == [expected_code]


def test_file_level_rejections_carry_codes():
    assert parse_feed(b"").errors[0].code == "file_empty"

    no_vin_column = "Марка;Модель\r\nToyota;Camry\r\n".encode("windows-1251")
    assert parse_feed(no_vin_column).errors[0].code == "missing_columns"


def test_params_carry_the_values_the_message_needs():
    result = parse_feed(make_feed({"VIN": "XW8ZZZ61ZJG"}))

    error = result.errors[0]
    assert error.params["actual"] == "11"
    assert error.params["expected"] == "17"


def test_field_rejections_name_the_offending_column():
    result = parse_feed(make_feed({"Цена": ""}))

    assert result.errors[0].params["field"] == "Цена"


def test_reason_still_renders_russian_for_logs():
    result = parse_feed(make_feed({"VIN": ""}))

    assert result.errors[0].reason == "поле «VIN» пустое"


def test_every_template_renders_without_a_missing_placeholder():
    """A template referencing a param no raise site supplies would render as a
    bare template string in the logs."""
    from app.parsers.csv_1c import render_reason

    for code, template in REASON_TEMPLATES.items():
        rendered = render_reason(code, {"actual": "1", "value": "x", "field": "f",
                                        "year": "0", "columns": "c", "error": "e",
                                        "expected": "17"})
        assert "{" not in rendered, f"{code} left an unfilled placeholder"
