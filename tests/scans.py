"""Load the register scans in docs/scans."""

import csv
from pathlib import Path

SCANS = Path(__file__).resolve().parent.parent / "docs" / "scans"

DISCHARGE_800W = "scan_20261110_1812_ontladen_800w_dispatch.csv"
CHARGE_3680W = "scan_20261110_1820_laden_3680w.csv"
CHARGE_500W = "scan_laden_500w.csv"


def load_scan(name: str) -> dict[int, int]:
    """Address -> raw register value."""
    with (SCANS / name).open() as fh:
        return {int(row["addr"], 16): int(row["raw"]) for row in csv.DictReader(fh)}
