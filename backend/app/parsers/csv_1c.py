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
    line: int
    vin: str | None = None
    reason: str


class ParseResult(BaseModel):
    records: list[VehicleRecord] = []
    errors: list[RowError] = []


class RowRejected(Exception):
    """Raised per row and caught by the loop; never escapes parse_feed."""


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
        raise RowRejected(f"обязательное поле «{column}» пустое")
    return value


def parse_int(row: dict[str, str], column: str) -> int:
    raw = clean(row.get(column))
    if raw is None:
        raise RowRejected(f"обязательное поле «{column}» пустое")
    cleaned = raw.translate(NUMERIC_NOISE)
    # A comma decimal on an integer column ("120 500,00") is still an integer.
    cleaned = cleaned.split(",")[0].split(".")[0]
    if not cleaned.lstrip("-").isdigit():
        raise RowRejected(f"поле «{column}» не число: {raw!r}")
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
        raise RowRejected("поле «VIN» пустое")
    vin = raw.upper()
    if len(vin) != VIN_LENGTH:
        raise RowRejected(f"VIN должен быть {VIN_LENGTH} символов, получено {len(vin)}: {vin!r}")
    if not set(vin) <= VIN_ALPHABET:
        raise RowRejected(f"VIN содержит недопустимые символы: {vin!r}")
    return vin


def parse_year(row: dict[str, str]) -> int:
    year = parse_int(row, "ГодВыпуска")
    current = datetime.now().year
    if not 1900 <= year <= current + 1:
        raise RowRejected(f"год выпуска вне допустимого диапазона: {year}")
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
        return ParseResult(errors=[RowError(line=0, reason="файл пуст")])

    present = {(name or "").strip().lstrip("﻿") for name in reader.fieldnames}
    missing = REQUIRED_COLUMNS - present
    if missing:
        return ParseResult(
            errors=[RowError(line=1, reason=f"в файле нет обязательных колонок: {', '.join(sorted(missing))}")]
        )

    result = ParseResult()
    for offset, row in enumerate(reader):
        line = offset + 2  # line 1 is the header
        try:
            result.records.append(build_record(row))
        except RowRejected as exc:
            result.errors.append(RowError(line=line, vin=clean(row.get("VIN")), reason=str(exc)))
        except Exception as exc:  # a row must never take down the file
            result.errors.append(RowError(line=line, vin=clean(row.get("VIN")), reason=f"необработанная ошибка: {exc}"))

    return result
