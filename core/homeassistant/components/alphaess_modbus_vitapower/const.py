"""Constants for the AlphaESS VitaPower integration."""

DOMAIN = "alphaess_modbus_vitapower"
ATTR_MANUFACTURER = "AlphaESS"

DEFAULT_NAME = "VitaPower"
MODEL = "VitaPower 3600 AC"
DEFAULT_PORT = 502
SCAN_INTERVAL = 5
SETTINGS_SCAN_INTERVAL = 300

CONF_UNIT_ID = "unit_id"

# Remote control: the command is written again this often, and each write lasts
# this long in the battery, so it takes control back itself within that time
# when Home Assistant stops writing.
KEEPALIVE_INTERVAL = 60
DISPATCH_DURATION = 300

# Control modes. DAO writes "on" and "off": set "entity set operating mode on"
# and "entity set operating mode off" to these.
MODE_ON = "on"
"""Follow the power setpoint."""
MODE_OFF = "off"
"""Hold the battery idle at 0 W."""
MODE_AUTO = "auto"
"""Write nothing: the battery follows its own mode."""
CONTROL_MODES = [MODE_ON, MODE_OFF, MODE_AUTO]

# Targets for a command when the configured cut-offs are not known yet.
DEFAULT_CHARGE_CUTOFF = 100
DEFAULT_DISCHARGE_CUTOFF = 10
