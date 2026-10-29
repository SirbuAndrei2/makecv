#!/usr/bin/env python3
"""Generate the Romanian and Russian builders (ro/index.html, ru/index.html) from index.html.

index.html stays the single source of truth; this script never edits it. For each language in LANGS it reads
tools/i18n/<lang>.json and tools/i18n/<lang>/<block>.html and writes <lang>/index.html, served at /<lang>.

    python3 tools/build_i18n.py               # build every language (build_pages.py also calls this)
    python3 tools/build_i18n.py --missing ro  # print what ro still lacks, as JSON ready to paste into ro.json

How index.html is translated (the build fails on anything it cannot translate, so nothing silently stays English):

1. Text. Every visible text run outside <script>/<style> is a translation unit: a stretch of text plus inline
   markup (<a>, <strong>, <b>, <em>, <code>, <br>…) between two other tags. Its key is the English HTML with
   whitespace collapsed; tools/i18n/<lang>.json → "strings" maps it to the translation. A translation must keep
   the same tags (any order), so links and <strong> survive. Units with no letter ("*", "★★★★★", "1") are skipped.
2. Attributes. alt, title, placeholder, aria-label, data-tip, and the content of the description / Open Graph /
   Twitter <meta> tags are units too (same "strings" table, key = the raw attribute value).
3. Script strings. Every user-facing string of the app script lives in the `L` object, strict JSON between the
   /*i18n:js*/ … /*/i18n:js*/ markers. "js" in the language file must have exactly the same keys; plural objects
   ({"one": …, "other": …}) must have the language's Intl.PluralRules categories instead (ro: one/few/other,
   ru: one/few/many/other).
4. Blocks. <!--i18n:block NAME--> … <!--/i18n:block--> marks markup that is replaced as a whole, because the
   content is local rather than translated (FAQ, guide links, footer links) or dropped (the English-only reviews
   and counters). tools/i18n/<lang>/<NAME>.html holds the replacement; its first line, <!--src:HASH-->, records
   the hash of the English block it was written against, so editing the English block fails the build until
   each language is reviewed and the hash updated (the error prints the new one). "lang-sw" is generated here.
5. JSON-LD. name/description/text/featureList… values go through "strings" as plain text; inLanguage, the
   WebApplication url/@id are localised; the FAQPage is rebuilt from the visible FAQ block (word for word).
6. Links. Every root-relative href must be in "hrefs" (English path → page to link from this language), or
   already be a /<lang>/ path, or point at a static file. Canonical, og:url, og:locale and <html lang> are set.

Python 3 standard library only. No network access.
"""
import hashlib
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
I18N = ROOT / "tools" / "i18n"
SITE = "https://makecv.org"
LANGS = ["ro", "ru"]
LANG_NAMES = {"en": "English", "ro": "Română", "ru": "Русский"}
PLURALS = {"en": {"one", "other"}, "ro": {"one", "few", "other"}, "ru": {"one", "few", "many", "other"}}
PLURAL_KEYS = {"zero", "one", "two", "few", "many", "other"}

INLINE = {"a", "strong", "b", "em", "code", "kbd", "br", "small", "abbr", "sup", "sub"}
ATTRS = {"alt", "title", "placeholder", "aria-label", "data-tip"}
META_KEYS = {"description", "og:title", "og:description", "og:image:alt", "twitter:title", "twitter:description",
             "twitter:image:alt"}
LD_KEYS = {"name", "alternateName", "description", "text", "applicationSubCategory", "featureList"}
LD_KEEP = {"MakeCV"}
LETTER = re.compile(r"[^\W\d_]")
TAG = re.compile(r"""<(/?)([a-zA-Z][a-zA-Z0-9-]*)((?:\s+[^\s=>/"']+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>"']+))?)*)\s*(/?)>""")
ATTR = re.compile(r"""([^\s=>/"']+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>"']+)))?""")
BLOCK = re.compile(r"<!--i18n:block ([\w-]+)-->(.*?)<!--/i18n:block-->", re.S)
JS = re.compile(r"/\*i18n:js\*/(.*?)/\*/i18n:js\*/", re.S)


def norm(s):
    return " ".join(s.split())


def page_url(lang):
    return f"{SITE}/" if lang == "en" else f"{SITE}/{lang}"


