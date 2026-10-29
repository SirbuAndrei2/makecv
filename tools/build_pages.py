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

Languages: fragments in tools/pages/ro/ and tools/pages/ru/ are Romanian and Russian pages (their path must start
with /ro/ or /ru/). Their header, footer, breadcrumbs, template figures, CTA and ad label come from "pages" and
"templates" in tools/i18n/<lang>.json; HREFLANG pairs equivalent pages across languages (hreflang links + the
EN / RO / RU switcher). After the pages, build_i18n.py generates the /ro and /ru builders from index.html
(skip that with --pages-only).

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
HOME_LASTMOD = "2026-10-29"  # bump when index.html content changes (also the lastmod of /ro and /ru)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_i18n  # noqa: E402
LANGS = ["en"] + build_i18n.LANGS
OG_LOCALE = {"en": "en_US", "ro": "ro_RO", "ru": "ru_RU"}

# Equivalent pages across languages: each group gets reciprocal hreflang links (+ x-default → English) and the
# header's language switcher points at them. Pages outside a group switch to the other language's builder.
HREFLANG = [
    {"en": "/resume-templates", "ro": "/ro/model-cv", "ru": "/ru/shablon-rezyume"},
    {"en": "/how-to-write-a-resume", "ro": "/ro/cum-sa-faci-un-cv", "ru": "/ru/kak-sostavit-rezyume"},
    {"en": "/resume-with-no-experience", "ro": "/ro/cv-fara-experienta", "ru": "/ru/rezyume-bez-opyta"},
    {"en": "/resume-skills", "ro": "/ro/competente-cv", "ru": "/ru/navyki-dlya-rezyume"},
]
HOME = {"en": "/", "ro": "/ro", "ru": "/ru"}

# ── Templates shown on the content pages (keys match TPLS in index.html) ──
TEMPLATES = {
    "professional": {"key": "professional", "name": "Professional", "ats": "Good", "columns": "Main column + light right sidebar",
                     "photo": "Optional, square, top right (nothing shown if you skip it)", "look": "Navy and blue, Source Sans, skill-level dots",
                     "best": "Corporate roles in any industry: sales, operations, HR, finance, project management"},
    "harvard": {"key": "harvard", "name": "Harvard", "ats": "Best", "columns": "One column, Education first",
                "photo": "No photo area", "look": "Black only, Source Serif, centred headings with rules",
                "best": "Students and graduates, finance, consulting, law, academia-adjacent roles"},
    "classic": {"key": "clasic", "name": "Classic", "ats": "Best", "columns": "One column",
                "photo": "Optional, round (nothing shown if you skip it)", "look": "Serif name, blue accents, white page",
                "best": "Accounting, law, teaching, public sector, first jobs"},
    "student": {"key": "student", "name": "Student", "ats": "Best", "columns": "One column, Education and Projects first",
                "photo": "Optional, round (nothing shown if you skip it)", "look": "DM Sans, teal accents, skill tags",
                "best": "Students, graduates, internships, part-time and first jobs"},
    "compact": {"key": "compact", "name": "Compact", "ats": "Best", "columns": "One column, section labels in a left margin",
                "photo": "No photo area", "look": "Dense Inter type, thin rules, blue labels",
                "best": "Experienced candidates who need everything on one page"},
    "minimalist": {"key": "minimalist", "name": "Minimalist", "ats": "Best", "columns": "One column, dates in a left margin",
                   "photo": "No photo area", "look": "Black and white, Playfair Display headings",
                   "best": "Consulting, finance, management, academia-adjacent roles"},
    "executive": {"key": "executive", "name": "Executive", "ats": "Good", "columns": "Main column + narrow right column",
                  "photo": "Optional, above the name (nothing shown if you skip it)", "look": "Garamond serif, gold rules",
                  "best": "Director, VP, C-level, senior legal and finance roles"},
    "swiss": {"key": "swiss", "name": "Swiss", "ats": "Good", "columns": "Main column + narrow right column",
              "photo": "Optional, square (nothing shown if you skip it)", "look": "Inter, black labels, red accents",
              "best": "Product, operations, architecture, design-minded corporate roles"},
    "modern": {"key": "modern", "name": "Modern", "ats": "Fair", "columns": "Dark left sidebar + main column",
               "photo": "Optional, round, in the sidebar (nothing shown if you skip it)", "look": "Navy sidebar, teal accents, skill bars",
               "best": "IT, marketing, sales, startups"},
    "aurora": {"key": "aurora", "name": "Aurora", "ats": "Fair", "columns": "Header + two columns below",
               "photo": "Optional, round (nothing shown if you skip it)", "look": "Gradient edge stripe, colourful skill pills",
               "best": "Marketing, communications, customer success"},
    "creative": {"key": "creativ", "name": "Creative", "ats": "Fair", "columns": "Gradient header + card grid",
                 "photo": "Optional, round, in the header (nothing shown if you skip it)", "look": "Purple-to-cyan gradient, cards",
                 "best": "Design, content, social media, events"},
    "bloom": {"key": "bloom", "name": "Bloom", "ats": "Fair", "columns": "Centred header + two columns",
              "photo": "Optional, round (nothing shown if you skip it)", "look": "Cream page, pink accents, emoji section icons",
              "best": "Early-years education, beauty, hospitality, creative freelancers"},
    "tech": {"key": "tech", "name": "Tech / Dark", "ats": "Fair", "columns": "Main column + right column, dark page",
             "photo": "Optional, square (nothing shown if you skip it)", "look": "Dark navy page, Space Grotesk, blue accents",
             "best": "Software engineering, data, DevOps, game development"},
    "neon": {"key": "neon", "name": "Neon", "ats": "Fair", "columns": "Main column + right column, near-black page",
             "photo": "Optional, square (nothing shown if you skip it)", "look": "Near-black page, cyan and magenta, skill bars",
             "best": "Gaming, creative tech, streaming, music"},
}
TPL_W, TPL_H = 640, 906


