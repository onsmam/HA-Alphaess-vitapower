#!/usr/bin/env python3
"""Build custom_components/alphaess_modbus_vitapower from core/ and library/.

The core integration is the source. This copies it into the HACS layout with
the device library vendored, so a Home Assistant without the library on PyPI
can run it:

- library/src/alphaess_modbus_vitapower -> custom_components/.../vendor/
- core/homeassistant/components/alphaess_modbus_vitapower/*.py, with the
  library imported from the vendored copy, and setup/unload returning a bool
  (Home Assistant before 2026.11 requires one from a custom integration)
- strings.json -> translations/en.json, with every [%key:...] reference
  resolved against a Home Assistant install; translations/nl.json is kept
  and checked to have the same keys
- manifest.json with the HACS fields
- core/tests/components/alphaess_modbus_vitapower -> tests/, run against the
  custom integration with pytest-homeassistant-custom-component (snapshots
  are the harness's own, in tests/__snapshots__)

Run it after changing core/ or library/:

    python3 scripts/sync_custom.py [--ha-path /path/to/homeassistant] [--check]

--check exits non-zero if the generated tree differs from what is on disk.
"""

import argparse
import filecmp
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DOMAIN = "alphaess_modbus_vitapower"
LIBRARY = "alphaess_modbus_vitapower"
CORE = ROOT / "core" / "homeassistant" / "components" / DOMAIN
LIBRARY_SRC = ROOT / "library" / "src" / LIBRARY
TARGET = ROOT / "custom_components" / DOMAIN
CORE_TESTS = ROOT / "core" / "tests" / "components" / DOMAIN
TESTS = ROOT / "tests"
VERSION_FILE = ROOT / "custom_components" / "VERSION"

# Kept in the target as is: maintained by hand.
HANDWRITTEN = ("translations/nl.json",)

# Shown in the Modbus integration's strings since 2026.11; resolved from here
# when the Home Assistant install is older.
MODBUS_COMMON_FALLBACK = {
    "tcp_host_description": "The hostname or IP address of the device or its "
    "Modbus TCP gateway.",
    "tcp_port_description": "The Modbus TCP port to connect to.",
}

_KEY = re.compile(r"\[%key:([a-z0-9_:]+)%\]")

# (file, old, new): the only places the custom version may differ from core.
_RETURN_BOOL = (
    (
        "__init__.py",
        "async def async_setup_entry(hass: HomeAssistant, entry: VitaPowerConfigEntry) -> None:",
        "async def async_setup_entry(hass: HomeAssistant, entry: VitaPowerConfigEntry) -> bool:",
    ),
    (
        "__init__.py",
        "    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)\n",
        "    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)\n"
        "    return True\n",
    ),
    (
        "__init__.py",
        "async def async_unload_entry(hass: HomeAssistant, entry: VitaPowerConfigEntry) -> None:",
        "async def async_unload_entry(hass: HomeAssistant, entry: VitaPowerConfigEntry) -> bool:",
    ),
    (
        "__init__.py",
        "    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)",
        "    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)",
    ),
)


def _ha_path(given: str | None) -> Path:
    if given:
        return Path(given)
    # Found, not imported: only its strings are needed, not its dependencies.
    spec = importlib.util.find_spec("homeassistant")
    if spec is None or not spec.submodule_search_locations:
        sys.exit("Home Assistant is not installed; pass --ha-path")
    return Path(next(iter(spec.submodule_search_locations)))


def _lookup(tree: dict[str, Any], path: list[str]) -> Any:
    node: Any = tree
    for part in path:
        node = node[part]
    return node


