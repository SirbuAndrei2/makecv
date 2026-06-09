# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MakeCV (makecv.org) is a **single-file, zero-build static resume builder**. The entire application — HTML, CSS, JavaScript, all 10 CV templates, and all UI — lives in `index.html` (≈2070 lines). There is no package manager, no bundler, no framework, and no build step.

## Running / Developing

Open `index.html` directly in a browser, or serve it locally:

```bash
npx serve .          # or: python3 -m http.server 8080
```

Deploy via Vercel — `vercel.json` handles routing (cleanUrls, security headers). No CI configuration exists.

## Architecture

### Single-file structure (index.html)

| Section | Lines (approx) | Description |
|---|---|---|
| `<head>` | 1–230 | Meta, SEO, JSON-LD schemas, ads scripts |
| `<style>` | ~230–760 | All CSS — Tailwind via CDN + custom per-template styles |
| Ad tags | ~753–760 | Monetag push/vignette zones |
| `<body>` HTML | ~766–1268 | Header, 3-step wizard UI, footer |
| `<script>` | ~1270–1991 | All app logic |
| Cookie / Privacy | ~1993–2070 | Cookie consent banner, privacy modal |

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

- **Google AdSense** — placeholder `ca-pub-XXXXXXXXXXXXXXXX` in head; replace with real publisher ID
- **Adsterra** — placeholder `YOUR_ADSTERRA_POPUNDER_KEY` in head
- **Monetag** — zones 11090465 (push, via sw.js) and 11090485 (vignette)
- `sw.js` — Monetag push notification service worker; references zone 11090465
- `ads.txt` — contains placeholder AdSense publisher ID; update when activating AdSense

### SEO / Structured data

Head contains JSON-LD for: `WebApplication`, `FAQPage`, `HowTo`, `Organization`, `BreadcrumbList`. Update `lastmod` in `sitemap.xml` on content changes.
