"""Registers every resource domain's tools onto a FastMCP instance."""

from intercom_mcp.tools import admins, companies, contacts, conversations, tickets

_MODULES = (contacts, conversations, companies, tickets, admins)


def register_all(mcp) -> None:
    for module in _MODULES:
        module.register(mcp)