class _Resolver:
    def __init__(self, ha: Path, own: dict[str, Any]) -> None:
        self._common = json.loads((ha / "strings.json").read_text())
        self._own = own
        self._components: dict[str, dict[str, Any]] = {DOMAIN: own}
        self._ha = ha

    def _component(self, name: str) -> dict[str, Any]:
        if name not in self._components:
            for candidate in ("strings.json", "translations/en.json"):
                path = self._ha / "components" / name / candidate
                if path.exists():
                    self._components[name] = json.loads(path.read_text())
                    break
            else:
                sys.exit(f"no strings for component {name!r} under {self._ha}")
        return self._components[name]

    def _key(self, key: str) -> str:
        parts = key.split("::")
        if parts[0] == "common":
            value = _lookup(self._common, parts)
        elif parts[0] == "component":
            name, *rest = parts[1:]
            try:
                value = _lookup(self._component(name), rest)
            except KeyError:
                if name == "modbus" and rest[:1] == ["common"]:
                    value = MODBUS_COMMON_FALLBACK[rest[1]]
                else:
                    raise
        else:
            sys.exit(f"cannot resolve [%key:{key}%]")
        return self.text(value)

    def text(self, value: str) -> str:
        return _KEY.sub(lambda match: self._key(match.group(1)), value)

    def tree(self, node: Any) -> Any:
        if isinstance(node, dict):
            return {key: self.tree(value) for key, value in node.items()}
        if isinstance(node, str):
            return self.text(node)
        return node


def _shape(node: Any, prefix: str = "") -> set[str]:
    if isinstance(node, dict):
        return {
            path
            for key, value in node.items()
            for path in _shape(value, f"{prefix}{key}.")
        }
    return {prefix.rstrip(".")}


def _python(name: str, source: str) -> str:
    source = re.sub(
        rf"^from {LIBRARY}(\.| )",
        lambda match: f"from .vendor.{LIBRARY}{match.group(1)}",
        source,
        flags=re.MULTILINE,
    )
    for file, old, new in _RETURN_BOOL:
        if file == name:
            if old not in source:
                sys.exit(f"{name}: expected {old!r}; update _RETURN_BOOL")
            source = source.replace(old, new)
    return source


def _manifest(version: str) -> str:
    manifest = json.loads((CORE / "manifest.json").read_text())
    manifest["documentation"] = "https://github.com/onsmam/HA-Alphaess-vitapower"
    manifest["issue_tracker"] = "https://github.com/onsmam/HA-Alphaess-vitapower/issues"
    manifest["loggers"] = [
        f"custom_components.{DOMAIN}.vendor.{LIBRARY}" if logger == LIBRARY else logger
        for logger in manifest["loggers"]
    ]
    # Vendored, so nothing to install; modbus_connection comes with modbus.
    manifest["requirements"] = []
    manifest.pop("quality_scale", None)
    manifest["version"] = version
    head = {key: manifest.pop(key) for key in ("domain", "name")}
    return json.dumps({**head, **dict(sorted(manifest.items()))}, indent=2) + "\n"