def esc(s):
    return html.escape(s, quote=True)


def tpl_figure(slug, eager=False, lang="en"):
    if lang != "en":
        return tpl_figure_i18n(slug, eager, lang)
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


def tpl_card(slug, lang="en"):
    if lang != "en":
        return tpl_card_i18n(slug, lang)
    t = TEMPLATES[slug]
    return f'''<div class="tpl-card-sm">
  <img src="/img/templates/{slug}.jpg" width="{TPL_W}" height="{TPL_H}" loading="lazy" decoding="async" alt="{esc(t['name'])} resume template preview with sample data">
  <div class="tpl-card-body"><div class="tpl-name">{esc(t['name'])} <span class="ats ats-{t['ats'].lower()}">ATS: {t['ats']}</span></div>
  <p>{esc(t['columns'])}. {esc(t['look'])}.</p>
  <a href="/?template={t['key']}">Use {esc(t['name'])} <i class="fa-solid fa-arrow-right" aria-hidden="true"></i></a></div>
</div>'''


def tr_tpl(slug, lang):
    """Template facts in `lang`: tools/i18n/<lang>.json → "templates"[slug] + "ats" labels."""
    d = I18N[lang]
    t = dict(TEMPLATES[slug], **d["templates"][slug])
    t["ats_label"] = d["ats"][TEMPLATES[slug]["ats"]]
    return t


def tpl_figure_i18n(slug, eager, lang):
    t, c = tr_tpl(slug, lang), I18N[lang]["pages"]["tpl"]
    load = 'fetchpriority="high"' if eager else 'loading="lazy" decoding="async"'
    use = f"{HOME[lang]}?template={t['key']}"
    return f'''<figure class="tpl-figure">
  <a href="{use}" class="tpl-shot"><img src="/img/templates/{slug}.jpg" width="{TPL_W}" height="{TPL_H}" {load} alt="{esc(c['alt_fig'].format(name=t['name']))}"></a>
  <figcaption>
    <div class="tpl-name">{esc(t['name'])} <span class="ats ats-{TEMPLATES[slug]['ats'].lower()}">ATS: {esc(t['ats_label'])}</span></div>
    <ul class="tpl-facts"><li><strong>{esc(c['layout'])}:</strong> {esc(t['columns'])}</li><li><strong>{esc(c['photo'])}:</strong> {esc(t['photo'])}</li><li><strong>{esc(c['look'])}:</strong> {esc(t['look'])}</li><li><strong>{esc(c['suits'])}:</strong> {esc(t['best'])}</li></ul>
    <a class="btn-blue" href="{use}">{esc(c['use'].format(name=t['name']))} <i class="fa-solid fa-arrow-right" aria-hidden="true"></i></a>
  </figcaption>
</figure>'''


