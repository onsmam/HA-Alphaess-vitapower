#!/usr/bin/env python3
"""Eenmalige dispatch-test op een AlphaESS VitaPower.

Dit script SCHRIJFT naar de batterij: het laat de batterij kort laden of
ontladen via het dispatch-blok (0x0880) en zet daarna de dispatch weer stop.
Het schrijft alleen 0x0880-0x0889, en alleen na bevestiging.

Wat het controleert:
  - werkt schrijven met FC16 (meerdere registers)?
  - klopt het teken (onder 32000 = laden, boven = ontladen)?
  - leest de batterij de waarden terug zoals geschreven (SOC-schaal 0,4 %)?
  - overschrijft de AlphaESS-cloud de dispatch tijdens de test?
  - zet stoppen de batterij terug?

Werkwijze (standaard): het commando wordt een keer geschreven met de gekozen
duur; het script stuurt GEEN stop, maar kijkt of de batterij na die duur zelf
terugvalt. Doet ze dat na nog 90 s niet, dan schrijft het script alsnog stop.

Veiligheid:
  - vermogen max 3680 W (het maximum van de VitaPower), duur max 300 s;
  - de BMS bewaakt zelf stroom, spanning en celgrenzen;
  - Ctrl+C of een fout stuurt altijd het stop-commando.

Gebruik (HA-integratie / YAML modbus-hub eerst uitzetten):
    python3 vitapower_dispatch_test.py --host 192.168.1.151
    python3 vitapower_dispatch_test.py --host 192.168.1.151 --power 300 --seconds 60
    python3 vitapower_dispatch_test.py --host 192.168.1.151 --discharge   # ontladen
    python3 vitapower_dispatch_test.py --power 3680 --seconds 300
        # 5 minuten laden met 3680 W; valt de batterij daarna zelf terug?
    python3 vitapower_dispatch_test.py --power 3680 --seconds 300 --auto-target
        # doel net onder wat haalbaar is: stopt de batterij zelf op het doel?
"""

import argparse
import csv
import datetime as dt
import sys
import time

DISPATCH = 0x0880
OFFSET = 32000
SOC_STEP = 0.4  # % per eenheid in 0x0886
MAX_POWER = 3680  # het maximum van de VitaPower 3600 AC
MAX_SECONDS = 300
# Hoe lang het script na de duur nog wacht tot de batterij zelf terugvalt.
FALLBACK_GRACE = 90
# Gemeten rendement AC <-> batterij bij hoog vermogen.
EFFICIENCY = 0.925
# Deel van de haalbare SOC-verandering dat --auto-target als doel neemt.
AUTO_TARGET_SHARE = 0.85
# Wat de batterij zelf na een gestopte dispatch laat staan.
STOP_BLOCK = [0, 0, OFFSET, 0, OFFSET, 0, 0, 0, 90, 255]


def connect(host, port):
    try:
        from pymodbus.client import ModbusTcpClient
    except ImportError:
        from pymodbus.client.sync import ModbusTcpClient  # pymodbus 2.x
    client = ModbusTcpClient(host, port=port, timeout=3)
    if not client.connect():
        sys.exit(
            f"Geen verbinding met {host}:{port}. Staat Home Assistant nog verbonden? "
            "De VitaPower staat maar een client toe."
        )
    return client


def _call(fn, *args, unit):
    for key in ("device_id", "slave", "unit"):  # pymodbus 3.x / 2.x
        try:
            return fn(*args, **{key: unit})
        except TypeError:
            continue
    raise RuntimeError("pymodbus-versie niet herkend")


def read(client, address, count, unit):
    rr = None
    for key in ("device_id", "slave", "unit"):
        try:
            rr = client.read_holding_registers(address, count=count, **{key: unit})
            break
        except TypeError:
            continue
    if rr is None or (hasattr(rr, "isError") and rr.isError()):
        raise RuntimeError(f"lezen 0x{address:04X} mislukt: {rr}")
    return list(rr.registers)


