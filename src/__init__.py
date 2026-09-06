"""
MCP Legal Assistant source package.

This file used to insert its own directory at the front of ``sys.path`` "for
relative imports". Every import in the project already uses the ``src.`` prefix,
so the insert did nothing useful -- and it put ``src/mcp`` in front of the MCP
SDK's ``mcp`` package, so ``from mcp.server.stdio import stdio_server`` in
``src/mcp/server.py`` resolved to this repository's own module and failed with
``No module named 'mcp.server.stdio'; 'mcp.server' is not a package``.
``python main.py mcp`` and the ``legal-assistant-mcp`` console script were
broken by it.
"""
