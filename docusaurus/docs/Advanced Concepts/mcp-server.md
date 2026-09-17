---
sidebar_label: MCP Server
---

# Backtest Analysis MCP Server

The built-in Model Context Protocol (MCP) server exposes stored backtests to
GitHub Copilot, Claude, and other MCP-compatible clients. It uses JSON-RPC over
stdio and reads one or more backtest directories without a web server.

## Start the server

Pass each backtest directory with `--directory` or `-d`:

```bash
investing-algorithm-framework mcp -d ./my-backtests
```

Multiple directories can be analyzed together:

```bash
investing-algorithm-framework mcp \
  -d ./experiments/momentum \
  -d ./experiments/mean-reversion
```

Keep stdout reserved for MCP messages because the client communicates with the
server over stdio.

## Configure VS Code

Create `.vscode/mcp.json` in the project containing your backtests:

```json
{
  "servers": {
    "backtest-analysis": {
      "command": "investing-algorithm-framework",
      "args": ["mcp", "-d", "./my-backtests"]
    }
  }
}
```

Use an absolute directory when the MCP client starts with a different working
directory. The command must resolve in the client's environment; alternatively,
point `command` at the virtual environment's executable.

## Analysis tools

The server provides tools for:

- Listing, filtering, ranking, and comparing strategies
- Reading strategy details, metadata, tags, and complete analyses
- Inspecting trades, orders, positions, scaling, stop-losses, and take-profits
- Querying equity, drawdown, rolling Sharpe, monthly and yearly returns
- Comparing symbols, return scenarios, correlations, and window coverage
- Reading portfolio snapshots and trading activity

Start with `list_strategies` to discover available algorithm IDs. Most tools
accept one strategy ID, multiple IDs, or a tag. Analytical series can also be
limited to a backtest window.

## Notes and dashboard integration

The server can create, list, read, update, and delete analysis notes. Notes are
persisted beside the backtests and appear in the dashboard's Report Builder.
Strategy selections support `keep`, `maybe`, and `reject` tags.

Dashboard snapshots can be embedded in note Markdown with `![[snap:ID]]`. Read
the note to discover snapshot IDs, then update its Markdown to place charts or
tables in the analysis.

## Data and security

The supplied bundles can contain strategy parameters, trades, orders, positions,
and portfolio history. Only expose the server to clients you trust, and do not
put credentials or secrets in backtest metadata or notes.

The MCP process is local and does not deploy a remote service. Remote access
requires transport, authentication, and network controls from your own
infrastructure.

See [Backtest Storage](../Getting%20Started/backtest-storage.md) and
[Backtest Reports](../Getting%20Started/backtest-reports.md).