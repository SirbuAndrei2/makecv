#!/usr/bin/env python3
"""Build MakeCV's static content pages and sitemap.xml.

The builder itself is index.html (hand-edited, not generated). Every other page is
generated from a fragment in tools/pages/*.html so header, footer, GA snippet,
JSON-LD and the sitemap stay consistent:

    python3 tools/build_pages.py

Each fragment starts with a JSON block in an HTML comment, then the article body:

    <!--meta
    {"path": "/ats-resume", "title": "...", "description": "...", "h1": "...", ...}
    -->
    <p>Body HTML…</p>

Placeholders usable in the body:
    {{tpl:classic}}        figure with the template preview + "Use this template" link
    {{tplcard:classic}}    compact card (image + name + facts) for grids
    {{cta}}                "Build your resume" call-to-action box

Output path follows Cloudflare's html_handling "drop-trailing-slash": the page for
/resume-templates/modern is written to resume-templates/modern.html. Canonicals and
sitemap URLs use the served form (no .html, no trailing slash).

Python 3 standard library only. No network access.
"""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "tools" / "pages"
SITE = "https://makecv.org"
HOME_LASTMOD = "2026-10-27"  # bump when index.html content changes

# ── Templates shown on the content pages (keys match TPLS in index.html) ──
TEMPLATES = {
    "classic": {"key": "clasic", "name": "Classic", "ats": "Best", "columns": "One column",
                "photo": "Round photo (placeholder icon if none)", "look": "Serif name, blue accents, white page",
                "best": "Accounting, law, teaching, public sector, first jobs"},
    "minimalist": {"key": "minimalist", "name": "Minimalist", "ats": "Best", "columns": "One column, dates in a left margin",
                   "photo": "No photo area", "look": "Black and white, Playfair Display headings",
                   "best": "Consulting, finance, management, academia-adjacent roles"},
    "executive": {"key": "executive", "name": "Executive", "ats": "Good", "columns": "Main column + narrow right column",
                  "photo": "Only if you upload one", "look": "Garamond serif, gold rules",
                  "best": "Director, VP, C-level, senior legal and finance roles"},
    "swiss": {"key": "swiss", "name": "Swiss", "ats": "Good", "columns": "Main column + narrow right column",
              "photo": "Square photo (placeholder icon if none)", "look": "Inter, black labels, red accents",
              "best": "Product, operations, architecture, design-minded corporate roles"},
    "modern": {"key": "modern", "name": "Modern", "ats": "Fair", "columns": "Dark left sidebar + main column",
               "photo": "Round photo in sidebar (placeholder icon if none)", "look": "Navy sidebar, teal accents, skill bars",
               "best": "IT, marketing, sales, startups"},
    "aurora": {"key": "aurora", "name": "Aurora", "ats": "Fair", "columns": "Header + two columns below",
               "photo": "Round photo (placeholder icon if none)", "look": "Gradient edge stripe, colourful skill pills",
               "best": "Marketing, communications, customer success"},
    "creative": {"key": "creativ", "name": "Creative", "ats": "Fair", "columns": "Gradient header + card grid",
                 "photo": "Round photo in header (placeholder icon if none)", "look": "Purple-to-cyan gradient, cards",
                 "best": "Design, content, social media, events"},
    "bloom": {"key": "bloom", "name": "Bloom", "ats": "Fair", "columns": "Centred header + two columns",
              "photo": "Round photo (flower placeholder if none)", "look": "Cream page, pink accents, emoji section icons",
              "best": "Early-years education, beauty, hospitality, creative freelancers"},
    "tech": {"key": "tech", "name": "Tech / Dark", "ats": "Fair", "columns": "Main column + right column, dark page",
             "photo": "Square photo (placeholder icon if none)", "look": "Dark navy page, Space Grotesk, blue accents",
             "best": "Software engineering, data, DevOps, game development"},
    "neon": {"key": "neon", "name": "Neon", "ats": "Fair", "columns": "Main column + right column, near-black page",
             "photo": "Square photo (placeholder icon if none)", "look": "Near-black page, cyan and magenta, skill bars",
             "best": "Gaming, creative tech, streaming, music"},
}
TPL_W, TPL_H = 640, 906


def esc(s):
    return html.escape(s, quote=True)