def tpl_card_i18n(slug, lang):
    t, c = tr_tpl(slug, lang), I18N[lang]["pages"]["tpl"]
    return f'''<div class="tpl-card-sm">
  <img src="/img/templates/{slug}.jpg" width="{TPL_W}" height="{TPL_H}" loading="lazy" decoding="async" alt="{esc(c['alt_card'].format(name=t['name']))}">
  <div class="tpl-card-body"><div class="tpl-name">{esc(t['name'])} <span class="ats ats-{TEMPLATES[slug]['ats'].lower()}">ATS: {esc(t['ats_label'])}</span></div>
  <p>{esc(t['columns'])}. {esc(t['look'])}.</p>
  <a href="{HOME[lang]}?template={t['key']}">{esc(c['use_short'].format(name=t['name']))} <i class="fa-solid fa-arrow-right" aria-hidden="true"></i></a></div>
</div>'''


def cta(lang):
    if lang == "en":
        return CTA
    c = I18N[lang]["pages"]["cta"]
    return f'''<aside class="cta-box">
  <div><div class="cta-title">{esc(c['title'])}</div>
  <p>{esc(c['text'])}</p></div>
  <a class="btn-blue" href="{HOME[lang]}">{esc(c['btn'])} <i class="fa-solid fa-arrow-right" aria-hidden="true"></i></a>
</aside>'''


# style page for each template (the hub links each template to the style page that covers it)
STYLE_OF = {"classic": "simple", "compact": "simple", "minimalist": "minimalist", "executive": "executive",
            "swiss": "minimalist", "modern": "modern", "aurora": "modern", "creative": "creative", "bloom": "creative",
            "tech": "tech", "neon": "tech", "professional": "professional", "harvard": "harvard", "student": "student"}


def slug_page(slug):
    return STYLE_OF[slug]


