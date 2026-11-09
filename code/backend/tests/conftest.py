"""Package-level test configuration (not part of the pinned study code).

Two CLI tests resolve points through the product's city builder
(`build_city_cey10_from_era5_land_hourly.py`), which depends on further product modules and is not part of this
package. Point resolution was done once before the study and is frozen in `study/03-freeze.json`; reproduction does
not repeat it. Those two tests are therefore skipped, with this reason, when the city builder is absent.
"""
from pathlib import Path

import pytest

_CITY_BUILDER = Path(__file__).resolve().parents[1] / "scripts" / "build_city_cey10_from_era5_land_hourly.py"
_NEEDS_CITY_BUILDER = {"test_all_subcommands_and_manifest", "test_points_file"}


def pytest_collection_modifyitems(config, items):
    if _CITY_BUILDER.exists():
        return
    skip = pytest.mark.skip(reason="needs the product city builder (point resolution, frozen in study/03-freeze.json)")
    for item in items:
        if item.name in _NEEDS_CITY_BUILDER:
            item.add_marker(skip)
