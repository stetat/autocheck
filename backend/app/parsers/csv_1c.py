"""Parser for 1C dealership export files.

Pure by design: bytes in, validated records out. It never touches the database,
which is what lets the parser tests run without any fixture and the upsert tests
run without any file.

Handles the quirks of a real 1C unload: windows-1251 encoding, ';' delimiter,
Cyrillic headers, non-breaking-space thousands separators, comma decimals and
DD.MM.YYYY dates. A malformed row is recorded as an error and skipped -- it never
aborts the run, because one bad line from a partner must not cost us the file.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime

from pydantic import BaseModel

# Source column -> internal field name.
COLUMNS = {
    "VIN": "vin",
    "Марка": "brand",
    "Модель": "model",
    "ГодВыпуска": "year",
    "Пробег": "mileage_km",
    "Цена": "price_kzt",
    "Цвет": "color",
    "ТипКузова": "body_type",
    "КПП": "transmission",
    "ОбъемДвигателя": "engine_volume_l",
    "Дефекты": "defects",
    "Салон": "dealer_name",
    "Город": "dealer_city",
    "ДатаВыгрузки": "exported_at",
}

REQUIRED_COLUMNS = {"VIN", "Марка", "Модель", "ГодВыпуска", "Пробег", "Цена", "Салон"}

DELIMITER = ";"
ENCODINGS = ("utf-8-sig", "windows-1251")
DATE_FORMATS = ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d")

# I, O and Q are absent from the VIN alphabet.
VIN_ALPHABET = set("ABCDEFGHJKLMNPRSTUVWXYZ0123456789")
VIN_LENGTH = 17

# Whitespace 1C uses inside numbers: plain, non-breaking, narrow non-breaking.
NUMERIC_NOISE = str.maketrans({" ": "", "\xa0": "", " ": "", "'": ""})


class VehicleRecord(BaseModel):
    """One validated vehicle from a feed. Mirrors app.models.Vehicle's data
    fields but carries no identity or persistence concerns."""

    vin: str
    brand: str
    model: str
    year: int
    mileage_km: int
    price_kzt: int
    color: str | None = None
    body_type: str | None = None
    transmission: str | None = None
    engine_volume_l: float | None = None
    defects: str | None = None
    dealer_name: str
    dealer_city: str | None = None
    exported_at: datetime | None = None


class RowError(BaseModel):
    """A rejected row.

    `code` and `params` are the machine-readable form, so the UI can render the
    reason in whichever language the reader has chosen. `reason` is the Russian
    rendering, kept for logs and for any consumer that just wants a string.
    """

    line: int
    vin: str | None = None
    code: str
    params: dict[str, str] = {}
    reason: str


class ParseResult(BaseModel):
    records: list[VehicleRecord] = []
    errors: list[RowError] = []


class RowRejected(Exception):
    """Raised per row and caught by the loop; never escapes parse_feed."""

    def __init__(self, code: str, **params: object) -> None:
        self.code = code
        self.params = {key: str(value) for key, value in params.items()}
        super().__init__(render_reason(code, self.params))


# Russian renderings of each rejection code. The Kazakh ones live in the
# frontend dictionary, keyed by the same codes.
REASON_TEMPLATES: dict[str, str] = {
    "vin_empty": "поле «VIN» пустое",
    "vin_length": "VIN должен быть 17 символов, получено {actual}: {value}",
    "vin_charset": "VIN содержит недопустимые символы: {value}",
    "field_empty": "обязательное поле «{field}» пустое",
    "field_not_number": "поле «{field}» не число: {value}",
    "year_out_of_range": "год выпуска вне допустимого диапазона: {year}",
    "file_empty": "файл пуст",
    "missing_columns": "в файле нет обязательных колонок: {columns}",
    "unhandled": "необработанная ошибка: {error}",
}


def render_reason(code: str, params: dict[str, str]) -> str:
    template = REASON_TEMPLATES.get(code)
    if template is None:
        return code
    try:
        return template.format(**params)
    except KeyError:
        return template


def row_error(line: int, vin: str | None, code: str, **params: object) -> RowError:
    rendered = {key: str(value) for key, value in params.items()}
    return RowError(
        line=line, vin=vin, code=code, params=rendered, reason=render_reason(code, rendered)
    )


def decode(data: bytes) -> str:
    """Decode a feed, tolerating either UTF-8 or windows-1251.

    UTF-8 is tried first precisely because it fails loudly on cp1251 Cyrillic,
    whereas cp1251 is single-byte and would silently mangle UTF-8 into mojibake.
    """
    for encoding in ENCODINGS:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("windows-1251", errors="replace")


def clean(value: str | None) -> str | None:
    """Trim a cell; treat blank and common 1C null markers as absent."""
    if value is None:
        return None
    text = value.strip()
    if text == "" or text.lower() in {"н/д", "не указан", "не указано", "-", "—"}:
        return None
    return text


def required_text(row: dict[str, str], column: str) -> str:
    value = clean(row.get(column))
    if value is None:
        raise RowRejected("field_empty", field=column)
    return value


def parse_int(row: dict[str, str], column: str) -> int:
    raw = clean(row.get(column))
    if raw is None:
        raise RowRejected("field_empty", field=column)
    cleaned = raw.translate(NUMERIC_NOISE)
    # A comma decimal on an integer column ("120 500,00") is still an integer.
    cleaned = cleaned.split(",")[0].split(".")[0]
    if not cleaned.lstrip("-").isdigit():
        raise RowRejected("field_not_number", field=column, value=repr(raw))
    return int(cleaned)


def parse_optional_float(row: dict[str, str], column: str) -> float | None:
    raw = clean(row.get(column))
    if raw is None:
        return None
    try:
        return float(raw.translate(NUMERIC_NOISE).replace(",", "."))
    except ValueError:
        return None


def parse_optional_datetime(row: dict[str, str], column: str) -> datetime | None:
    raw = clean(row.get(column))
    if raw is None:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def parse_vin(row: dict[str, str]) -> str:
    raw = clean(row.get("VIN"))
    if raw is None:
        raise RowRejected("vin_empty")
    vin = raw.upper()
    if len(vin) != VIN_LENGTH:
        raise RowRejected("vin_length", expected=VIN_LENGTH, actual=len(vin), value=repr(vin))
    if not set(vin) <= VIN_ALPHABET:
        raise RowRejected("vin_charset", value=repr(vin))
    return vin


def parse_year(row: dict[str, str]) -> int:
    year = parse_int(row, "ГодВыпуска")
    current = datetime.now().year
    if not 1900 <= year <= current + 1:
        raise RowRejected("year_out_of_range", year=year)
    return year


def build_record(row: dict[str, str]) -> VehicleRecord:
    return VehicleRecord(
        vin=parse_vin(row),
        brand=required_text(row, "Марка"),
        model=required_text(row, "Модель"),
        year=parse_year(row),
        mileage_km=parse_int(row, "Пробег"),
        price_kzt=parse_int(row, "Цена"),
        color=clean(row.get("Цвет")),
        body_type=clean(row.get("ТипКузова")),
        transmission=clean(row.get("КПП")),
        engine_volume_l=parse_optional_float(row, "ОбъемДвигателя"),
        defects=clean(row.get("Дефекты")),
        dealer_name=required_text(row, "Салон"),
        dealer_city=clean(row.get("Город")),
        exported_at=parse_optional_datetime(row, "ДатаВыгрузки"),
    )


def parse_feed(data: bytes) -> ParseResult:
    """Parse a 1C export. Never raises for row-level problems."""
    reader = csv.DictReader(io.StringIO(decode(data), newline=""), delimiter=DELIMITER)

    if reader.fieldnames is None:
        return ParseResult(errors=[row_error(0, None, "file_empty")])

    present = {(name or "").strip().lstrip("﻿") for name in reader.fieldnames}
    missing = REQUIRED_COLUMNS - present
    if missing:
        return ParseResult(
            errors=[row_error(1, None, "missing_columns", columns=", ".join(sorted(missing)))]
        )

    result = ParseResult()
    for offset, row in enumerate(reader):
        line = offset + 2  # line 1 is the header
        try:
            result.records.append(build_record(row))
        except RowRejected as exc:
            result.errors.append(row_error(line, clean(row.get("VIN")), exc.code, **exc.params))
        except Exception as exc:  # a row must never take down the file
            result.errors.append(row_error(line, clean(row.get("VIN")), "unhandled", error=exc))

    return result