CTA = '''<aside class="cta-box">
  <div><div class="cta-title">Build your resume now — free, no sign-up</div>
  <p>Fill in your details once, switch between 14 templates, and download a PDF or a text-based ATS PDF. Nothing is uploaded: your resume stays in your browser.</p></div>
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
# Phones only (guide.css hides .ad-lead from 768px, so it never mounts there): right after the lead paragraph, about
# 0.7–1.3 screens down, so phone readers meet an ad before the long article instead of only after it (5–10 screens).
# 40px margins keep it clear of the lead's links and of the first figure's preview link / the contents box.
AD_LEAD = '<aside class="ad-slot ad-lead" data-ad="lead" aria-label="Advertisement"></aside>'
AD_SCRIPT = """<script>
(function () {
  var HOST = 'https://bicea.org', LBL = '@@AD_LABEL@@';
  var Z = { '728x90': { key: '0e7f300ebc75925f1b35d2404c7f5b04', w: 728, h: 90 }, '300x250': { key: '14546d762f4609577c45abcfd23ed569', w: 300, h: 250 } };
  function mount(slot) {
    var z = Z[window.matchMedia('(min-width: 768px)').matches ? '728x90' : '300x250'];
    slot.style.maxWidth = (z.w + 18) + 'px';
    slot.innerHTML = '<span class="ad-slot-label" aria-hidden="true">' + LBL + '</span>';
    var b = document.createElement('div'); b.className = 'ad-slot-body'; b.style.minHeight = z.h + 'px';
    var f = document.createElement('iframe'); f.title = LBL; f.width = z.w; f.height = z.h; f.scrolling = 'no';
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

I18N = {}  # lang → tools/i18n/<lang>.json, loaded in main()
# Content-page chrome. English stays in code (exact current output); ro/ru come from tools/i18n/<lang>.json → "pages".
CHROME_EN = {"skip": "Skip to content", "logo_aria": "MakeCV — Free Resume Builder", "free_pill": "100% Free",
             "build_btn": "Build my resume", "nav_aria": "Main", "nav_aria_m": "Main (mobile)", "lang_aria": "Language",
             "home": "Home", "breadcrumb_aria": "Breadcrumb", "faq_h": "Frequently asked questions",
             "related_h": "Keep reading", "ad": "Advertisement",
             "byline": "By the MakeCV team · Updated {date}"}
CHROME_KEYS = set(CHROME_EN) | {"nav", "foot_text", "foot_cols", "foot_site", "foot_bottom", "months", "date_fmt", "tpl", "cta"}

NAV = [("/resume-templates", "Templates"), ("/how-to-write-a-resume", "How to write"),
       ("/ats-resume", "ATS guide"), ("/resume-vs-cv", "Resume vs CV"), ("/resume-format", "Format")]


def chrome(lang):
    return CHROME_EN if lang == "en" else I18N[lang]["pages"]


def parse(fragment):
    text = fragment.read_text(encoding="utf-8")
    m = re.match(r"\s*<!--meta\s*(\{.*?\})\s*-->\s*", text, re.S)
    if not m:
        sys.exit(f"{fragment}: missing <!--meta {{...}} --> header")
    meta = json.loads(m.group(1))
    meta["body"] = text[m.end():]
    meta["src"] = str(fragment.relative_to(PAGES))
    meta["lang"] = fragment.parent.name if fragment.parent != PAGES else "en"
    if meta["lang"] != "en" and not meta["path"].startswith(f"/{meta['lang']}/"):
        sys.exit(f"{fragment}: a {meta['lang']} page's path must start with /{meta['lang']}/")
    for k in ("path", "title", "description", "h1", "nav_label", "blurb", "updated"):
        if k not in meta:
            sys.exit(f"{fragment}: meta is missing '{k}'")
    return meta


def out_file(path):
    return ROOT / (path.strip("/") + ".html")


def alternates(path):
    """{lang: path} of the pages equivalent to `path` (only pages that exist), or {} if it has none."""
    for g in HREFLANG:
        if path in g.values():
            alt = {l: p for l, p in g.items() if p in BUILT}
            return alt if len(alt) > 1 else {}
    return {}


def header(meta):
    lang = meta["lang"]
    c = chrome(lang)
    nav = NAV if lang == "en" else c["nav"]
    links = "".join(f'<a href="{p}">{esc(l)}</a>' for p, l in nav)
    targets = {**HOME, **alternates(meta["path"]), lang: meta["path"]}
    switch = build_i18n.lang_switcher(lang, targets, c["lang_aria"])
    home = HOME[lang]
    return f'''<a href="#content" class="skip-link">{esc(c["skip"])}</a>
<header class="site-header">
  <div class="bar">
    <a href="{home}" class="logo" aria-label="{esc(c["logo_aria"])}">
      <span class="logo-mark" aria-hidden="true"><i class="fa-solid fa-file-lines"></i></span>
      <span class="logo-text">MakeCV</span>
      <span class="free-pill">{esc(c["free_pill"])}</span>
    </a>
    <nav aria-label="{esc(c["nav_aria"])}" class="main-nav">{links}</nav>
    <div class="hdr-actions">{switch}<a href="{home}" class="btn-blue btn-sm">{esc(c["build_btn"])}</a></div>
  </div>
  <nav aria-label="{esc(c["nav_aria_m"])}" class="mobile-nav">{links}</nav>