def write_block(client, values, unit):
    """FC16: alle registers vanaf 0x0880 in een keer."""
    rr = _call(client.write_registers, DISPATCH, values, unit=unit)
    if rr is None or (hasattr(rr, "isError") and rr.isError()):
        raise RuntimeError(f"schrijven 0x{DISPATCH:04X} mislukt: {rr}")


def signed(value, bits):
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def snapshot(client, unit):
    battery = read(client, 0x0100, 0x0127 - 0x0100, unit)
    inverter = read(client, 0x040C, 2, unit)
    dispatch = read(client, DISPATCH, 10, unit)
    settings = read(client, 0x0850, 6, unit)
    capacity = battery[0x19] / 10
    return {
        "soc": battery[0x02] / 10,
        "battery_v": battery[0x00] / 10,
        "battery_a": signed(battery[0x01], 16) / 10,
        "dc_w": signed(battery[0x26], 16),
        "ac_w": signed((inverter[0] << 16) | inverter[1], 32),
        "dispatch": dispatch,
        "dispatch_active": dispatch[0],
        "dispatch_w": ((dispatch[1] << 16) | dispatch[2]) - OFFSET,
        "dispatch_soc": dispatch[6] * SOC_STEP,
        "dispatch_s": (dispatch[7] << 16) | dispatch[8],
        "discharge_cutoff": settings[0],
        "charge_cutoff": settings[5],
        "capacity": capacity,
    }


