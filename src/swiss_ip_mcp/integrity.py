"""Tool-definition hash pinning (audit finding SEC-022).

A "rug pull" is when a server silently changes a tool's behaviour after the
user approved it. To make any change to the exposed tool surface explicit and
reviewable, we pin a SHA-256 fingerprint of every tool definition (name,
description, input schema, annotations) in ``tool_manifest.json``.

``tests/test_server.py`` recomputes the fingerprints and fails if they drift
from the pinned manifest, forcing an intentional regeneration via
``scripts/update_tool_manifest.py`` (and a CHANGELOG note).

All tools also share the immutable ``swiss_ip_`` namespace prefix, so they
cannot be confused with another server's tools.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

TOOL_NAMESPACE_PREFIX = "swiss_ip_"


def fingerprint_tool(tool: Any) -> str:
    """Stable SHA-256 over a tool's externally visible definition."""
    annotations = None
    if getattr(tool, "annotations", None) is not None:
        annotations = tool.annotations.model_dump(mode="json")
    payload = {
        "name": tool.name,
        "description": tool.description or "",
        "inputSchema": tool.inputSchema,
        "annotations": annotations,
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


async def compute_manifest(mcp: Any) -> dict[str, str]:
    """Return {tool_name: fingerprint} for all registered tools, sorted."""
    tools = await mcp.list_tools()
    return {t.name: fingerprint_tool(t) for t in sorted(tools, key=lambda t: t.name)}
