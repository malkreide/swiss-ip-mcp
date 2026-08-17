#!/usr/bin/env python3
"""Regenerate tool_manifest.json (SEC-022).

Run after any intentional change to a tool's name, description, input schema or
annotations, then commit the updated manifest and note the change in the
CHANGELOG (and bump the major version if the change is breaking).

    python scripts/update_tool_manifest.py
"""

from __future__ import annotations

import asyncio
import json
import pathlib

from swiss_ip_mcp.integrity import compute_manifest
from swiss_ip_mcp.server import mcp

MANIFEST_PATH = pathlib.Path(__file__).resolve().parents[1] / "tool_manifest.json"


def main() -> None:
    manifest = asyncio.run(compute_manifest(mcp))
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(manifest)} tool fingerprints to {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