def line(s):
    return (
        f"SOC {s['soc']:5.1f} %  AC {s['ac_w']:6d} W  DC {s['dc_w']:6d} W  "
        f"I {s['battery_a']:6.1f} A  dispatch actief={s['dispatch_active']} "
        f"P={s['dispatch_w']:+d} W  doel={s['dispatch_soc']:.1f} %  duur={s['dispatch_s']} s"
    )


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--host", default="192.168.1.151")
    p.add_argument("--port", type=int, default=502)
    p.add_argument("--unit", type=int, default=85)
    p.add_argument("--power", type=int, default=300, help=f"W, max {MAX_POWER}")
    p.add_argument("--seconds", type=int, default=300, help=f"duur van het commando, max {MAX_SECONDS}")
    p.add_argument("--discharge", action="store_true", help="ontladen in plaats van laden")
    p.add_argument("--target-soc", type=float, help="doel-SOC in %% (standaard de laad- of ontlaadgrens)")
    p.add_argument(
        "--auto-target", action="store_true",
        help="doel-SOC net onder wat haalbaar is in --seconds met --power, om te testen "
        "of de batterij zelf op het doel stopt",
    )
    p.add_argument(
        "--keepalive", type=int, default=0,
        help="0 (standaard): een keer schrijven en kijken of de batterij na --seconds zelf "
        "terugvalt. 30-120: elke zoveel seconden herschrijven en zelf stoppen.",
    )
    p.add_argument("--log", default=f"dispatch_test_{dt.datetime.now():%Y%m%d_%H%M%S}.csv")
    args = p.parse_args()

    if not 50 <= args.power <= MAX_POWER:
        sys.exit(f"--power moet tussen 50 en {MAX_POWER} W liggen")
    if not 10 <= args.seconds <= MAX_SECONDS:
        sys.exit(f"--seconds moet tussen 10 en {MAX_SECONDS} liggen")
    if args.keepalive and not 30 <= args.keepalive <= 120:
        sys.exit("--keepalive moet 0 zijn of tussen 30 en 120 s liggen")
    fallback = args.keepalive == 0

    client = connect(args.host, args.port)
    try:
        before = snapshot(client, args.unit)
        print("Nu:     ", line(before))
        print(f"Grenzen: ontladen {before['discharge_cutoff']} %, laden {before['charge_cutoff']} %")

        if before["dispatch_active"]:
            sys.exit(
                "\nDe dispatch is al actief: de AlphaESS-cloud stuurt de batterij nu. "
                "Een test zou overschreven worden. Zet in de app eerst een modus "
                "zonder cloud-sturing en probeer opnieuw."
            )
        if args.discharge:
            target = before["discharge_cutoff"]
            if before["soc"] < target + 5:
                sys.exit(f"\nSOC {before['soc']} % is te dicht bij de ontlaadgrens ({target} %).")
            power = args.power  # boven 32000 = ontladen
        else:
            target = before["charge_cutoff"]
            if before["soc"] > target - 3:
                sys.exit(f"\nSOC {before['soc']} % is te dicht bij de laadgrens ({target} %).")
            power = -args.power  # onder 32000 = laden

        if args.auto_target:
            # Wat de batterij in de test kan opnemen of afgeven, met het gemeten
            # rendement (~92,5 %), en daarvan 85 %: het doel moet zeker gehaald worden.
            stored = args.power * EFFICIENCY * args.seconds / 3600  # Wh
            change = stored / (before["capacity"] * 1000) * 100 * AUTO_TARGET_SHARE
            raw = before["soc"] + (-change if args.discharge else change)
            steps = int(raw / SOC_STEP) if not args.discharge else -int(-raw // SOC_STEP)
            args.target_soc = round(steps * SOC_STEP, 1)
            print(
                f"Auto-doel: {args.power} W x {EFFICIENCY:.3f} x {args.seconds} s = {stored:.0f} Wh "
                f"= {stored / (before['capacity'] * 1000) * 100:.2f} % van {before['capacity']} kWh; "
                f"85 % daarvan, afgerond op 0,4 %: doel {args.target_soc} %"
            )
        if args.target_soc is not None:
            if args.discharge and not before["discharge_cutoff"] <= args.target_soc < before["soc"]:
                sys.exit("--target-soc moet onder de huidige SOC en boven de ontlaadgrens liggen")
            if not args.discharge and not before["soc"] < args.target_soc <= before["charge_cutoff"]:
                sys.exit("--target-soc moet boven de huidige SOC en onder de laadgrens liggen")
            target = args.target_soc
        soc_raw = round(target / SOC_STEP)
        duration = args.seconds if fallback else 2 * args.keepalive
        # In terugval-modus wacht het script daarna nog zo lang op de batterij.
        watch = args.seconds + FALLBACK_GRACE if fallback else args.seconds
        block = [1, 0, OFFSET + power, 0, OFFSET, 2, soc_raw, 0, duration, 255]
        action = "ONTLADEN" if args.discharge else "LADEN"
        how = (
            f"een keer geschreven; geen stop: kijkt of de batterij na {duration} s zelf terugvalt "
            f"(vangnet: stop na {watch} s)"
            if fallback
            else f"keep-alive elke {args.keepalive} s, stop na {args.seconds} s"
        )
        print(
            f"\nTest: {action} met {args.power} W, doel-SOC {soc_raw * SOC_STEP:.1f} % "
            f"(0x0886 = {soc_raw}), duur in de batterij {duration} s."
            f"\nWerkwijze: {how}."
            f"\nSchrijft 0x0880-0x0889 = {block}"
            f"\nStop (bij Ctrl+C/fout/vangnet): {STOP_BLOCK}"
        )
        if args.power > 1000:
            print(
                f"\nLet op: {args.power} W is ongeveer {args.power / 230:.0f} A uit het stopcontact. "
                "Zet zware verbruikers op dezelfde groep even uit."
            )
        if input("\nTyp 'ja' om te starten: ").strip().lower() != "ja":
            sys.exit("Afgebroken, er is niets geschreven.")

        with open(args.log, "w", newline="") as fh:
            log = csv.writer(fh)
            log.writerow(["tijd", "sec", "fase", "soc", "ac_w", "dc_w", "battery_a",
                          "dispatch_active", "dispatch_w", "dispatch_soc", "dispatch_s"])
            t0 = time.monotonic()

            def record(phase, s):
                log.writerow([dt.datetime.now().isoformat(timespec="seconds"),
                              round(time.monotonic() - t0), phase, s["soc"], s["ac_w"], s["dc_w"],
                              s["battery_a"], s["dispatch_active"], s["dispatch_w"],
                              s["dispatch_soc"], s["dispatch_s"]])
                fh.flush()

            record("voor", before)
            active = []  # snapshots while the dispatch ran
            overwritten = False
            fell_back = None  # seconds after the write the battery ended it itself
            writes = 0
            stop_needed = True  # cleared only once the battery has ended it itself
            try:
                write_block(client, block, args.unit)
                writes += 1
                print("\nGeschreven. Teruglezen:", read(client, DISPATCH, 10, args.unit))
                start = last_write = time.monotonic()
                while time.monotonic() - start < watch:
                    time.sleep(5)
                    if not fallback and time.monotonic() - last_write >= args.keepalive:
                        write_block(client, block, args.unit)
                        writes += 1
                        last_write = time.monotonic()
                        print(f"{last_write - start:5.0f} s  keep-alive geschreven ({writes}x)")
                    s = snapshot(client, args.unit)
                    elapsed = time.monotonic() - start
                    record("test" if fell_back is None else "na", s)
                    print(f"{elapsed:5.0f} s ", line(s))
                    if fell_back is None and s["dispatch_active"] == 0:
                        fell_back = elapsed
                        print(f"  >> de batterij heeft de dispatch zelf beeindigd na {elapsed:.0f} s, "
                              f"SOC {s['soc']} %")
                        if fallback:
                            stop_needed = False
                            watch = min(watch, elapsed + 20)  # nog even nakijken
                    if fell_back is None:
                        active.append(s)
                        if s["dispatch"] != block and not overwritten:
                            overwritten = True
                            print("  !! dispatch-blok wijkt af van wat geschreven is:", s["dispatch"])
            finally:
                if stop_needed:
                    write_block(client, STOP_BLOCK, args.unit)
                    print("\nStop geschreven. Teruglezen:", read(client, DISPATCH, 10, args.unit))

            if stop_needed:
                for _ in range(3):
                    time.sleep(5)
                    s = snapshot(client, args.unit)
                    record("na", s)
                    print("na    ", line(s))

        settled = active[2:] or active
        ac = sum(x["ac_w"] for x in settled) / len(settled) if settled else 0
        dc = sum(x["dc_w"] for x in settled) / len(settled) if settled else 0
        print("\n=== Resultaat ===")
        print(f"Gevraagd: {power:+d} W (+ = ontladen)   gemeten AC {ac:+.0f} W, DC {dc:+.0f} W")
        if ac and dc:
            ratio = (dc / ac) if power < 0 else (ac / dc)
            print(f"Rendement: {ratio * 100:.1f} %")
        sign_ok = (ac < -50) if power < 0 else (ac > 50)
        print("Teken klopt:", "ja" if sign_ok else "NEE / geen reactie")
        print(f"SOC: {before['soc']} % -> {s['soc']} %")
        print("Blok overschreven tijdens test (cloud?):", "ja" if overwritten else "nee")
        if fell_back is not None:
            target_pct = soc_raw * SOC_STEP
            reached = (s["soc"] >= target_pct - 0.1) if power < 0 else (s["soc"] <= target_pct + 0.1)
            if fell_back < duration - 10 and reached:
                print(f"Doel-SOC: de batterij stopte zelf op het doel na {fell_back:.0f} s "
                      f"(doel {target_pct:.1f} %, gemeten {s['soc']} %)")
            elif fell_back < duration - 10:
                print(f"De batterij stopte zelf na {fell_back:.0f} s, VOOR de duur ({duration} s) en "
                      f"zonder het doel ({target_pct:.1f} %) te halen (SOC {s['soc']} %)")
            else:
                print(f"Terugval: de batterij stopte zelf na {fell_back:.0f} s (duur was {duration} s)")
        elif fallback:
            print(f"Terugval: GEEN - na {watch} s nog actief, vangnet-stop geschreven")
        print(f"Schrijfacties: {writes}" + (" + 1 stop" if stop_needed else ""))
        print("Dispatch nu actief:", s["dispatch_active"])
        print(f"Meetlog: {args.log}  - stuur dit bestand en deze uitvoer op.")
    finally:
        client.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # Het stop-commando is dan al geschreven (finally hierboven).
        sys.exit("\nAfgebroken met Ctrl+C; de dispatch is gestopt.")
