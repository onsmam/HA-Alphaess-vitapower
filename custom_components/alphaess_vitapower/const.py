"""Constants for the AlphaESS VitaPower integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "alphaess_vitapower"

CONF_UNIT_ID: Final = "unit_id"

DEFAULT_PORT: Final = 502
DEFAULT_UNIT_ID: Final = 85

MANUFACTURER: Final = "AlphaESS"
MODEL: Final = "VitaPower 3600 AC"
DEVICE_NAME: Final = "VitaPower"

# The coordinator ticks at the fastest block interval; slower blocks are read
# only when they are due (see registers.BLOCKS).
UPDATE_INTERVAL: Final = timedelta(seconds=5)

# Taken over from the YAML hub that has been running against this device:
# `delay: 1` and `message_wait_milliseconds: 30`.
CONNECT_DELAY: Final = 1.0
MESSAGE_SPACING: Final = 0.03