</header>'''


def footer_i18n(pages, lang):
    c = chrome(lang)

    def col(title, items):
        lis = "".join(f'<li><a href="{p}">{esc(l)}</a></li>' for p, l in items)
        return f'<nav aria-label="{esc(title)}"><div class="foot-title">{esc(title)}</div><ul>{lis}</ul></nav>' if items else ""
    mine = [p for p in pages if p["lang"] == lang]
    tpl = [(p["path"], p["nav_label"]) for p in mine if p.get("group") == "templates"]
    guides = [(p["path"], p["nav_label"]) for p in mine if p.get("group") == "guides"]
    return f'''<footer class="site-footer">
  <div class="foot-grid">
    <div class="foot-brand">
      <a href="{HOME[lang]}" class="logo"><span class="logo-mark" aria-hidden="true"><i class="fa-solid fa-file-lines"></i></span><span class="logo-text">MakeCV</span></a>
      <p>{esc(c["foot_text"])}</p>
    </div>
    {col(c["foot_cols"]["templates"], tpl)}
    {col(c["foot_cols"]["guides"], guides)}
    {col(c["foot_cols"]["site"], [tuple(x) for x in c["foot_site"]])}
  </div>
  <div class="foot-bottom"><span>{esc(c["foot_bottom"][0])}</span><span>{esc(c["foot_bottom"][1])}</span></div>
</footer>'''


def footer(pages, lang="en"):
    if lang != "en":
        return footer_i18n(pages, lang)
    pages = [p for p in pages if p["lang"] == "en"]
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
    c = chrome(meta["lang"])
    crumbs = meta.get("crumbs") or [[c["home"], HOME[meta["lang"]]], [meta["nav_label"], meta["path"]]]
    items = []
    for i, (name, path) in enumerate(crumbs):
        if i == len(crumbs) - 1:
            items.append(f'<li aria-current="page">{esc(name)}</li>')
        else:
            items.append(f'<li><a href="{path}">{esc(name)}</a></li>')
    visible = f'<nav aria-label="{esc(c["breadcrumb_aria"])}" class="crumbs"><ol>{"".join(items)}</ol></nav>'
    ld = {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": name, "item": SITE + (path if path != "/" else "/")}
        for i, (name, path) in enumerate(crumbs)]}
    return visible, ld


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def render(meta, pages, by_path):
    url = SITE + meta["path"]
    lang = meta["lang"]
    c = chrome(lang)
    body = meta["body"]
    body = re.sub(r"\{\{tpl:(\w+)\}\}", lambda m: tpl_figure(m.group(1), lang=lang), body)
    body = re.sub(r"\{\{tplfirst:(\w+)\}\}", lambda m: tpl_figure(m.group(1), eager=True, lang=lang), body)
    body = re.sub(r"\{\{tplcard:(\w+)\}\}", lambda m: tpl_card(m.group(1), lang=lang), body)
    body = body.replace("{{cta}}", cta(lang))
    crumbs_html, crumbs_ld = breadcrumbs(meta)
    noindex = meta.get("noindex", False)

    image = SITE + meta["image"] if meta.get("image") else f"{SITE}/og-image.png"
    graph = [ORG]
    if not noindex:
        graph.append(crumbs_ld)
        kind = meta.get("schema", "Article")
        main = {"@type": kind, "@id": url + "#main", "url": url, "name": meta["h1"],
                "description": meta["description"], "inLanguage": lang,
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
        faq_html = f'<section class="faq" aria-labelledby="faq-h"><h2 id="faq-h">{esc(c["faq_h"])}</h2><dl>{items}</dl></section>'

    related_html = ""
    rel = [by_path[p] for p in meta.get("related", []) if p in by_path]
    if rel:
        cards = "".join(f'<a class="rel-card" href="{r["path"]}"><span class="rel-title">{esc(r["nav_label"])}</span><span class="rel-blurb">{esc(r["blurb"])}</span></a>' for r in rel)
        related_html = f'<section class="related" aria-labelledby="rel-h"><h2 id="rel-h">{esc(c["related_h"])}</h2><div class="rel-grid">{cards}</div></section>'

    with_ads = not noindex and meta.get("group") in ("templates", "guides")
    if with_ads:
        body, n = re.subn(r'(<p class="lead">.*?</p>)', lambda m: m.group(1) + "\n" + AD_LEAD, body, count=1, flags=re.S)
        if not n:
            sys.exit(f"{meta['src']}: a page with ads needs a <p class=\"lead\"> paragraph (the phone ad goes after it)")
    ad_html = AD_SLOT if with_ads else ""
    ad_script = AD_SCRIPT.replace("@@AD_LABEL@@", c["ad"].replace("'", "\\'")) if with_ads else ""
    updated_h = meta["updated"]
    robots = "noindex, follow" if noindex else "index, follow, max-image-preview:large, max-snippet:-1"
    canonical = "" if noindex else f'<link rel="canonical" href="{url}">\n'
    og_type = "article" if meta.get("schema", "Article") == "Article" else "website"
    byline = "" if meta.get("no_byline") else '<p class="byline">' + esc(c["byline"]).replace(
        "{date}", f'<time datetime="{updated_h}">{pretty_date(updated_h, lang)}</time>') + '</p>'
    alt = alternates(meta["path"]) if not noindex else {}
    hreflang = "".join(f'<link rel="alternate" hreflang="{l}" href="{SITE}{alt[l]}">\n' for l in LANGS if l in alt)
    if "en" in alt:
        hreflang += f'<link rel="alternate" hreflang="x-default" href="{SITE}{alt["en"]}">\n'

    return f'''<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(meta["title"])}</title>
