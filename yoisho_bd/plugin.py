"""Registers Yoisho BD OS with Sellbird (entry point ``sellbird.extensions``)."""

from __future__ import annotations

from yoisho_bd import livecheck


def install(registry) -> None:
    registry.add_cli_command(
        "yoisho-check", livecheck.configure,
        help="Yoisho: test web search, website reading and Claude on this server")
