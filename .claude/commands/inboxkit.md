---
description: Run an InboxKit task via the InboxKit MCP server
argument-hint: [what you want InboxKit to do]
allowed-tools: mcp__inboxkit__*
---

Use the **InboxKit** MCP server (registered in `.mcp.json` as `inboxkit`) to handle the
following request:

$ARGUMENTS

Guidance:
- Discover the available InboxKit tools (`mcp__inboxkit__*`) and pick the ones that fit
  the request. If no arguments were given above, list what InboxKit can do and ask what
  the user wants.
- If the server needs sign-in or a token and isn't connected yet, tell the user to run
  `/mcp` to authenticate the `inboxkit` server, then retry.
- Report results concisely and confirm any action that sends, deletes, or modifies data
  before performing it.
