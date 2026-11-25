"""Registers Yoisho BD OS with Sellbird (entry point ``sellbird.extensions``)."""

from __future__ import annotations

from yoisho_bd import api, commands, livecheck, server


def install(registry) -> None:
    registry.add_router(api.router)
    registry.add_cli_command(
        "yoisho-dashboard", server.configure_dashboard,
        help="Yoisho: run Yoisho BD OS (Sellbird's dashboard with Yoisho's screens)")
    registry.add_cli_command(
        "yoisho-check", livecheck.configure,
        help="Yoisho: test web search, website reading and Claude on this server")
    registry.add_cli_command(
        "yoisho-import", commands.configure_import,
        help="Yoisho: import clients, partners or competitors from a CSV file")
    registry.add_cli_command(
        "yoisho-status", commands.configure_status,
        help="Yoisho: count organizations, opportunities and tasks")