def build(out: Path, ha: Path) -> None:
    """Write the custom integration into ``out``."""
    out.mkdir(parents=True)
    for source in sorted(CORE.glob("*.py")):
        (out / source.name).write_text(_python(source.name, source.read_text()))
    shutil.copy(CORE / "icons.json", out / "icons.json")

    vendor = out / "vendor"
    shutil.copytree(
        LIBRARY_SRC,
        vendor / LIBRARY,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    (vendor / "__init__.py").write_text(
        f'"""A copy of library/src/{LIBRARY}, kept in sync by scripts/sync_custom.py."""\n'
    )

    strings = json.loads((CORE / "strings.json").read_text())
    english = _Resolver(ha, strings).tree(strings)
    (out / "translations").mkdir()
    (out / "translations" / "en.json").write_text(
        json.dumps(english, indent=2, ensure_ascii=False) + "\n"
    )
    for handwritten in HANDWRITTEN:
        current = TARGET / handwritten
        if not current.exists():
            sys.exit(f"{current} is missing; write it by hand")
        shutil.copy(current, out / handwritten)
        missing = _shape(english) - _shape(json.loads(current.read_text()))
        extra = _shape(json.loads(current.read_text())) - _shape(english)
        if missing or extra:
            sys.exit(
                f"{handwritten} does not match en.json:\n"
                f"  missing: {sorted(missing)}\n  extra: {sorted(extra)}"
            )

    (out / "manifest.json").write_text(_manifest(VERSION_FILE.read_text().strip()))


# (old, new) for the tests, in order.
_TEST_REWRITES = (
    (f"homeassistant.components.{DOMAIN}", f"custom_components.{DOMAIN}"),
    ("pytest_homeassistant.", "pytest_homeassistant_custom_component."),
    (
        f'"{LIBRARY}.device.CONNECT_DELAY"',
        f'"custom_components.{DOMAIN}.vendor.{LIBRARY}.device.CONNECT_DELAY"',
    ),
)

# Fixtures core's own test plugin provides.
_TEST_FIXTURES = """

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    \"\"\"Load custom_components/ in every test.\"\"\"


@pytest.fixture
def snapshot(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    \"\"\"Serialize registry entries and states the way Home Assistant does.\"\"\"
    return snapshot.use_extension(HomeAssistantSnapshotExtension)


@pytest.fixture
def entity_registry_enabled_by_default() -> Generator[None]:
    \"\"\"Enable every entity in the registry.\"\"\"
    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        return_value=True,
    ):
        yield
"""


def build_tests(out: Path) -> None:
    """Write the custom integration's tests into ``out``."""
    out.mkdir(parents=True)
    for source in sorted(CORE_TESTS.glob("*.py")):
        text = source.read_text()
        for old, new in _TEST_REWRITES:
            text = text.replace(old, new)
        if source.name == "conftest.py":
            text = text.replace(
                "import pytest\n",
                "import pytest\n"
                "from pytest_homeassistant_custom_component.syrupy import (\n"
                "    HomeAssistantSnapshotExtension,\n"
                ")\n"
                "from syrupy.assertion import SnapshotAssertion\n",
                1,
            )
            text = text.rstrip("\n") + "\n" + _TEST_FIXTURES
        (out / source.name).write_text(text)


def _ruff(path: Path, config: Path) -> None:
    """Sort imports and format, as the longer import paths need re-wrapping."""
    ruff = shutil.which("ruff")
    command = [ruff] if ruff else [sys.executable, "-m", "ruff"]
    for args in (
        ["check", "--fix", "--select", "I001", "--quiet"],
        ["format", "--quiet"],
    ):
        subprocess.run(
            [*command, *args, "--config", str(config), str(path)], check=True
        )


def _differences(left: Path, right: Path) -> list[str]:
    comparison = filecmp.dircmp(
        left,
        right,
        ignore=[
            "__pycache__",
            "__snapshots__",
            "snapshots",
            "ruff.toml",
            ".ruff_cache",
        ],
    )
    found = [
        *(f"only in {left}: {name}" for name in comparison.left_only),
        *(f"only in {right}: {name}" for name in comparison.right_only),
        *(f"differs: {name}" for name in comparison.diff_files),
    ]
    for name in comparison.common_dirs:
        found += _differences(left / name, right / name)
    return found


def main() -> int:
    """Generate the custom integration, or check it is up to date."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ha-path", help="the homeassistant package directory")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    ha = _ha_path(args.ha_path)

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / DOMAIN
        tests = Path(tmp) / "tests"
        build(out, ha)
        build_tests(tests)
        _ruff(out, ROOT / ".ruff.toml")
        _ruff(tests, ROOT / "tests" / "ruff.toml")
        if args.check:
            differences = _differences(out, TARGET)
            if TESTS.exists():
                differences += _differences(tests, TESTS)
            else:
                differences.append(f"{TESTS} is missing")
            if differences:
                print("custom_components is out of date; run scripts/sync_custom.py")
                print("\n".join(differences))
                return 1
            print("custom_components is up to date")
            return 0
        shutil.rmtree(TARGET, ignore_errors=True)
        shutil.copytree(out, TARGET)
        TESTS.mkdir(exist_ok=True)
        for generated in tests.iterdir():
            shutil.copy(generated, TESTS / generated.name)
    print(f"wrote {TARGET.relative_to(ROOT)} and {TESTS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
