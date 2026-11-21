# -*- coding: utf-8 -*-
"""Minimal SQLite MCP server for the LineSight database (read-only).

Exposes:
  - tool `query`        : run a read-only SQL SELECT
  - tool `list_tables`  : list tables with row counts
  - tool `describe`     : columns of a table
  - resource `schema://` : full DDL

Run:  python -m linesight.mcp_db --db-path <path>
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys

from mcp.server.mcpserver import MCPServer
from mcp.server.stdio import stdio_server


def make_server(db_path: str) -> MCPServer:
    mcp = MCPServer("linesight-db")

    def connect() -> sqlite3.Connection:
        c = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        c.row_factory = sqlite3.Row
        return c

    @mcp.tool()
    def list_tables() -> str:
        """List all tables in the database with their row counts."""
        c = connect()
        try:
            rows = c.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            out = []
            for r in rows:
                n = c.execute(f"SELECT COUNT(*) FROM \"{r['name']}\"").fetchone()[0]
                out.append({"table": r["name"], "rows": n})
            return json.dumps(out, indent=2)
        finally:
            c.close()

    @mcp.tool()
    def describe(table: str) -> str:
        """Describe the columns of a table."""
        c = connect()
        try:
            cols = c.execute(f"PRAGMA table_info(\"{table}\")").fetchall()
            return json.dumps([dict(col) for col in cols], indent=2, default=str)
        finally:
            c.close()

    @mcp.tool()
    def query(sql: str) -> str:
        """Run a read-only SQL query (SELECT only) and return the rows as JSON."""
        s = sql.strip().lower()
        if not s.startswith("select") and not s.startswith("with") and not s.startswith("pragma"):
            return "error: only SELECT / WITH / PRAGMA queries are allowed"
        c = connect()
        try:
            cur = c.execute(sql)
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            return json.dumps({"columns": cols, "rows": rows, "count": len(rows)}, indent=2, default=str)
        except Exception as e:
            return f"error: {e}"
        finally:
            c.close()

    @mcp.resource("schema://ddl")
    def schema() -> str:
        """Full DDL of the database."""
        c = connect()
        try:
            rows = c.execute(
                "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type, name"
            ).fetchall()
            return "\n\n".join(r[0] for r in rows)
        finally:
            c.close()

    return mcp


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", default="data/linesight.db")
    args = parser.parse_args()
    mcp = make_server(args.db_path)
    import asyncio
    asyncio.run(mcp.run_stdio_async())


if __name__ == "__main__":
    main()