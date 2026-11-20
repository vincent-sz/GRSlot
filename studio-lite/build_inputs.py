# SPDX-License-Identifier: GPL-2.0-only
"""Bind the native colour payload to a validated Studio project and stock input."""

from check_project import DEFAULT_LIBRARY, load_checked_project
from native_profile import require
from native_registry import build_native_registry


def prepare_build_inputs(project_path, firmware_path, library_path=DEFAULT_LIBRARY):
    project, receipt = load_checked_project(project_path, firmware_path, library_path)
    if firmware_path.is_dir():
        firmware_path = firmware_path / "fwdc239b.bin"
    factory = firmware_path.read_bytes()
    payload, registry = build_native_registry(
        factory, library_path, selected=project["selected"], defaults=project["slots"]
    )
    require(registry["library_sha256"] == receipt["library_id"], "Film library changed during preparation")
    return factory, project, receipt, payload, registry
