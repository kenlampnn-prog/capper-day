#!/usr/bin/env python3
"""Put real team logos into index.html using logos/map.json.

Usage: python3 tools/apply_logos.py [index.html]
Every `.av` letter circle next to a `.nm` team name becomes
  <div class="av logo" style="..."><img src="logos/.." alt="Team"><span>AB</span></div>
If the name is not in logos/map.json the letter circle stays as is and the name is
printed as MISSING (then add the official logo + key to map.json and rerun).
If an image fails to load in the browser, onerror restores the letter circle.
Idempotent: already converted circles are refreshed, not duplicated.
"""
import json, os, re, sys, html
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
MAP = json.load(open(os.path.join(ROOT, "logos", "map.json"), encoding="utf-8"))["teams"]

def norm(s):
    return re.sub(r"\s+", " ", html.unescape(s).replace("ё", "е").replace("Ё", "Е")).strip().lower()

NMAP = {norm(k): v for k, v in MAP.items()}

def logo_for(name):
    return MAP.get(name.strip()) or NMAP.get(norm(name))

AV = r'<div class="av(?: logo)?" style="([^"]*)">(?:<img [^>]*>)?(?:<span>)?([^<]*)(?:</span>)?</div>'
NM = r'<div class="nm">([^<]*)</div>'
missing = set()

def av_html(style, letters, name):
    p = logo_for(name)
    if not p:
        missing.add(name.strip())
        return f'<div class="av" style="{style}">{letters}</div>'
    a = html.escape(name.strip(), quote=True)
    return (f'<div class="av logo" style="{style}"><img src="{p}" alt="{a}" title="{a}" width="30" height="30" loading="lazy" '
            f'onerror="this.parentNode.classList.remove(\'logo\');this.remove()"><span>{letters}</span></div>')

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "index.html")
    s = open(path, encoding="utf-8").read()
    n = 0
    def a_then_n(m):
        nonlocal n; n += 1
        return av_html(m.group(1), m.group(2), html.unescape(m.group(3))) + f'<div class="nm">{m.group(3)}</div>'
    def n_then_a(m):
        nonlocal n; n += 1
        return f'<div class="nm">{m.group(1)}</div>' + av_html(m.group(2), m.group(3), html.unescape(m.group(1)))
    s = re.sub(AV + NM, a_then_n, s)
    s = re.sub(NM + AV, n_then_a, s)
    open(path, "w", encoding="utf-8").write(s)
    print(f"circles processed: {n}")
    for x in sorted(missing):
        print("MISSING", x)

if __name__ == "__main__":
    main()