def tpl_figure(slug, eager=False):
    t = TEMPLATES[slug]
    load = 'fetchpriority="high"' if eager else 'loading="lazy" decoding="async"'
    return f'''<figure class="tpl-figure">
  <a href="/resume-templates/{slug_page(slug)}" class="tpl-shot"><img src="/img/templates/{slug}.jpg" width="{TPL_W}" height="{TPL_H}" {load} alt="{esc(t['name'])} resume template filled with a sample product marketing manager resume"></a>
  <figcaption>
    <div class="tpl-name">{esc(t['name'])} <span class="ats ats-{t['ats'].lower()}">ATS: {t['ats']}</span></div>
    <ul class="tpl-facts"><li><strong>Layout:</strong> {esc(t['columns'])}</li><li><strong>Photo:</strong> {esc(t['photo'])}</li><li><strong>Look:</strong> {esc(t['look'])}</li><li><strong>Suits:</strong> {esc(t['best'])}</li></ul>
    <a class="btn-blue" href="/?template={t['key']}">Use the {esc(t['name'])} template <i class="fa-solid fa-arrow-right" aria-hidden="true"></i></a>
  </figcaption>
</figure>'''


def tpl_card(slug):
    t = TEMPLATES[slug]
    return f'''<div class="tpl-card-sm">
  <img src="/img/templates/{slug}.jpg" width="{TPL_W}" height="{TPL_H}" loading="lazy" decoding="async" alt="{esc(t['name'])} resume template preview with sample data">
  <div class="tpl-card-body"><div class="tpl-name">{esc(t['name'])} <span class="ats ats-{t['ats'].lower()}">ATS: {t['ats']}</span></div>
  <p>{esc(t['columns'])}. {esc(t['look'])}.</p>
  <a href="/?template={t['key']}">Use {esc(t['name'])} <i class="fa-solid fa-arrow-right" aria-hidden="true"></i></a></div>
</div>'''


# style page for each template (the hub links each template to the style page that covers it)
STYLE_OF = {"classic": "simple", "minimalist": "minimalist", "executive": "executive", "swiss": "minimalist",
            "modern": "modern", "aurora": "modern", "creative": "creative", "bloom": "creative",
            "tech": "tech", "neon": "tech"}


def slug_page(slug):
    return STYLE_OF[slug]


CTA = '''<aside class="cta-box">
  <div><div class="cta-title">Build your resume now — free, no sign-up</div>
  <p>Fill in your details once, switch between 10 templates, and download a PDF or a text-based ATS PDF. Nothing is uploaded: your resume stays in your browser.</p></div>
  <a class="btn-blue" href="/">Open the resume builder <i class="fa-solid fa-arrow-right" aria-hidden="true"></i></a>
</aside>'''

GA = """<!-- Google Analytics 4 — same snippet as index.html; runs only on makecv.org.
     Consent Mode v2: storage denied by default in the EEA/UK/CH, granted elsewhere; a stored cookie-banner choice overrides it. -->
<script>
(function () {
  var GA_ID = 'G-WF9MGRZJ3Z';
  if (!GA_ID || location.hostname !== 'makecv.org') return;
  var GRANTED = { ad_storage: 'granted', ad_user_data: 'granted', ad_personalization: 'granted', analytics_storage: 'granted' };
  var DENIED = { ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied', analytics_storage: 'denied' };
  window.dataLayer = window.dataLayer || [];
  window.gtag = function () { dataLayer.push(arguments); };
  gtag('consent', 'default', Object.assign({}, DENIED, { region: ['AT','BE','BG','HR','CY','CZ','DK','EE','FI','FR','DE','GR','HU','IS','IE','IT','LV','LI','LT','LU','MT','NL','NO','PL','PT','RO','SK','SI','ES','SE','GB','CH'] }));
  gtag('consent', 'default', GRANTED);
  try { var c = localStorage.getItem('makecv_cookie_consent'); if (c === 'accepted') gtag('consent', 'update', GRANTED); if (c === 'declined') gtag('consent', 'update', DENIED); } catch (e) {}
  gtag('js', new Date());
  gtag('config', GA_ID);
  var s = document.createElement('script'); s.async = true; s.src = 'https://www.googletagmanager.com/gtag/js?id=' + GA_ID;
  document.head.appendChild(s);
  window.makecvConsent = function (accepted) { gtag('consent', 'update', accepted ? GRANTED : DENIED); };
})();
</script>"""

