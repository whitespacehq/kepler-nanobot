"""Auto-discover and register Kepler tools from nanobot.kepler.tools."""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any

from loguru import logger

from nanobot.agent.tools.base import Tool


def load_kepler_tools(*, bus: Any) -> list[Tool]:
    """Discover tool modules in this package and instantiate them.

    Each module that exports a ``create_tool(**kwargs)`` function is called
    with the available dependencies.  The function should accept ``**kwargs``
    and pick what it needs — this lets us add dependencies later without
    breaking existing tools.
    """
    import nanobot.kepler.tools as pkg

    kwargs = {"bus": bus}
    tools: list[Tool] = []

    for _, module_name, ispkg in pkgutil.iter_modules(pkg.__path__):
        if module_name.startswith("_") or module_name == "loader" or ispkg:
            continue
        try:
            mod = importlib.import_module(f"nanobot.kepler.tools.{module_name}")
            if hasattr(mod, "create_tool"):
                tool = mod.create_tool(**kwargs)
                if tool is not None:
                    tools.append(tool)
                    logger.debug("Loaded Kepler tool: {}", tool.name)
        except Exception:
            logger.exception("Failed to load Kepler tool '{}'", module_name)

    return tools
