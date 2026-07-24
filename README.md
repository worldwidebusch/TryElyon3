# Elyon / tryelyon.com

Marketing site for **Elyon**, AI employees for sales, support and operations (MX / LATAM / US / ES).

Single self-contained page: no build step, no dependencies, no backend. Bilingual (EN/ES) with
browser auto-detection and a manual toggle.

## Structure

```
index.html               The full site (HTML + CSS + JS in one file)
CNAME                    Custom domain for GitHub Pages (tryelyon.com)
brand/guidelines.html    Elyon brand system (mark, wordmark, color, type, usage)
brand/assets/*.svg       Logo, wordmark, lockups, app icon, favicon (production SVGs)
```

## Deploy with GitHub Pages

1. Push this repo to GitHub (see below).
2. Repo Settings -> Pages -> Source: `Deploy from a branch`, Branch: `main`, folder `/ (root)`.
3. DNS for tryelyon.com:
   - `A` records for the apex -> 185.199.108.153 / 185.199.109.153 / 185.199.110.153 / 185.199.111.153
   - `CNAME` record for `www` -> `<your-github-username>.github.io`
4. Back in Settings -> Pages, set custom domain `tryelyon.com` and enable **Enforce HTTPS**
   (the CNAME file in this repo keeps the domain setting across deploys).

## Before launch (checklist)

- [ ] `index.html`: set `ELYON_WA` (search for `const ELYON_WA`) to your WhatsApp Business
      number, digits only with country code. Powers the floating button AND the lead form.
- [ ] Replace the three SAMPLE testimonials in the `03.5 / FIELD RESULTS` section with real,
      verifiable customer results. Do not launch with placeholders.
- [ ] Paste GA4 + Meta Pixel snippets into the marked slot in `<head>`. Events already fire
      through `trackEvent()`.
- [ ] Keep the capacity line in `07.0 / OPEN CHANNEL` only if it is genuinely true.
- [ ] Verify current WhatsApp per-message rates and your LLM costs; adjust plan limits and
      overage rates in the pricing section if needed.

## Editing

- Brand colors/typography: CSS variables at the top of `index.html` (`BRAND TOKENS`).
- Spanish copy: the `ES` dictionary at the top of the `<script>` block. English lives in the HTML.
- Demo slideshow scenes: `.scene` blocks inside `#screen`; timings via `data-d` / `data-dur`.

## MCP integration (Claude Code)

This repo registers the **InboxKit** MCP server as a project-scoped tool provider in
[`.mcp.json`](.mcp.json), so anyone running Claude Code inside this repo can use its
tools for inbox/email tasks.

```json
{
  "mcpServers": {
    "inboxkit": {
      "type": "http",
      "url": "https://mcp.inboxkit.com/mcp"
    }
  }
}
```

- On first use, Claude Code prompts you to approve the project MCP server.
- Auth uses an InboxKit API token, injected from the `INBOXKIT_TOKEN` environment
  variable (never committed to git). Export it before launching Claude Code:

  ```sh
  export INBOXKIT_TOKEN="<your-inboxkit-api-token>"
  claude   # picks up .mcp.json and expands ${INBOXKIT_TOKEN} into the auth header
  ```

  If InboxKit expects a different header name than `Authorization: Bearer`, adjust the
  `headers` block in `.mcp.json` accordingly.
- Verify it loaded with `claude mcp list` (or `/mcp` inside a Claude Code session).

### `/inboxkit` slash command

A project command in [`.claude/commands/inboxkit.md`](.claude/commands/inboxkit.md) lets you
invoke InboxKit directly:

```
/inboxkit <what you want InboxKit to do>
```

It routes the request to the `inboxkit` MCP tools. If the server isn't authenticated yet,
run `/mcp` first to sign in, then retry.

(c) 2026 Elyon. All rights reserved.