# One in-content Adsterra banner per template/guide page, between the article and the FAQ (a natural break,
# never inside the text or next to a "Use this template" button). Same zone keys and srcdoc-iframe approach as
# index.html's ADS script; mounted lazily when it comes within 300px of the viewport. No social bar, no popunder.
AD_SLOT = '<aside class="ad-slot" data-ad="incontent" aria-label="Advertisement"></aside>'
AD_SCRIPT = """<script>
(function () {
  var HOST = 'https://bicea.org';
  var Z = { '728x90': { key: '0e7f300ebc75925f1b35d2404c7f5b04', w: 728, h: 90 }, '300x250': { key: '14546d762f4609577c45abcfd23ed569', w: 300, h: 250 } };
  function mount(slot) {
    var z = Z[window.matchMedia('(min-width: 768px)').matches ? '728x90' : '300x250'];
    slot.style.maxWidth = (z.w + 18) + 'px';
    slot.innerHTML = '<span class="ad-slot-label" aria-hidden="true">Advertisement</span>';
    var b = document.createElement('div'); b.className = 'ad-slot-body'; b.style.minHeight = z.h + 'px';
    var f = document.createElement('iframe'); f.title = 'Advertisement'; f.width = z.w; f.height = z.h; f.scrolling = 'no';
    f.srcdoc = '<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;padding:0;background:transparent;overflow:hidden}</style></head><body>'
      + "<script>atOptions={key:'" + z.key + "',format:'iframe',height:" + z.h + ',width:' + z.w + ',params:{}}<\\/script>'
      + '<script src="' + HOST + '/22/' + z.key + '"><\\/script></body></html>';
    b.appendChild(f); slot.appendChild(b);
  }
  var slots = document.querySelectorAll('aside[data-ad]');
  if (!('IntersectionObserver' in window)) { slots.forEach(mount); return; }
  var io = new IntersectionObserver(function (en) { en.forEach(function (x) { if (x.isIntersecting) { io.unobserve(x.target); mount(x.target); } }); }, { rootMargin: '300px 0px' });
  slots.forEach(function (s) { io.observe(s); });
})();
</script>"""

ORG = {"@type": "Organization", "@id": f"{SITE}/#organization", "name": "MakeCV", "url": f"{SITE}/",
       "logo": {"@type": "ImageObject", "url": f"{SITE}/logo.png", "width": 512, "height": 512}}

NAV = [("/resume-templates", "Templates"), ("/how-to-write-a-resume", "How to write"),
       ("/ats-resume", "ATS guide"), ("/resume-vs-cv", "Resume vs CV"), ("/resume-format", "Format")]


def parse(fragment):
    text = fragment.read_text(encoding="utf-8")
    m = re.match(r"\s*<!--meta\s*(\{.*?\})\s*-->\s*", text, re.S)
    if not m:
        sys.exit(f"{fragment}: missing <!--meta {{...}} --> header")
    meta = json.loads(m.group(1))
    meta["body"] = text[m.end():]
    meta["src"] = fragment.name
    for k in ("path", "title", "description", "h1", "nav_label", "blurb", "updated"):
        if k not in meta:
            sys.exit(f"{fragment}: meta is missing '{k}'")
    return meta


def out_file(path):
    return ROOT / (path.strip("/") + ".html")


def header():
    links = "".join(f'<a href="{p}">{l}</a>' for p, l in NAV)
    mlinks = "".join(f'<a href="{p}">{l}</a>' for p, l in NAV)
    return f'''<a href="#content" class="skip-link">Skip to content</a>
<header class="site-header">
  <div class="bar">
    <a href="/" class="logo" aria-label="MakeCV — Free Resume Builder">
      <span class="logo-mark" aria-hidden="true"><i class="fa-solid fa-file-lines"></i></span>
      <span class="logo-text">MakeCV</span>
      <span class="free-pill">100% Free</span>
    </a>
    <nav aria-label="Main" class="main-nav">{links}</nav>
    <a href="/" class="btn-blue btn-sm">Build my resume</a>
  </div>
  <nav aria-label="Main (mobile)" class="mobile-nav">{mlinks}</nav>
</header>'''


