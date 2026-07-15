import argparse
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


COLUMNS = ["Date", "Item", "Grams", "Total_Paid_AUD", "Source", "Notes"]


def clean_text(value: str, fallback: str = "") -> str:
    cleaned = " ".join(value.replace("\r", " ").replace("\n", " ").split())
    return cleaned or fallback


def positive_decimal(value: str, label: str) -> Decimal:
    try:
        number = Decimal(value.replace(",", "").strip())
    except (InvalidOperation, AttributeError):
        raise ValueError(f"{label} must be a number") from None
    if not number.is_finite() or number <= 0:
        raise ValueError(f"{label} must be greater than zero")
    return number


def read_existing(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    if set(COLUMNS).issubset(fieldnames):
        return [{column: row.get(column, "") for column in COLUMNS} for row in rows]

    if {"Date", "Grams", "Price_Paid_AUD"}.issubset(fieldnames):
        migrated = []
        for row in rows:
            grams = positive_decimal(row["Grams"], "Grams")
            unit_price = positive_decimal(row["Price_Paid_AUD"], "Price_Paid_AUD")
            migrated.append({
                "Date": row["Date"],
                "Item": "Gold purchase",
                "Grams": format(grams.normalize(), "f"),
                "Total_Paid_AUD": f"{grams * unit_price:.2f}",
                "Source": "",
                "Notes": "Migrated from legacy per-gram record",
            })
        return migrated

    raise ValueError(f"{path} has an unsupported holdings format")


def append_purchase(
    path: Path,
    purchase_date: str,
    item: str,
    grams: str,
    total_paid_aud: str,
    source: str,
    notes: str = "",
) -> bool:
    try:
        parsed_date = date.fromisoformat(purchase_date.strip())
    except ValueError:
        raise ValueError("Purchase date must use YYYY-MM-DD") from None

    grams_value = positive_decimal(grams, "Grams")
    total_value = positive_decimal(total_paid_aud, "Total paid (AUD)")
    row = {
        "Date": parsed_date.isoformat(),
        "Item": clean_text(item, "Gold purchase"),
        "Grams": format(grams_value.normalize(), "f"),
        "Total_Paid_AUD": f"{total_value:.2f}",
        "Source": clean_text(source, "Other"),
        "Notes": clean_text(notes),
    }
    rows = read_existing(path)
    if row in rows:
        print("This purchase is already recorded; no duplicate was added.")
        return False

    rows.append(row)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Recorded {row['Grams']}g for A${row['Total_Paid_AUD']} on {row['Date']}.")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Record a gold purchase in the holdings ledger.")
    parser.add_argument("--date", required=True)
    parser.add_argument("--item", required=True)
    parser.add_argument("--grams", required=True)
    parser.add_argument("--total-paid-aud", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--notes", default="")
    args = parser.parse_args()
    append_purchase(
        Path("my_holdings.csv"), args.date, args.item, args.grams,
        args.total_paid_aud, args.source, args.notes,
    )


if __name__ == "__main__":
    main()