def has_letter(fragment):
    return bool(LETTER.search(html.unescape(re.sub(r"<[^>]+>", "", fragment))))


def block_hash(content):
    return hashlib.sha256(norm(content).encode()).hexdigest()[:10]


# ── Units: text runs and attribute values, as (start, end, key) spans of the source ──
def units(src):
    out, run = [], []

    def flush():
        r = run[:]
        run.clear()
        while r and r[0][0] == "text" and not src[r[0][1]:r[0][2]].strip():
            r.pop(0)
        while r and r[-1][0] == "text" and not src[r[-1][1]:r[-1][2]].strip():
            r.pop()
        # strip an inline element that wraps the whole run (<a href="…">Templates</a> → "Templates")
        while len(r) >= 2 and r[0][0] == "open" and r[-1][0] == "close" and r[0][3] == r[-1][3]:
            depth, wraps = 0, True
            for k, t in enumerate(r):
                if t[0] in ("open", "close") and t[3] == r[0][3]:
                    depth += 1 if t[0] == "open" else -1
                    if depth == 0 and k != len(r) - 1:
                        wraps = False
                        break
            if not wraps:
                break
            r = r[1:-1]
            while r and r[0][0] == "text" and not src[r[0][1]:r[0][2]].strip():
                r.pop(0)
            while r and r[-1][0] == "text" and not src[r[-1][1]:r[-1][2]].strip():
                r.pop()
        if not r:
            return
        a, b = r[0][1], r[-1][2]
        # keep the run's own leading/trailing whitespace out of the span
        while a < b and src[a].isspace():
            a += 1
        while b > a and src[b - 1].isspace():
            b -= 1
        if has_letter(src[a:b]):
            out.append(("text", a, b, norm(src[a:b])))

    i, n = 0, len(src)
    while i < n:
        if src.startswith("<!--", i):
            flush()
            i = src.index("-->", i) + 3
            continue
        if src.startswith("<!", i):
            flush()
            i = src.index(">", i) + 1
            continue
        m = TAG.match(src, i)
        if m:
            closing, name = bool(m.group(1)), m.group(2).lower()
            if not closing:
                attrs = {}
                for am in ATTR.finditer(m.group(3)):
                    gi = next((g for g in (2, 3, 4) if am.group(g) is not None), None)
                    if gi is None:
                        continue
                    attrs[am.group(1).lower()] = (am.group(gi), m.start(3) + am.start(gi), m.start(3) + am.end(gi))
                for k, (v, a, b) in attrs.items():
                    meta_ok = name == "meta" and k == "content" and \
                        (attrs.get("name", ("",))[0] in META_KEYS or attrs.get("property", ("",))[0] in META_KEYS)
                    if (k in ATTRS or meta_ok) and has_letter(v):
                        out.append(("attr", a, b, norm(v)))
            if name in INLINE:
                run.append(("close" if closing else "open", m.start(), m.end(), name))
            else:
                flush()
            i = m.end()
            if not closing and name in ("script", "style"):
                j = src.lower().index(f"</{name}", i)
                out.append(("raw", i, j, src[m.start():m.end()]))
                i = j
            continue
        j = src.find("<", i + 1)
        j = n if j == -1 else j
        run.append(("text", i, j, None))
        i = j
    flush()
    return out


def tags_of(s):
    return sorted(norm(t) for t in re.findall(r"<[^>]+>", s))


# ── Language data ──
def load(lang):
    f = I18N / f"{lang}.json"
    if not f.exists():
        sys.exit(f"missing {f.relative_to(ROOT)}")
    return json.loads(f.read_text(encoding="utf-8"))


def check_js(en, tr, lang, path="js"):
    errs = []
    if isinstance(en, dict) and en and set(en) <= PLURAL_KEYS and "other" in en:
        if not isinstance(tr, dict) or set(tr) != PLURALS[lang]:
            errs.append(f"{path}: plural forms must be exactly {sorted(PLURALS[lang])}")
        return errs
    if isinstance(en, dict):
        if not isinstance(tr, dict):
            return [f"{path}: expected an object"]
        for k in en:
            if k == "lang":
                continue
            if k not in tr:
                errs.append(f"{path}.{k}: missing")
            else:
                errs += check_js(en[k], tr[k], lang, f"{path}.{k}")
        errs += [f"{path}.{k}: not in index.html's L (remove it)" for k in tr if k not in en and k != "lang"]
    elif isinstance(en, list):
        if not isinstance(tr, list) or len(tr) != len(en):
            errs.append(f"{path}: expected a list of {len(en)}")
        else:
            for k, (a, b) in enumerate(zip(en, tr)):
                errs += check_js(a, b, lang, f"{path}[{k}]")
    elif type(en) is not type(tr):
        errs.append(f"{path}: expected {type(en).__name__}")
    elif isinstance(tr, str) and not tr.strip():
        errs.append(f"{path}: empty")
    return errs


