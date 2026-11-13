"""The component base every VitaPower sub-system builds on."""

from __future__ import annotations

from modbus_connection.model import Component, Range, UpdateReport

__all__ = [
    "READABLE_RANGES",
    "UpdateReport",
    "VitaPowerComponent",
]

# The holding ranges the VitaPower answers, from full register scans. Reads
# never bridge out of these, so the planner cannot run into the addresses that
# fail a whole block (0x0453-0x0454, 0x072C-0x073F) or into the network
# settings (0x0808-0x0810), which nothing here needs to read.
READABLE_RANGES: tuple[Range, ...] = (
    (0x0001, 0x0001),
    (0x0010, 0x0042),
    (0x0081, 0x0081),
    (0x0090, 0x00B6),
    (0x0100, 0x0148),
    # 0x0441-0x0449 answer, but change layout between charging and
    # discharging; nothing is read from them.
    (0x0400, 0x0440),
    (0x044A, 0x0452),
    (0x0640, 0x0658),
    (0x0700, 0x072B),
    (0x0740, 0x0760),
    (0x0800, 0x0807),
    (0x0811, 0x0891),
    (0x08D0, 0x08D5),
    (0x1000, 0x1024),
)


class VitaPowerComponent(Component):
    """A sub-system of the VitaPower's holding register map."""

    register_ranges = READABLE_RANGES
    # Full scans read 16-register blocks without trouble; the largest block
    # here (the battery) is 46 registers, well inside one request.
    max_span = 100
