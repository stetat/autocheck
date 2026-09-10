"""Generate a realistic 1C dealership export.

Mimics the quirks of a real Russian-locale 1C CSV unload:
  * windows-1251 encoding
  * ';' delimiter
  * Cyrillic column headers
  * comma as the decimal separator
  * DD.MM.YYYY dates
  * thousands separated by non-breaking spaces in numeric columns
  * free-text defect descriptions
  * a small share of dirty rows (blank VIN, bad checksum, junk mileage)

Usage:
    python scripts/generate_feed.py --rows 120 --out data/feeds/feed_day1.csv
    python scripts/generate_feed.py --rows 120 --out data/feeds/feed_day2.csv \
        --base data/feeds/feed_day1.csv --carry-over 0.7
"""

from __future__ import annotations

import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

ENCODING = "windows-1251"
DELIMITER = ";"

HEADERS = [
    "VIN",
    "Марка",
    "Модель",
    "ГодВыпуска",
    "Пробег",
    "Цена",
    "Цвет",
    "ТипКузова",
    "КПП",
    "ОбъемДвигателя",
    "Дефекты",
    "Салон",
    "Город",
    "ДатаВыгрузки",
]

# model -> (body type, plausible engine volumes). Keeping these together stops the
# generator from emitting nonsense like a "Niva Travel" saloon with a CVT.
MODELS: dict[str, list[tuple[str, str, list[float]]]] = {
    "Toyota": [
        ("Camry", "Седан", [2.0, 2.5, 3.5]),
        ("Corolla", "Седан", [1.6, 1.8]),
        ("RAV4", "Кроссовер", [2.0, 2.5]),
        ("Land Cruiser 200", "Внедорожник", [4.6, 4.5]),
        ("Highlander", "Кроссовер", [2.5, 3.5]),
    ],
    "Hyundai": [
        ("Elantra", "Седан", [1.6, 2.0]),
        ("Tucson", "Кроссовер", [1.6, 2.0, 2.5]),
        ("Sonata", "Седан", [2.0, 2.5]),
        ("Accent", "Седан", [1.4, 1.6]),
        ("Santa Fe", "Кроссовер", [2.2, 2.5]),
    ],
    "Kia": [
        ("Rio", "Седан", [1.4, 1.6]),
        ("Sportage", "Кроссовер", [1.6, 2.0]),
        ("K5", "Седан", [2.0, 2.5]),
        ("Seltos", "Кроссовер", [1.6, 2.0]),
        ("Sorento", "Кроссовер", [2.2, 3.5]),
    ],
    "Lada": [
        ("Vesta", "Седан", [1.6, 1.8]),
        ("Granta", "Седан", [1.6]),
        ("Largus", "Универсал", [1.6]),
        ("Niva Travel", "Внедорожник", [1.7]),
    ],
    "Volkswagen": [
        ("Polo", "Седан", [1.4, 1.6]),
        ("Tiguan", "Кроссовер", [1.4, 2.0]),
        ("Passat", "Седан", [1.8, 2.0]),
        ("Touareg", "Внедорожник", [3.0, 3.6]),
    ],
    "Nissan": [
        ("Qashqai", "Кроссовер", [1.6, 2.0]),
        ("X-Trail", "Кроссовер", [2.0, 2.5]),
        ("Almera", "Седан", [1.6]),
        ("Patrol", "Внедорожник", [4.0, 5.6]),
    ],
    "Chevrolet": [
        ("Cobalt", "Седан", [1.5]),
        ("Nexia", "Седан", [1.5]),
        ("Onix", "Седан", [1.2, 1.5]),
        ("Tracker", "Кроссовер", [1.0, 1.2]),
    ],
    "Mercedes-Benz": [
        ("E 200", "Седан", [2.0]),
        ("GLE 350", "Кроссовер", [3.0]),
        ("S 500", "Седан", [4.7]),
        ("C 180", "Седан", [1.6, 2.0]),
    ],
    "BMW": [
        ("X5", "Кроссовер", [3.0, 4.4]),
        ("320i", "Седан", [2.0]),
        ("530i", "Седан", [2.0, 3.0]),
        ("X3", "Кроссовер", [2.0, 3.0]),
    ],
    "Renault": [
        ("Duster", "Кроссовер", [1.6, 2.0]),
        ("Logan", "Седан", [1.4, 1.6]),
        ("Arkana", "Кроссовер", [1.3, 1.6]),
    ],
}

COLORS = ["Белый", "Чёрный", "Серебристый", "Серый", "Синий", "Красный", "Коричневый", "Зелёный"]

# Budget brands here are overwhelmingly manual/auto; CVTs and DCTs belong elsewhere.
TRANSMISSIONS_BY_BRAND: dict[str, list[str]] = {
    "Lada": ["МКПП", "МКПП", "АКПП"],
    "Chevrolet": ["МКПП", "АКПП"],
    "Renault": ["МКПП", "АКПП", "Вариатор"],
    "Nissan": ["Вариатор", "АКПП", "МКПП"],
    "Volkswagen": ["Робот", "АКПП", "МКПП"],
    "Mercedes-Benz": ["АКПП"],
    "BMW": ["АКПП"],
}
DEFAULT_TRANSMISSIONS = ["АКПП", "МКПП", "Вариатор"]

