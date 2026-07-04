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

(c) 2026 Elyon. All rights reserved.
