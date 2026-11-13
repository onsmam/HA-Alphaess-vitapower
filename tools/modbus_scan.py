#!/usr/bin/env python3
"""
Modbus-scanner voor de AlphaESS VitaPower (of een ander Modbus-apparaat).

Leest alleen - er wordt nooit geschreven.

Installatie:
    pip install pymodbus

Gebruik:
    # 1. Scan van de standaardblokken, resultaat naar snapshot1.csv
    python3 modbus_scan.py --host 192.168.1.50 --out snapshot1.csv

    # 2. Verander iets (laat de batterij ontladen op 500 W), daarna:
    python3 modbus_scan.py --host 192.168.1.50 --out snapshot2.csv

    # 3. Vergelijk: welke registers zijn veranderd?
    python3 modbus_scan.py --diff snapshot1.csv snapshot2.csv

    # Eigen bereik scannen:
    python3 modbus_scan.py --host 192.168.1.50 --ranges 0x0100-0x0200,0x0800-0x0890

Let op: de VitaPower accepteert maar een TCP-verbinding tegelijk.
Stop eerst je Home Assistant Modbus-integratie.
"""

import argparse
import csv
import struct
import sys
import time

# SMILE-blokken uit de AlphaESS Household Modbus Register Parameter List:
# grid, PV-meter, batterij, omvormer, instellingen, dispatch, systemRun
DEFAULT_RANGES = ("0x0010-0x0042,0x0090-0x00B6,0x0100-0x0148,0x0400-0x0454,"
                  "0x0700-0x0760,0x0800-0x0890,0x08D0-0x08D5")


def parse_ranges(text):
    out = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        lo, _, hi = part.partition("-")
        lo = int(lo, 0)
        hi = int(hi, 0) if hi else lo
        out.append((lo, hi))
    return out


def connect(host, port):
    try:
        from pymodbus.client import ModbusTcpClient
    except ImportError:
        from pymodbus.client.sync import ModbusTcpClient  # pymodbus 2.x
    client = ModbusTcpClient(host, port=port, timeout=3)
    if not client.connect():
        sys.exit(f"Geen verbinding met {host}:{port}")
    return client


def read_block(client, func, addr, count, unit):
    """Leest een blok registers; geeft None terug bij een fout."""
    kwargs = {}
    # pymodbus 3.x gebruikt device_id/slave, 2.x gebruikt unit
    for key in ("device_id", "slave", "unit"):
        try:
            kwargs = {key: unit}
            fn = client.read_holding_registers if func == 3 else client.read_input_registers
            rr = fn(addr, count=count, **kwargs)
            break
        except TypeError:
            continue
        except Exception as exc:  # verbinding weg, timeout e.d.
            print(f"\n  fout bij 0x{addr:04X}: {exc}", file=sys.stderr)
            return None
    else:
        return None
    if rr is None or (hasattr(rr, "isError") and rr.isError()):
        return None
    return list(rr.registers)


def scan(client, ranges, func, unit, pace, block):
    values = {}
    for lo, hi in ranges:
        addr = lo
        while addr <= hi:
            count = min(block, hi - addr + 1)
            regs = read_block(client, func, addr, count, unit)
            if regs is None and count > 1:
                # blok mislukt: per register proberen om gaten te vinden
                for a in range(addr, addr + count):
                    one = read_block(client, func, a, 1, unit)
                    if one:
                        values[a] = one[0]
                    time.sleep(pace)
            elif regs:
                for i, v in enumerate(regs):
                    values[addr + i] = v
            addr += count
            time.sleep(pace)
            print(f"\r  gelezen tot 0x{addr:04X} ({len(values)} registers)", end="", file=sys.stderr)
    print("", file=sys.stderr)
    return values


def decode(values, addr):
    """Geeft mogelijke interpretaties van een register."""
    raw = values[addr]
    s16 = struct.unpack(">h", struct.pack(">H", raw))[0]
    row = {
        "addr": f"0x{addr:04X}",
        "raw": raw,
        "uint16": raw,
        "int16": s16,
        "x0.1": round(s16 * 0.1, 2),
        "min32000": raw - 32000,
        "ascii": "".join(
            chr(c) if 32 <= c < 127 else "." for c in (raw >> 8, raw & 0xFF)
        ),
    }
    nxt = values.get(addr + 1)
    if nxt is not None:
        u32 = (raw << 16) | nxt
        row["uint32_hi_lo"] = u32
        row["int32_hi_lo"] = struct.unpack(">i", struct.pack(">I", u32))[0]
        row["uint32_lo_hi"] = (nxt << 16) | raw
    return row


FIELDS = [
    "addr", "raw", "uint16", "int16", "x0.1", "min32000", "ascii",
    "uint32_hi_lo", "int32_hi_lo", "uint32_lo_hi",
]


def write_csv(values, path):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for addr in sorted(values):
            w.writerow(decode(values, addr))
    print(f"{len(values)} registers geschreven naar {path}")


def load_csv(path):
    with open(path) as fh:
        return {r["addr"]: r for r in csv.DictReader(fh)}


def diff(path_a, path_b):
    a, b = load_csv(path_a), load_csv(path_b)
    print(f"{'adres':8} {'voor':>10} {'na':>10} {'verschil':>10}  int16 voor/na")
    changed = 0
    for addr in sorted(set(a) & set(b)):
        va, vb = int(a[addr]["raw"]), int(b[addr]["raw"])
        if va != vb:
            changed += 1
            print(f"{addr:8} {va:10} {vb:10} {vb - va:10}  "
                  f"{a[addr]['int16']} / {b[addr]['int16']}")
    print(f"\n{changed} registers veranderd van {len(set(a) & set(b))} vergeleken")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--host")
    p.add_argument("--port", type=int, default=502)
    p.add_argument("--unit", type=int, default=85, help="slave-id (VitaPower: 85)")
    p.add_argument("--ranges", default=DEFAULT_RANGES)
    p.add_argument("--func", type=int, default=3, choices=(3, 4),
                   help="3 = holding registers, 4 = input registers")
    p.add_argument("--block", type=int, default=16, help="registers per leesopdracht")
    p.add_argument("--pace", type=float, default=0.05, help="pauze tussen opdrachten (s)")
    p.add_argument("--out", default="snapshot.csv")
    p.add_argument("--diff", nargs=2, metavar=("VOOR", "NA"))
    args = p.parse_args()

    if args.diff:
        diff(*args.diff)
        return
    if not args.host:
        p.error("--host is verplicht (of gebruik --diff)")

    client = connect(args.host, args.port)
    try:
        values = scan(client, parse_ranges(args.ranges), args.func,
                      args.unit, args.pace, args.block)
    finally:
        client.close()
    if not values:
        sys.exit("Niets gelezen. Controleer slave-id, functiecode en of er geen "
                 "andere TCP-verbinding openstaat.")
    write_csv(values, args.out)


if __name__ == "__main__":
    main()