def lang_switcher(lang, targets, label):
    """targets: {lang: href}. The current language is marked with aria-current."""
    links = "".join(
        f'<a href="{targets[l]}" hreflang="{l}" lang="{l}" title="{LANG_NAMES[l]}"'
        f'{" aria-current=\"true\"" if l == lang else ""}>{l.upper()}</a>' for l in ("en", "ro", "ru"))
    return f'<nav class="lang-sw" aria-label="{html.escape(label)}">{links}</nav>'


def faq_pairs(block_html):
    pairs = re.findall(r"<dt>(.*?)</dt>\s*<dd>(.*?)</dd>", block_html, re.S)
    clean = lambda s: norm(html.unescape(re.sub(r"<[^>]+>", "", s)))
    return [(clean(q), clean(a)) for q, a in pairs]


# ── Build one language ──
def build(lang, report_missing=False):
    data = load(lang)
    strings, hrefs = data.get("strings", {}), data.get("hrefs", {})
    src = (ROOT / "index.html").read_text(encoding="utf-8")
    errs, missing = [], {}

    # 4. blocks → placeholders
    blocks = {}

    def take_block(m):
        name, content = m.group(1), m.group(2)
        if name == "lang-sw":
            label = strings.get("Language")
            if label is None:
                missing["Language"] = ""
                label = "Language"
            blocks[name] = lang_switcher(lang, {"en": "/", "ro": "/ro", "ru": "/ru"}, label)
        else:
            f = I18N / lang / f"{name}.html"
            want = block_hash(content)
            if not f.exists():
                errs.append(f"block '{name}': create tools/i18n/{lang}/{name}.html starting with <!--src:{want}-->")
                blocks[name] = ""
            else:
                body = f.read_text(encoding="utf-8")
                hm = re.match(r"\s*<!--src:(\w+)-->\n?", body)
                if not hm or hm.group(1) != want:
                    errs.append(f"block '{name}': the English block changed (or no <!--src:…--> line); review "
                                f"tools/i18n/{lang}/{name}.html against index.html, then set its first line to <!--src:{want}-->")
                blocks[name] = body[hm.end():] if hm else body
        return f"<!--@@{name}@@-->"

    src = BLOCK.sub(take_block, src)

    # 3. the L object
    jm = JS.search(src)
    if not jm:
        sys.exit("index.html: /*i18n:js*/ … /*/i18n:js*/ markers not found")
    en_js = json.loads(jm.group(1))
    tr_js = data.get("js", {})
    errs += check_js(en_js, tr_js, lang)
    tr_js = dict(tr_js, lang=lang)
    js_out = json.dumps({k: tr_js.get(k) for k in en_js}, ensure_ascii=False, indent=1)
    src = src[:jm.start(1)] + js_out + src[jm.end(1):]

    # 1 + 2. text and attribute units; 5. JSON-LD
    pieces, pos, used = [], 0, set()
    for kind, a, b, key in units(src):
        if kind == "raw":
            if 'application/ld+json' not in key:
                continue
            raw = src[a:b]
            doc = json.loads(raw)
            new = ld_translate(doc, lang, strings, missing, used, blocks.get("faq", ""))
            pieces += [src[pos:a], "\n" + json.dumps(new, ensure_ascii=False, indent=2) + "\n"]
            pos = b
            continue
        if key not in strings or not str(strings[key]).strip():
            missing[key] = ""
            continue
        val = strings[key]
        used.add(key)
        if kind == "text" and tags_of(val) != tags_of(key):
            errs.append(f"strings[{key[:60]!r}]: the translation must keep the same tags {tags_of(key)}")
        if kind == "attr" and '"' in val:
            errs.append(f"strings[{key[:60]!r}]: use &quot; or typographic quotes, not \" (attribute value)")
        pieces += [src[pos:a], val]
        pos = b
    pieces.append(src[pos:])
    out = "".join(pieces)

    if report_missing:
        return missing, errs, [k for k in strings if k not in used and k != "Language"]
    if missing:
        errs.append(f"{len(missing)} English string(s) have no {lang} translation: run "
                    f"`python3 tools/build_i18n.py --missing {lang}`. First: {next(iter(missing))[:80]!r}")

    # blocks go in now, except the switcher: its EN link must survive the href rewrite below
    for name, body in blocks.items():
        if name != "lang-sw":
            out = out.replace(f"<!--@@{name}@@-->", body.strip("\n"))

    # 6. head + links
    url = page_url(lang)
    for old, new in [('<html lang="en">', f'<html lang="{lang}">'),
                     ('<link rel="canonical" href="https://makecv.org/">', f'<link rel="canonical" href="{url}">'),
                     ('<meta property="og:url" content="https://makecv.org/">', f'<meta property="og:url" content="{url}">'),
                     ('<meta property="og:locale" content="en_US">', f'<meta property="og:locale" content="{data["locale"]}">')]:
        if out.count(old) != 1:
            errs.append(f"index.html: expected exactly one {old}")
        out = out.replace(old, new)

    def link(m):
        path, rest = m.group(1), m.group(2)
        if any(path == f"/{l}" or path.startswith(f"/{l}/") for l in LANGS) or re.search(r"\.\w+$", path):
            return m.group(0)
        if path not in hrefs:
            errs.append(f"href {path!r}: add it to \"hrefs\" in tools/i18n/{lang}.json (the page this language should link to)")
            return m.group(0)
        return f'href="{hrefs[path]}{rest}"'

    out = re.sub(r'href="(/[^"#?]*)([^"]*)"', link, out)
    out = out.replace("<!--@@lang-sw@@-->", blocks.get("lang-sw", ""))
    out = out.replace("<!DOCTYPE html>\n", f"<!DOCTYPE html>\n<!-- Generated by tools/build_i18n.py from index.html + tools/i18n/{lang}.json"
                      f" + tools/i18n/{lang}/*.html. Edit those, never this file. -->\n", 1)
    if errs:
        sys.exit(f"build_i18n ({lang}) failed:\n  - " + "\n  - ".join(errs))
    dest = ROOT / lang / "index.html"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(out, encoding="utf-8")
    unused = [k for k in strings if k not in used and k != "Language"]
    if unused:
        print(f"note: {len(unused)} unused {lang} string(s) (English text changed or removed?): {unused[:3]}")
    print(f"wrote {dest.relative_to(ROOT)}  (/{lang})")


