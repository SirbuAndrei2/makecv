# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MakeCV (makecv.org) is a **single-file, zero-build static resume builder**. The entire application — HTML, CSS, JavaScript, all 10 CV templates, and all UI — lives in `index.html` (≈2070 lines). There is no package manager, no bundler, no framework, and no build step.

## Running / Developing

Open `index.html` directly in a browser, or serve it locally:

```bash
npx serve .          # or: python3 -m http.server 8080
```

Hosted on Cloudflare Workers (static assets only, `wrangler.jsonc`; the repo root is the asset directory and `.assetsignore` excludes docs/config). Security and cache headers live in `_headers`. Deploy with `npx wrangler deploy` (or `./sw deploy makecv` from the workspace root): **Workers Builds is not connected** to this Worker, so a push to `main` does not deploy (verified 2026-10-27). `makecv.org` is a Workers custom domain since 2026-10-27; the old Vercel CNAME and `_vercel` TXT records were deleted. `www.makecv.org` → apex is a separate Worker in `www-redirect/` (`npx wrangler deploy -c www-redirect/wrangler.jsonc`).

## Architecture

### Single-file structure (index.html)

| Section | Lines (approx) | Description |
|---|---|---|
| `<head>` | 1–230 | Meta, SEO, JSON-LD schemas, ads scripts |
| `<style>` | ~230–760 | All CSS — Tailwind via CDN + custom per-template styles |
| `<body>` HTML | ~766–1268 | Header, 3-step wizard UI, footer |
| `<script>` | ~1270–1991 | All app logic |
| Cookie / Privacy | end of file | Cookie consent banner, privacy modal (its script waits for DOMContentLoaded: the markup comes after it) |

### External dependencies (CDN only — no npm)
- **Tailwind CSS** — utility classes in the HTML
- **Font Awesome** — icons
- **html2pdf.js** — client-side PDF generation via html2canvas + jsPDF

### App state

All state lives in a single in-memory `cv` object:

```js
cv = {
  personal: { name, title, email, phone, city, linkedin, website, photo },
  summary: '',
  experience: [],   // max 5
  education: [],    // max 3
  skills: [],       // { name, level: 'Începător'|'Mediu'|'Avansat' }
  languages: [],    // max 4
  projects: [],     // max 3
  certifications: [],// max 4
  selectedTemplate: 'modern'
}
```

No localStorage persistence (except cookie consent in `makecv_cookie_consent`). Refresh clears all data.

### Key functions

- `upd(path, val)` — dot-path state updater, triggers `renderCV()` if on step 3
- `updEntry(type, idx, field, val)` — updates a repeatable list entry
- `renderCV()` — writes `TPLS[cv.selectedTemplate](cv)` into `#cv-preview`
- `goStep(n)` — shows step n, hides others; step 3 triggers renderCV + scale
- `selTpl(name)` — sets `cv.selectedTemplate`, highlights template card
- `applyScale()` — CSS-transforms the preview to fit the viewport
- `downloadPDF()` — async; resets transform to scale(1) before html2pdf capture, then restores
- `e(s)` — HTML escape helper; **must be used on all user-supplied content rendered into templates**
- `barW(lvl)` — maps Romanian skill levels to progress bar widths (32/62/92%)

### Templates

The `TPLS` object maps 10 template keys to functions `(cv) => htmlString`:

`clasic`, `modern`, `minimalist`, `creativ`, `executive`, `tech`, `bloom`, `neon`, `aurora`, `swiss`

Each template function renders directly from the `cv` state object. Templates contain their own layout CSS under `.tpl-<name>` classes in the `<style>` block.

**Important**: Template section headings are in Romanian (`Experiență profesională`, `Educație`, `Abilități`, etc.). Skill levels are stored as Romanian strings (`'Mediu'`, `'Avansat'`, `'Începător'`) — `barW()` depends on these exact strings.

### Ads

**Adsterra only** (there is no AdSense). Slots are `<aside class="ad-slot" data-ad="…">` placeholders in the HTML; the ADS script at the end of `<body>` fills each one when it first comes within 300px of the viewport (IntersectionObserver), so slots in hidden steps or `lg:hidden` variants never request an ad. Keys and zones live in that script's `BANNERS` / constants.

| `data-ad` | Size | Where |
|---|---|---|
| `leaderboard` | 728×90, 320×50 below 768px | Step 1, under the hero |
| `inline` | 468×60, 320×50 below 768px | Step 1, before Languages |
| `native` | /21/ native banner (`#container-<zone>`, one per page) | Step 2, under the template grid |
| `300x250` | 300×250 | Step 3: left panel from 1024px (panel widens to `lg:w-80`), under the preview below 1024px |
| `responsive` | 728×90, 300×250 below 768px | Between How it works and the FAQ |
| `rail-left` / `rail-right` | 160×600 / 160×300 | Fixed beside the active step, only when they fit (`placeRails`, re-run on `goStep` and resize) |

- Iframe banners (/22/) each render in their own `srcdoc` iframe: the invoke script reads the global `atOptions` and uses `document.write`.
- **Social Bar** (/14/) loads 1.5 s after `load`, every page view.
- **Popunder** (/1/, afders.org) loads only after the visitor gets a PDF (`makecv:downloaded`, fired by `downloadPDF()` and `printATS()`), once per session (`sessionStorage.makecv_pu`). It binds a page-wide click handler, so loading it earlier hijacks clicks in the form.
- **Direct link** (arwf.org): the `a[data-ad-link]` "Sponsored" cards in step 3 (`rel="sponsored"`, new tab).
- `@media print` hides `body > *`, so no ad reaches the ATS print.
- `sw.js` is a kill switch for an old third-party push service worker removed on 2026-10-27: browsers that registered it keep re-fetching the file, and this version unregisters itself (dropping the push subscription) and reloads open tabs. It is served `no-cache`. Delete `sw.js` and its `_headers` entry after 2026-11-26.
- The cookie banner and privacy policy (modal) describe Adsterra; `ads.txt` lists no sellers (no AdSense).

### Analytics

Google Analytics 4: inline script at the top of `<head>` (`GA_ID`, empty = no tag; only runs on the `makecv.org` hostname). Consent Mode v2 denies storage by default in the EEA/UK/CH and grants it elsewhere; `acceptCookies()` / `declineCookies()` call `makecvConsent()` to update it, and a stored choice is applied on every load.

### SEO / Structured data

Head contains JSON-LD for: `WebApplication`, `FAQPage`, `HowTo`, `Organization`, `BreadcrumbList`. Update `lastmod` in `sitemap.xml` on content changes.
