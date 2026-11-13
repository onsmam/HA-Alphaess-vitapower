#!/usr/bin/env python3
"""Replace the serial number in a modbus_scan.py CSV before sharing it.

The serial sits at 0x0706-0x070D and 0x0743-0x074A (15 ASCII characters).
Only the rows that hold (part of) the serial are rewritten, with
modbus_scan.decode(); every other row stays exactly as scanned.

    python3 tools/redact_scan.py scan.csv [--serial ALG0REDACTED001]
"""

import argparse
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from modbus_scan import FIELDS, decode

SERIAL_STARTS = (0x0706, 0x0743)
SERIAL_REGISTERS = 8


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv", nargs="+")
    p.add_argument("--serial", default="ALG0REDACTED001")
    args = p.parse_args()
    data = args.serial.encode("ascii").ljust(SERIAL_REGISTERS * 2, b"\x00")
    words = [int.from_bytes(data[i : i + 2], "big") for i in range(0, len(data), 2)]

    for path in args.csv:
        with open(path) as fh:
            rows = list(csv.DictReader(fh))
        # Only registers that actually followed each other in the scan get the
        # 32-bit columns, as in modbus_scan.write_csv().
        values = {int(r["addr"], 16): int(r["raw"]) for r in rows}
        has_pair = {int(r["addr"], 16) for r in rows if r["uint32_hi_lo"] != ""}
        for start in SERIAL_STARTS:
            if start in values:
                for i, word in enumerate(words):
                    values[start + i] = word
        touched = {
            a
            for start in SERIAL_STARTS
            if start in values
            for a in range(start - 1, start + SERIAL_REGISTERS)
        }
        with open(path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
            w.writeheader()
            for original in rows:
                addr = int(original["addr"], 16)
                if addr not in touched:
                    w.writerow(original)
                    continue
                row = decode(values, addr)
                if addr not in has_pair:
                    for key in ("uint32_hi_lo", "int32_hi_lo", "uint32_lo_hi"):
                        row.pop(key, None)
                w.writerow(row)
        print(f"redacted {path}")


if __name__ == "__main__":
    main()