def ld_translate(doc, lang, strings, missing, used, faq_block):
    url = page_url(lang)
    if doc.get("@type") == "FAQPage":
        pairs = faq_pairs(faq_block)
        if not pairs:
            missing["(faq block: no <dt>/<dd> pairs)"] = ""
        return {"@context": doc["@context"], "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in pairs]}

    def tr(v):
        if v in LD_KEEP:
            return v
        if v not in strings:
            missing[v] = ""
            return v
        used.add(v)
        return strings[v]

    def walk(o):
        if isinstance(o, list):
            return [walk(x) for x in o]
        if not isinstance(o, dict):
            return o
        r = {}
        for k, v in o.items():
            if k in LD_KEYS and isinstance(v, str):
                r[k] = tr(v)
            elif k == "featureList":
                r[k] = [tr(x) for x in v]
            elif k == "inLanguage" and v == "en":
                r[k] = lang
            else:
                r[k] = walk(v)
        if r.get("@type") == "WebApplication":
            r["@id"], r["url"] = f"{url}#app", url
        return r
    return walk(doc)


def main(argv):
    if len(argv) >= 2 and argv[0] == "--missing":
        miss, errs, unused = build(argv[1], report_missing=True)
        print(json.dumps(miss, ensure_ascii=False, indent=1))
        for e in errs:
            print("error:", e, file=sys.stderr)
        if unused:
            print(f"unused: {json.dumps(unused, ensure_ascii=False)}", file=sys.stderr)
        return
    for lang in (argv or LANGS):
        build(lang)


if __name__ == "__main__":
    main(sys.argv[1:])