<meta name="description" content="{esc(meta["description"])}">
<meta name="robots" content="{robots}">
{canonical}{hreflang}<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="apple-touch-icon" href="/logo.png">
<meta name="theme-color" content="#2563eb">
<meta property="og:type" content="{og_type}">
<meta property="og:url" content="{url}">
<meta property="og:title" content="{esc(meta["title"])}">
<meta property="og:description" content="{esc(meta["description"])}">
<meta property="og:image" content="{image}">
<meta property="og:site_name" content="MakeCV">
<meta property="og:locale" content="{OG_LOCALE[lang]}">
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
{header(meta)}
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
{footer(pages, lang)}
{ad_script}
</body>
</html>
'''


def pretty_date(iso, lang="en"):
    y, m, d = iso.split("-")
    if lang != "en":
        c = chrome(lang)
        return c["date_fmt"].format(d=int(d), m=c["months"][int(m) - 1], y=y)
    months = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
              "October", "November", "December"]
    return f"{months[int(m) - 1]} {int(d)}, {y}"


def sitemap(pages):
    rows = [f"  <url>\n    <loc>{SITE}{HOME[l] if l != 'en' else '/'}</loc>\n    <lastmod>{HOME_LASTMOD}</lastmod>\n  </url>" for l in LANGS]
    for p in pages:
        if p.get("noindex"):
            continue
        rows.append(f"  <url>\n    <loc>{SITE}{p['path']}</loc>\n    <lastmod>{p['updated']}</lastmod>\n  </url>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(rows) + "\n</urlset>\n")


BUILT = set()


def main(argv):
    for lang in build_i18n.LANGS:
        I18N[lang] = build_i18n.load(lang)
        miss = CHROME_KEYS - set(I18N[lang].get("pages", {}))
        if miss:
            sys.exit(f"tools/i18n/{lang}.json: \"pages\" is missing {sorted(miss)}")
        miss = [s for s in TEMPLATES if s not in I18N[lang].get("templates", {})]
        if miss or set(I18N[lang].get("ats", {})) != {"Best", "Good", "Fair"}:
            sys.exit(f"tools/i18n/{lang}.json: \"templates\" needs every slug ({miss}) and \"ats\" Best/Good/Fair")
    pages = [parse(f) for f in sorted(PAGES.rglob("*.html"))]
    BUILT.update(p["path"] for p in pages)
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
    for g in HREFLANG:
        gone = [p for p in g.values() if p not in BUILT]
        if gone:
            print(f"note: HREFLANG lists pages that do not exist yet: {gone}")
    for p in pages:
        f = out_file(p["path"])
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(render(p, pages, by_path), encoding="utf-8")
        print(f"wrote {f.relative_to(ROOT)}  ({p['path']})")
    (ROOT / "sitemap.xml").write_text(sitemap(pages), encoding="utf-8")
    print(f"wrote sitemap.xml ({len(LANGS) + sum(1 for p in pages if not p.get('noindex'))} URLs)")
    if "--pages-only" not in argv:
        build_i18n.main([])


if __name__ == "__main__":
    main(sys.argv[1:])