# Approximate price of a NEW car of each brand, in tenge. Prices are derived by
# depreciating this, so a fresh X5 and a fresh Granta cannot end up equal.
BRAND_BASE_PRICE_KZT: dict[str, int] = {
    "Lada": 7_500_000,
    "Chevrolet": 9_000_000,
    "Renault": 11_000_000,
    "Kia": 13_000_000,
    "Hyundai": 13_500_000,
    "Nissan": 15_000_000,
    "Volkswagen": 17_000_000,
    "Toyota": 19_000_000,
    "BMW": 34_000_000,
    "Mercedes-Benz": 38_000_000,
}

# Yearly value retained. Cars lose most value early, then flatten out.
ANNUAL_RETENTION = 0.87
RESIDUAL_FLOOR = 0.10  # even a very old car keeps roughly this share of value

DEALERS = [
    ("Автосалон Астана Моторс", "Астана"),
    ("Allur Auto", "Алматы"),
    ("Мега Авто", "Шымкент"),
    ("Kolesa Trade", "Алматы"),
    ("Караван Авто", "Караганда"),
    ("Актобе Моторс", "Актобе"),
]

DEFECTS = [
    "Скол на лобовом стекле",
    "Царапина на заднем бампере",
    "Требуется замена тормозных колодок",
    "Вмятина на левой передней двери",
    "Потёртость водительского сиденья",
    "Коррозия на пороге",
    "Не работает стеклоподъёмник задней двери",
    "Замена ремня ГРМ по регламенту",
    "Помутнение фары",
    "Люфт рулевой рейки",
    "Окрашено переднее крыло",
    "Требуется регулировка развал-схождения",
]

# Standard VIN alphabet: I, O and Q are excluded to avoid confusion with 1/0.
VIN_ALPHABET = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"
VIN_TRANSLIT = {
    **{str(d): d for d in range(10)},
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8,
    "J": 1, "K": 2, "L": 3, "M": 4, "N": 5, "P": 7, "R": 9,
    "S": 2, "T": 3, "U": 4, "V": 5, "W": 6, "X": 7, "Y": 8, "Z": 9,
}
VIN_WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]


def vin_check_digit(vin: str) -> str:
    """Compute the ISO 3779 check digit (position 9)."""
    total = sum(VIN_TRANSLIT[ch] * w for ch, w in zip(vin, VIN_WEIGHTS))
    rem = total % 11
    return "X" if rem == 10 else str(rem)


def make_vin(rng: random.Random) -> str:
    """Build a syntactically valid VIN with a correct check digit."""
    chars = [rng.choice(VIN_ALPHABET) for _ in range(17)]
    chars[8] = "0"
    vin = "".join(chars)
    return vin[:8] + vin_check_digit(vin) + vin[9:]


def fmt_int(value: int, rng: random.Random) -> str:
    """1C often writes thousands separated by a non-breaking space."""
    if rng.random() < 0.5:
        return f"{value:,}".replace(",", "\xa0")
    return str(value)


def fmt_decimal(value: float) -> str:
    """Russian locale uses a comma for the decimal separator."""
    return f"{value:.1f}".replace(".", ",")


def price_for(brand: str, age: int, mileage: int, rng: random.Random) -> int:
    """Depreciate a brand's new price by age, mileage and a little noise.

    Multiplicative rather than additive: an earlier version sampled a Gaussian
    whose fixed 4M spread swamped the age-shrunken mean, so 38% of the fleet
    landed on the clamp floor at exactly 1 800 000 and a 2005 Polo could outprice
    a 2017 X5.
    """
    base = BRAND_BASE_PRICE_KZT.get(brand, 12_000_000)

    retention = max(RESIDUAL_FLOOR, ANNUAL_RETENTION ** age)

    # Mileage beyond the ~18k/year norm costs extra value, capped at -25%.
    expected_km = max(1, age * 18_000)
    excess = max(0.0, (mileage - expected_km) / expected_km)
    mileage_penalty = max(0.75, 1.0 - 0.25 * min(1.0, excess))

    noise = rng.lognormvariate(0.0, 0.11)

    price = base * retention * mileage_penalty * noise

    # Jittered floor: cheap old cars really do bunch near the bottom of the
    # market, but a single constant floor shows up as one repeated price.
    floor = 1_000_000 + rng.randrange(0, 9) * 50_000

    # Dealers advertise round numbers.
    return max(floor, int(round(price / 50_000) * 50_000))