def footer(pages):
    def col(title, items):
        lis = "".join(f'<li><a href="{p}">{esc(l)}</a></li>' for p, l in items)
        return f'<nav aria-label="{title}"><div class="foot-title">{title}</div><ul>{lis}</ul></nav>'
    tpl = [(p["path"], p["nav_label"]) for p in pages if p.get("group") == "templates"]
    guides = [(p["path"], p["nav_label"]) for p in pages if p.get("group") == "guides"]
    site = [("/", "Free resume builder")] + [(p["path"], p["nav_label"]) for p in pages if p.get("group") == "site"]
    return f'''<footer class="site-footer">
  <div class="foot-grid">
    <div class="foot-brand">
      <a href="/" class="logo"><span class="logo-mark" aria-hidden="true"><i class="fa-solid fa-file-lines"></i></span><span class="logo-text">MakeCV</span></a>
      <p>Free resume builder: no sign-up, no watermark, instant PDF. Your resume never leaves your browser.</p>
    </div>
    {col("Resume templates", tpl)}
    {col("Guides", guides)}
    {col("MakeCV", site)}
  </div>
  <div class="foot-bottom"><span>© 2026 MakeCV</span><span>No sign-up · No watermark · Data stays in your browser</span></div>
</footer>'''


def breadcrumbs(meta):
    crumbs = meta.get("crumbs") or [["Home", "/"], [meta["nav_label"], meta["path"]]]
    items = []
    for i, (name, path) in enumerate(crumbs):
        if i == len(crumbs) - 1:
            items.append(f'<li aria-current="page">{esc(name)}</li>')
        else:
            items.append(f'<li><a href="{path}">{esc(name)}</a></li>')
    visible = f'<nav aria-label="Breadcrumb" class="crumbs"><ol>{"".join(items)}</ol></nav>'
    ld = {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": name, "item": SITE + (path if path != "/" else "/")}
        for i, (name, path) in enumerate(crumbs)]}
    return visible, ld


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def render(meta, pages, by_path):
    url = SITE + meta["path"]
    body = meta["body"]
    body = re.sub(r"\{\{tpl:(\w+)\}\}", lambda m: tpl_figure(m.group(1)), body)
    body = re.sub(r"\{\{tplfirst:(\w+)\}\}", lambda m: tpl_figure(m.group(1), eager=True), body)
    body = re.sub(r"\{\{tplcard:(\w+)\}\}", lambda m: tpl_card(m.group(1)), body)
    body = body.replace("{{cta}}", CTA)
    crumbs_html, crumbs_ld = breadcrumbs(meta)
    noindex = meta.get("noindex", False)

    image = SITE + meta["image"] if meta.get("image") else f"{SITE}/og-image.png"
    graph = [ORG]
    if not noindex:
        graph.append(crumbs_ld)
        kind = meta.get("schema", "Article")
        main = {"@type": kind, "@id": url + "#main", "url": url, "name": meta["h1"],
                "description": meta["description"], "inLanguage": "en",
                "isPartOf": {"@type": "WebSite", "@id": f"{SITE}/#website", "name": "MakeCV", "url": f"{SITE}/"},
                "dateModified": meta["updated"], "primaryImageOfPage": {"@type": "ImageObject", "url": image}}
        if kind == "Article":
            main.update({"headline": meta["h1"], "image": image, "datePublished": meta.get("published", meta["updated"]),
                         "author": {"@id": f"{SITE}/#organization"}, "publisher": {"@id": f"{SITE}/#organization"},
                         "mainEntityOfPage": url})
        if meta.get("itemlist"):
            main["mainEntity"] = {"@type": "ItemList", "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "name": name, "url": SITE + path}
                for i, (name, path) in enumerate(meta["itemlist"])]}
        graph.append(main)
        if meta.get("faq"):
            graph.append({"@type": "FAQPage", "mainEntity": [
                {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": strip_tags(a)}}
                for q, a in meta["faq"]]})
    ld = json.dumps({"@context": "https://schema.org", "@graph": graph}, indent=1, ensure_ascii=False)

    faq_html = ""
    if meta.get("faq"):
        items = "".join(f'<div class="faq-item"><dt>{esc(q)}</dt><dd>{a}</dd></div>' for q, a in meta["faq"])
        faq_html = f'<section class="faq" aria-labelledby="faq-h"><h2 id="faq-h">Frequently asked questions</h2><dl>{items}</dl></section>'

    related_html = ""
    rel = [by_path[p] for p in meta.get("related", []) if p in by_path]
    if rel:
        cards = "".join(f'<a class="rel-card" href="{r["path"]}"><span class="rel-title">{esc(r["nav_label"])}</span><span class="rel-blurb">{esc(r["blurb"])}</span></a>' for r in rel)
        related_html = f'<section class="related" aria-labelledby="rel-h"><h2 id="rel-h">Keep reading</h2><div class="rel-grid">{cards}</div></section>'

    with_ads = not noindex and meta.get("group") in ("templates", "guides")
    ad_html = AD_SLOT if with_ads else ""
    ad_script = AD_SCRIPT if with_ads else ""
    updated_h = meta["updated"]
    robots = "noindex, follow" if noindex else "index, follow, max-image-preview:large, max-snippet:-1"
    canonical = "" if noindex else f'<link rel="canonical" href="{url}">\n'
    og_type = "article" if meta.get("schema", "Article") == "Article" else "website"
    byline = "" if meta.get("no_byline") else f'<p class="byline">By the MakeCV team · Updated <time datetime="{updated_h}">{pretty_date(updated_h)}</time></p>'

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(meta["title"])}</title>
<meta name="description" content="{esc(meta["description"])}">
<meta name="robots" content="{robots}">
{canonical}<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="apple-touch-icon" href="/logo.png">
<meta name="theme-color" content="#2563eb">
<meta property="og:type" content="{og_type}">
<meta property="og:url" content="{url}">
<meta property="og:title" content="{esc(meta["title"])}">
<meta property="og:description" content="{esc(meta["description"])}">
<meta property="og:image" content="{image}">
<meta property="og:site_name" content="MakeCV">
<meta property="og:locale" content="en_US">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(meta["title"])}">
<meta name="twitter:description" content="{esc(meta["description"])}">
<meta name="twitter:image" content="{image}">
<script type="application/ld+json">
{ld}
</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
{GA}
<script src="https://cdn.tailwindcss.com"></script>
<link rel="stylesheet" href="/guide.css">
</head>
<body>
<!-- Generated by tools/build_pages.py from tools/pages/{meta["src"]} — edit the fragment, not this file. -->
{header()}
<main class="guide" id="content">
{crumbs_html}
<article>
<h1>{esc(meta["h1"])}</h1>
{byline}
{body}
</article>
{ad_html}
{faq_html}
{related_html if not noindex else ""}
</main>
{footer(pages)}
{ad_script}
</body>
</html>
'''


def pretty_date(iso):
    y, m, d = iso.split("-")
    months = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
              "October", "November", "December"]
    return f"{months[int(m) - 1]} {int(d)}, {y}"


def sitemap(pages):
    rows = [f"  <url>\n    <loc>{SITE}/</loc>\n    <lastmod>{HOME_LASTMOD}</lastmod>\n  </url>"]
    for p in pages:
        if p.get("noindex"):
            continue
        rows.append(f"  <url>\n    <loc>{SITE}{p['path']}</loc>\n    <lastmod>{p['updated']}</lastmod>\n  </url>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(rows) + "\n</urlset>\n")


def main():
    pages = [parse(f) for f in sorted(PAGES.glob("*.html"))]
    order = {"templates": 0, "guides": 1, "site": 2}
    pages.sort(key=lambda p: (order.get(p.get("group"), 3), p.get("order", 50), p["path"]))
    by_path = {p["path"]: p for p in pages}
    seen = {}
    for p in pages:
        for k in ("title", "description", "h1"):
            if p[k] in seen.get(k, {}):
                sys.exit(f"duplicate {k}: {p['path']} and {seen[k][p[k]]}")
            seen.setdefault(k, {})[p[k]] = p["path"]
        for r in p.get("related", []):
            if r not in by_path:
                sys.exit(f"{p['path']}: related link to unknown page {r}")
    for p in pages:
        f = out_file(p["path"])
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(render(p, pages, by_path), encoding="utf-8")
        print(f"wrote {f.relative_to(ROOT)}  ({p['path']})")
    (ROOT / "sitemap.xml").write_text(sitemap(pages), encoding="utf-8")
    print(f"wrote sitemap.xml ({1 + sum(1 for p in pages if not p.get('noindex'))} URLs)")


if __name__ == "__main__":
    main()
