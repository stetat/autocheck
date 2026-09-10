import csv
import io
from collections.abc import Iterator

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401  -- registers tables on SQLModel.metadata

HEADERS = [
    "VIN", "Марка", "Модель", "ГодВыпуска", "Пробег", "Цена", "Цвет",
    "ТипКузова", "КПП", "ОбъемДвигателя", "Дефекты", "Салон", "Город",
    "ДатаВыгрузки",
]

# A clean baseline row; tests override only the fields they care about.
BASE_ROW = {
    "VIN": "XW8ZZZ61ZJG000001",
    "Марка": "Toyota",
    "Модель": "Camry",
    "ГодВыпуска": "2019",
    "Пробег": "120\xa0500",
    "Цена": "14 200 000",
    "Цвет": "Белый",
    "ТипКузова": "Седан",
    "КПП": "АКПП",
    "ОбъемДвигателя": "2,5",
    "Дефекты": "Скол на лобовом стекле; Царапина на заднем бампере",
    "Салон": "Астана Моторс",
    "Город": "Астана",
    "ДатаВыгрузки": "09.09.2026 06:00:00",
}


def make_feed(*rows: dict[str, str]) -> bytes:
    """Build a windows-1251, ';'-delimited 1C feed from partial row overrides."""
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=HEADERS, delimiter=";", lineterminator="\r\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({**BASE_ROW, **row})
    return buf.getvalue().encode("windows-1251")


@pytest.fixture
def session() -> Iterator[Session]:
    """A real SQLite database, in memory. No mocks: the upsert under test is a
    database behaviour, so mocking the database would test nothing."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    # Mirrors the production factory in app.db.get_session; without this the
    # tests would not reproduce commit-expiry behaviour.
    with Session(engine, expire_on_commit=False) as s:
        yield s