def build_row(rng: random.Random, exported_at: datetime, vin: str | None = None) -> dict[str, str]:
    brand = rng.choice(list(MODELS))
    model, body_type, engine_volumes = rng.choice(MODELS[brand])
    year = rng.randint(2005, 2024)
    age = max(1, exported_at.year - year)

    # Mileage correlates with age (~18k km/year) plus noise.
    mileage = max(0, int(rng.gauss(age * 18_000, age * 4_000)))
    price = price_for(brand, age, mileage, rng)

    # Older cars accumulate more defects.
    n_defects = min(len(DEFECTS), max(0, int(rng.gauss(age / 4, 1))))
    defects = "; ".join(rng.sample(DEFECTS, n_defects)) if n_defects else ""

    dealer, city = rng.choice(DEALERS)

    return {
        "VIN": vin or make_vin(rng),
        "Марка": brand,
        "Модель": model,
        "ГодВыпуска": str(year),
        "Пробег": fmt_int(mileage, rng),
        "Цена": fmt_int(price, rng),
        "Цвет": rng.choice(COLORS),
        "ТипКузова": body_type,
        "КПП": rng.choice(TRANSMISSIONS_BY_BRAND.get(brand, DEFAULT_TRANSMISSIONS)),
        "ОбъемДвигателя": fmt_decimal(rng.choice(engine_volumes)),
        "Дефекты": defects,
        "Салон": dealer,
        "Город": city,
        "ДатаВыгрузки": exported_at.strftime("%d.%m.%Y %H:%M:%S"),
    }


def corrupt(row: dict[str, str], rng: random.Random) -> dict[str, str]:
    """Introduce one realistic data-quality problem. The parser must survive these."""
    kind = rng.choice(["blank_vin", "short_vin", "junk_mileage", "bad_year", "empty_price"])
    row = dict(row)
    if kind == "blank_vin":
        row["VIN"] = ""
    elif kind == "short_vin":
        row["VIN"] = row["VIN"][:11]
    elif kind == "junk_mileage":
        row["Пробег"] = rng.choice(["н/д", "не указан", "-"])
    elif kind == "bad_year":
        row["ГодВыпуска"] = rng.choice(["0", "19999", ""])
    elif kind == "empty_price":
        row["Цена"] = ""
    return row


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding=ENCODING, newline="") as fh:
        return [
            r
            for r in csv.DictReader(fh, delimiter=DELIMITER)
            if len(r.get("VIN", "")) == 17
        ]


def parse_int(raw: str) -> int | None:
    cleaned = raw.replace("\xa0", "").replace(" ", "")
    return int(cleaned) if cleaned.isdigit() else None


def age_row(prev: dict[str, str], rng: random.Random, exported_at: datetime) -> dict[str, str]:
    """Produce the next day's version of a car already seen in an earlier feed.

    A real dealership re-exports the same vehicle with mileage that has only gone
    up and a price that has usually drifted down. Generating these fields freshly
    would produce cars that un-drive themselves, which makes the upsert demo
    nonsense.
    """
    row = dict(prev)
    row["ДатаВыгрузки"] = exported_at.strftime("%d.%m.%Y %H:%M:%S")

    prev_mileage = parse_int(prev["Пробег"])
    if prev_mileage is not None:
        row["Пробег"] = fmt_int(prev_mileage + rng.randint(150, 2_500), rng)

    prev_price = parse_int(prev["Цена"])
    if prev_price is not None:
        # Usually a markdown, occasionally a small correction upward.
        factor = rng.uniform(0.94, 0.995) if rng.random() < 0.8 else rng.uniform(1.0, 1.03)
        row["Цена"] = fmt_int(
            max(1_200_000, int(round(prev_price * factor / 50_000) * 50_000)), rng
        )

    # A fresh inspection sometimes finds one more defect.
    if rng.random() < 0.25:
        existing = [d for d in prev["Дефекты"].split("; ") if d]
        candidates = [d for d in DEFECTS if d not in existing]
        if candidates:
            row["Дефекты"] = "; ".join(existing + [rng.choice(candidates)])

    return row


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rows", type=int, default=120)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dirty-ratio", type=float, default=0.06)
    ap.add_argument("--days-ago", type=int, default=0)
    ap.add_argument("--base", type=Path, help="Reuse VINs from this feed (simulates the next day's export)")
    ap.add_argument("--carry-over", type=float, default=0.7, help="Share of --base VINs to repeat")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    exported_at = datetime(2026, 9, 10, 6, 0, 0) - timedelta(days=args.days_ago)

    # Carried-over VINs are what exercise the upsert: same car, new mileage/price.
    carried: list[dict[str, str]] = []
    if args.base and args.base.exists():
        base_rows = read_rows(args.base)
        carried = rng.sample(base_rows, min(len(base_rows), int(len(base_rows) * args.carry_over)))

    rows: list[dict[str, str]] = []
    for i in range(args.rows):
        if i < len(carried):
            # Carried-over rows are aged, never corrupted: they must land as clean updates.
            rows.append(age_row(carried[i], rng, exported_at))
            continue
        row = build_row(rng, exported_at)
        if rng.random() < args.dirty_ratio:
            row = corrupt(row, rng)
        rows.append(row)

    rng.shuffle(rows)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding=ENCODING, newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=HEADERS, delimiter=DELIMITER)
        writer.writeheader()
        writer.writerows(rows)

    print(f"{args.out}: {len(rows)} rows, {len(carried)} carried over from base")


if __name__ == "__main__":
    main()
