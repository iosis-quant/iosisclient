from __future__ import annotations

import sys

from iosisclient.client import (
    IosisError,
    fetch_version_status,
    local_package_versions,
    pypi_latest_versions,
    version_supported,
)
from iosisclient.config import Config


def version(args: object, config: Config) -> int:
    installed = local_package_versions()
    latest = pypi_latest_versions()

    try:
        minimums = fetch_version_status(config.cloud.base_url)
    except IosisError as exc:
        print(f"Warning: could not reach version API ({exc.message}).", file=sys.stderr)
        minimums = {}
    if not isinstance(minimums, dict):
        minimums = {}

    ok = True
    for package in ("iosisclient", "iosislib"):
        have = installed.get(package) or "-"
        new = latest.get(package)
        if new and have != "-" and new != have:
            freshness = f"{have} (latest {new} — update available)"
        else:
            freshness = have
        floor = minimums.get(package)
        floor_str = floor if isinstance(floor, str) else None
        support = version_supported(installed.get(package), floor_str) if floor_str else None
        verdict = (
            "supported" if support is True
            else "NOT SUPPORTED" if support is False
            else "unknown"
        )
        if support is False:
            ok = False
        print(f"{package}: {freshness} | min supported {floor_str or '-'} → {verdict}")

    if not ok:
        print("Error: installed versions are no longer supported. Upgrade and retry.", file=sys.stderr)
        return 1
    return 0
