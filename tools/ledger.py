#!/usr/bin/env python3
"""Capper Day — публичный журнал ставок, отпечатки купонов и страница статистики.

  python3 tools/ledger.py add-coupon 2026-10-22                 # купон из index.html
  python3 tools/ledger.py add-coupon 2026-10-22 --json c.json   # купон из json
  python3 tools/ledger.py settle 2026-10-21 --json results.json
  python3 tools/ledger.py settle 2026-10-21 --set S1 win 3:1 --set E1-L2 loss 2:4
  python3 tools/ledger.py build                                 # stats.html + hashes.txt
  python3 tools/ledger.py verify                                # проверить sha256 всех купонов

Файлы: data/bets.csv (журнал), data/coupons/YYYY-MM-DD.json (канонический купон),
data/coupons/hashes.txt («дата sha256 первый_коммит»), data/site_bank.json (банк, который
сайт показывал утром — для сверки), stats.html (генерируется, руками не править).
"""
import argparse, csv, datetime as dt, hashlib, html, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
CSV_PATH = os.path.join(DATA, "bets.csv")
CPN_DIR = os.path.join(DATA, "coupons")
HASHES = os.path.join(CPN_DIR, "hashes.txt")
SITE_BANK = os.path.join(DATA, "site_bank.json")
STATS = os.path.join(ROOT, "stats.html")
REPO_URL = "https://github.com/kenlampnn-prog/capper-day"
BASE_BANK = 9708          # банк утром 12.10.2026 (база пользователя)
BASE_DATE = "2026-10-12"

FIELDS = ["bet_id", "date", "published_at_utc", "first_commit", "league", "match", "pick", "rule",
          "odds", "odds_source", "stake", "kind", "express_id", "result", "score", "profit", "note"]
RULE_REG, RULE_OT = "осн. время", "с ОТ и буллитами"
RESULTS = {"win", "loss", "open", "void"}


# ---------------------------------------------------------------- io helpers
def read_rows():
    if not os.path.exists(CSV_PATH):
        return []
    with open(CSV_PATH, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(rows):
    rows.sort(key=lambda r: (r["date"], 0 if r["bet_id"][11:].startswith("S") else 1, r["bet_id"]))
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def read_hashes():
    out = {}
    if os.path.exists(HASHES):
        for line in open(HASHES, encoding="utf-8"):
            p = line.split()
            if len(p) >= 2 and not line.startswith("#"):
                out[p[0]] = [p[1], p[2] if len(p) > 2 else "-"]
    return out


def write_hashes(h):
    with open(HASHES, "w", encoding="utf-8") as f:
        f.write("# date sha256(data/coupons/<date>.json) first_commit — sha256sum data/coupons/<date>.json\n")
        for d in sorted(h):
            f.write(f"{d} {h[d][0]} {h[d][1]}\n")


def git(*args):
    try:
        return subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return ""


def fmt_odds(x):
    return f"{float(x):.2f}"


def utcnow():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------- index.html parser
def _txt(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def parse_index(path):
    """Best-effort: купон дня из index.html (карточки take = одиночки, «в экспресс» = ноги)."""
    src = open(path, encoding="utf-8").read()
    m = re.search(r"фикс (\d+) ₽", src)
    stake = int(m.group(1)) if m else 200
    singles, legs = [], []
    # League containers: <div id="khl|nhl|del"> inside hock, <section id="foot"> for Norway
    blocks = []
    for lid, lname in (("khl", "КХЛ"), ("nhl", "НХЛ"), ("del", "DEL")):
        mm = re.search(r'<div id="%s"[^>]*>(.*?)(?=<div id="(?:khl|nhl|del)"|</section>)' % lid, src, re.S)
        if mm:
            blocks.append((lname, mm.group(1)))
    mm = re.search(r'<section id="foot".*?</section>', src, re.S)
    if mm:
        blocks.append(("Норвегия", mm.group(0)))
    for lname, blk in blocks:
        for card in re.findall(r'<article class="card">(.*?)</article>', blk, re.S):
            b = re.search(r'class="badge (\w+)">([^<]*)<', card)
            if not b:
                continue
            kind = "single" if b.group(1) == "take" and b.group(2).strip() == "take" else (
                "leg" if "в экспресс" in b.group(2) else None)
            if not kind:
                continue
            names = [_txt(x) for x in re.findall(r'<div class="nm">(.*?)</div>', card)]
            vs = re.search(r'<span class="vs">([^<]*)</span>', card)
            sep = " @ " if vs and "@" in vs.group(1) else " — "
            mon = re.search(r'<div class="m on"><div class="k">(.*?)</div><div class="v">(.*?)</div>', card)
            note = re.search(r'<div class="note">(.*?)</div>', card, re.S)
            notet = _txt(note.group(1)) if note else ""
            if not (mon and len(names) == 2):
                continue
            label, odds = _txt(mon.group(1)), _txt(mon.group(2))
            team = notet.split(",")[0].strip()
            rule = RULE_OT if ("с ОТ" in label or "с ОТ" in notet.split("(")[0]) else RULE_REG
            mk = re.sub(r"\s*(60|90) мин|\s*с ОТ.*", "", label).strip()
            if mk.startswith(team) or not mk:
                mk = "победа"
            pick = f"{mk} {team}".strip() if mk != "победа" else f"{team} победа"
            src_m = re.search(r"\d\.\d\d\s*\(([^)]*)\)", notet)
            tm = re.search(r'<span class="time">([^<]*)</span>', card)
            bet = {"league": lname, "match": sep.join(names), "pick": pick, "rule": rule,
                   "odds": float(odds), "odds_source": re.sub(r"\s+([;,.])", r"\1", src_m.group(1)).strip() if src_m else "",
                   "kickoff_msk": re.sub(r"\s*(take|в экспресс)$", "", _txt(tm.group(1))) if tm else ""}
            (singles if kind == "single" else legs).append(bet)
    ex = re.search(r'<section id="ex".*?<span class="badge take">([\d.]+)</span>', src, re.S)
    bets = [dict(b, kind="single") for b in singles]
    if legs:
        bets.append({"kind": "express", "odds": float(ex.group(1)) if ex else None, "legs": legs})
    return {"stake": stake, "bets": bets}


# ---------------------------------------------------------------- coupon model
def normalise_coupon(date, raw, published_at=None):
    """Канонический купон: id S1,S2,E1, ноги E1-L1..; без результатов."""
    stake = int(raw.get("stake", 200))
    out, s, e = [], 0, 0
    for b in raw["bets"]:
        if b["kind"] == "single":
            s += 1
            out.append({"id": f"S{s}", "kind": "single", "league": b["league"], "match": b["match"],
                        "pick": b["pick"], "rule": b["rule"], "odds": fmt_odds(b["odds"]),
                        "odds_source": b.get("odds_source", ""), "stake": b.get("stake", stake),
                        **({"kickoff_msk": b["kickoff_msk"]} if b.get("kickoff_msk") else {})})
        else:
            e += 1
            eid = f"E{e}"
            legs = []
            prod = 1.0
            for i, l in enumerate(b["legs"], 1):
                prod *= float(l["odds"])
                legs.append({"id": f"{eid}-L{i}", "league": l["league"], "match": l["match"], "pick": l["pick"],
                             "rule": l["rule"], "odds": fmt_odds(l["odds"]), "odds_source": l.get("odds_source", ""),
                             **({"kickoff_msk": l["kickoff_msk"]} if l.get("kickoff_msk") else {})})
            odds = b.get("odds") or round(prod, 2)
            out.append({"id": eid, "kind": "express", "odds": fmt_odds(odds), "stake": b.get("stake", stake),
                        "legs": legs})
    c = {"date": date, "stake": stake, "published_at": published_at or raw.get("published_at") or utcnow(),
         "bets": out}
    if raw.get("proof"):
        c["proof"] = raw["proof"]
    if raw.get("note"):
        c["note"] = raw["note"]
    return c


def rows_from_coupon(c, first_commit="", notes=None):
    notes = dict(notes or {})
    if c.get("note"):
        for k in [b["id"] for b in c["bets"]]:
            notes[k] = "; ".join(x for x in ("исправленный купон (история — в data/coupons/%s.json)" % c["date"], notes.get(k, "")) if x)
    rows = []
    base = {"date": c["date"], "published_at_utc": c["published_at"], "first_commit": first_commit,
            "result": "open", "score": "", "profit": ""}
    for b in c["bets"]:
        if b["kind"] == "single":
            rows.append(dict(base, bet_id=f'{c["date"]}-{b["id"]}', league=b["league"], match=b["match"],
                             pick=b["pick"], rule=b["rule"], odds=b["odds"], odds_source=b["odds_source"],
                             stake=b["stake"], kind="single", express_id="", note=notes.get(b["id"], "")))
        else:
            lg = sorted({l["league"] for l in b["legs"]})
            rules = sorted({l["rule"] for l in b["legs"]})
            rows.append(dict(base, bet_id=f'{c["date"]}-{b["id"]}', league="/".join(lg),
                             match=" × ".join(l["match"] for l in b["legs"]),
                             pick=" × ".join(l["pick"] for l in b["legs"]), rule="/".join(rules),
                             odds=b["odds"], odds_source="произведение кэфов ног", stake=b["stake"],
                             kind="express", express_id=f'{c["date"]}-{b["id"]}', note=notes.get(b["id"], "")))
            for l in b["legs"]:
                rows.append(dict(base, bet_id=f'{c["date"]}-{l["id"]}', league=l["league"], match=l["match"],
                                 pick=l["pick"], rule=l["rule"], odds=l["odds"], odds_source=l["odds_source"],
                                 stake="", kind="leg", express_id=f'{c["date"]}-{b["id"]}', profit="",
                                 note=notes.get(l["id"], "")))
    return rows


def cmd_add_coupon(a):
    d = a.date
    path = os.path.join(CPN_DIR, f"{d}.json")
    if os.path.exists(path) and not a.force:
        sys.exit(f"{path} уже есть — купон зафиксирован. Перезапись только с --force (и это будет видно в git).")
    raw = json.load(open(a.json, encoding="utf-8")) if a.json else parse_index(a.index or os.path.join(ROOT, "index.html"))
    if a.stake:
        raw["stake"] = a.stake
        for b in raw["bets"]:
            b.pop("stake", None)
    c = normalise_coupon(d, raw, a.published_at)
    # sanity per user rules
    singles = [b for b in c["bets"] if b["kind"] == "single"]
    exps = [b for b in c["bets"] if b["kind"] == "express"]
    warn = []
    if len(singles) > 2: warn.append("одиночек больше 2")
    if len(exps) > 1: warn.append("экспрессов больше 1")
    for e in exps:
        if float(e["odds"]) < 3.0: warn.append(f"экспресс {e['odds']} < 3.00")
    allp = singles + [l for e in exps for l in e["legs"]]
    for p in allp:
        if float(p["odds"]) < 1.70: warn.append(f"{p['pick']} {p['odds']} < 1.70")
        if p["league"] == "Норвегия" and float(p["odds"]) < 1.80: warn.append(f"Норвегия {p['pick']} < 1.80")
    ms = [p["match"] for p in allp]
    if len(ms) != len(set(ms)): warn.append("дубль матча")
    if not c["bets"]: sys.exit("купон пуст — нечего фиксировать")
    for w in warn: print("ВНИМАНИЕ:", w, file=sys.stderr)
    data = canonical(c)
    os.makedirs(CPN_DIR, exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    h = read_hashes()
    h[d] = [hashlib.sha256(data).hexdigest(), a.first_commit or "-"]
    write_hashes(h)
    rows = [r for r in read_rows() if r["date"] != d]
    rows += rows_from_coupon(c, a.first_commit or "", json.loads(a.notes) if a.notes else None)
    write_rows(rows)
    print(f"{d}: купон зафиксирован, sha256 {h[d][0]}")
    for b in c["bets"]:
        if b["kind"] == "single":
            print(f"  {b['id']} {b['match']} · {b['pick']} ({b['rule']}) {b['odds']} · {b['stake']} ₽")
        else:
            print(f"  {b['id']} экспресс {b['odds']} · {b['stake']} ₽: " + " × ".join(f"{l['pick']} {l['odds']}" for l in b["legs"]))


def settle_rows(rows, d, results):
    """results: {'S1': {'result':'win','score':'3:1'}, 'E1-L1': {...}, ...} (ids без даты)."""
    byid = {r["bet_id"]: r for r in rows if r["date"] == d}
    if not byid:
        sys.exit(f"за {d} ставок нет")
    for k, v in results.items():
        bid = k if k.startswith(d) else f"{d}-{k}"
        if bid not in byid:
            sys.exit(f"нет ставки {bid}")
        if v["result"] not in RESULTS:
            sys.exit(f"result {v['result']} не из {RESULTS}")
        byid[bid]["result"] = v["result"]
        if v.get("score") is not None:
            byid[bid]["score"] = v["score"]
        if v.get("note"):
            byid[bid]["note"] = (byid[bid]["note"] + "; " if byid[bid]["note"] else "") + v["note"]
    # expresses from legs
    for r in byid.values():
        if r["kind"] != "express":
            continue
        legs = [x for x in byid.values() if x["kind"] == "leg" and x["express_id"] == r["bet_id"]]
        k = r["bet_id"][len(d) + 1:]
        if k not in results:
            res = [l["result"] for l in legs]
            if "loss" in res: r["result"] = "loss"
            elif "open" in res: r["result"] = "open"
            elif all(x == "void" for x in res): r["result"] = "void"
            else: r["result"] = "win"
            if not r["score"]:
                r["score"] = " × ".join(l["score"] or "?" for l in legs)
        if r["result"] == "win" and any(l["result"] == "void" for l in legs):
            odds = 1.0
            for l in legs:
                if l["result"] != "void":
                    odds *= float(l["odds"])
            r["note"] = (r["note"] + "; " if r["note"] else "") + f"кэф пересчитан на {odds:.2f} (возврат ноги)"
            r["odds"] = fmt_odds(odds)
    for r in byid.values():
        if r["kind"] == "leg":
            r["profit"] = ""
            continue
        st = int(r["stake"])
        r["profit"] = {"win": str(round(st * (float(r["odds"]) - 1))), "loss": str(-st), "void": "0",
                       "open": ""}[r["result"]]
    return rows


def cmd_settle(a):
    results = {}
    if a.json:
        results.update(json.load(open(a.json, encoding="utf-8")))
    for bid, res, score in a.set or []:
        results[bid] = {"result": res, "score": score}
    rows = settle_rows(read_rows(), a.date, results)
    write_rows(rows)
    for r in rows:
        if r["date"] == a.date and r["kind"] != "leg":
            print(f"  {r['bet_id']} {r['result']} {r['score']} {r['profit']}")


def cmd_verify(a):
    h, bad = read_hashes(), 0
    for d, (sha, fc) in sorted(h.items()):
        p = os.path.join(CPN_DIR, f"{d}.json")
        ok = os.path.exists(p) and sha256_file(p) == sha
        bad += not ok
        print(d, "OK " if ok else "BAD", sha[:12], fc)
    sys.exit(1 if bad else 0)


# ---------------------------------------------------------------- stats
def compute(rows):
    st = {}
    main = [r for r in rows if r["kind"] in ("single", "express")]
    settled = [r for r in main if r["result"] in ("win", "loss", "void")]
    wins = sum(r["result"] == "win" for r in settled)
    losses = sum(r["result"] == "loss" for r in settled)
    turnover = sum(int(r["stake"]) for r in settled if r["result"] != "void")
    profit = sum(int(r["profit"] or 0) for r in settled)
    opens = [r for r in main if r["result"] == "open"]
    st.update(bets=len(settled), wins=wins, losses=losses, voids=sum(r["result"] == "void" for r in settled),
              turnover=turnover, profit=profit, open=len(opens), open_sum=sum(int(r["stake"]) for r in opens),
              hit=(100.0 * wins / (wins + losses)) if wins + losses else 0.0,
              roi=(100.0 * profit / turnover) if turnover else 0.0, bank=BASE_BANK + profit)
    days = sorted({r["date"] for r in rows})
    bank, curve = BASE_BANK, [(BASE_DATE, "утро 12.10", BASE_BANK)]
    morning = {}
    for d in days:
        morning[d] = bank
        dp = [r for r in settled if r["date"] == d]
        if dp and not any(r["result"] == "open" for r in main if r["date"] == d):
            bank += sum(int(r["profit"] or 0) for r in dp)
            curve.append((d, "после " + d[8:10] + "." + d[5:7], bank))
    st["curve"], st["morning"], st["days"] = curve, morning, days

    def group(keyf, src):
        g = {}
        for r in src:
            k = keyf(r)
            x = g.setdefault(k, dict(n=0, w=0, l=0, turn=0, profit=0, lw=0, ll=0))
            if r["kind"] == "leg":
                if r["result"] == "win": x["lw"] += 1
                elif r["result"] == "loss": x["ll"] += 1
                continue
            if r["result"] not in ("win", "loss", "void"):
                continue
            x["n"] += 1
            x["w"] += r["result"] == "win"
            x["l"] += r["result"] == "loss"
            x["turn"] += int(r["stake"]) if r["result"] != "void" else 0
            x["profit"] += int(r["profit"] or 0)
        return g
    singles_legs = [r for r in rows if r["kind"] in ("single", "leg")]
    st["by_league"] = group(lambda r: r["league"], singles_legs)
    st["by_type"] = group(lambda r: "Одиночки" if r["kind"] == "single" else "Экспрессы", main)
    st["by_rule"] = group(lambda r: r["rule"], singles_legs)
    st["by_stake"] = group(lambda r: f'{r["stake"]} ₽', main)
    return st


def check_site_bank(st):
    msgs = []
    if os.path.exists(SITE_BANK):
        sb = json.load(open(SITE_BANK, encoding="utf-8"))
        for d, v in sorted(sb.items()):
            if d.startswith("_"):
                continue
            m = st["morning"].get(d)
            if m is not None and int(v) != m:
                msgs.append(f"{d}: сайт утром показывал {v} ₽, журнал даёт {m} ₽")
    return msgs


def load_logos():
    try:
        m = json.load(open(os.path.join(ROOT, "logos", "map.json"), encoding="utf-8"))
        t = m.get("teams", m)
        low = {k.lower(): v for k, v in t.items() if isinstance(v, str)}
        return t, low
    except Exception:
        return {}, {}


def money(x, sign=True):
    s = f"{abs(int(x)):,}".replace(",", " ")
    if not sign:
        return s
    return ("+" if x > 0 else "−" if x < 0 else "") + s


def build_html(rows, st):
    E = html.escape
    teams, low = load_logos()
    hashes = read_hashes()

    def logo(team):
        t = team.strip()
        p = teams.get(t) or low.get(t.lower())
        if not p:
            for k, v in teams.items():
                if isinstance(v, str) and len(k) > 3 and (t.startswith(k) or k.startswith(t)):
                    p = v; break
        ini = E("".join(w[0] for w in re.split(r"[\s/-]+", t) if w)[:2].upper())
        if p:
            return (f'<span class="lg"><img src="{E(p)}" alt="{E(t)}" title="{E(t)}" width="26" height="26" '
                    f'onerror="this.parentNode.classList.add(\'ini\');this.remove()"><i>{ini}</i></span>')
        return f'<span class="lg ini"><i>{ini}</i></span>'

    def match_html(m):
        sep = " @ " if " @ " in m else " — "
        parts = m.split(sep)
        if len(parts) == 2:
            return f'{logo(parts[0])}<span class="mt">{E(parts[0])}<em>{E(sep.strip())}</em>{E(parts[1])}</span>{logo(parts[1])}'
        return f'<span class="mt">{E(m)}</span>'

    def rnote(r):
        n = re.sub(r"^исправленный купон \(история — в data/coupons/[\d-]+\.json\);?\s*", "", r["note"] or "")
        return f'<div class="bn">{E(n)}</div>' if n else ""

    def badge(r):
        res = r["result"]
        lab = {"win": "выигрыш", "loss": "проигрыш", "open": "в игре", "void": "возврат"}[res]
        if r["kind"] != "leg" and res in ("win", "loss", "void"):
            lab = money(int(r["profit"] or 0)) + " ₽"
        if r["kind"] == "leg":
            lab = {"win": "✓ зашла", "loss": "✗ мимо", "open": "в игре", "void": "возврат"}[res]
        return f'<span class="badge {res}">{E(lab)}</span>'

    curve = st["curve"]
    # ---- SVG chart
    W, H, pl, pr, pt, pb = 820, 260, 58, 18, 18, 40
    vals = [c[2] for c in curve]
    lo, hi = min(vals + [BASE_BANK]), max(vals + [BASE_BANK])
    pad = max(300, (hi - lo) * 0.12)
    lo, hi = (lo - pad) // 500 * 500, (hi + pad + 499) // 500 * 500
    def X(i): return pl + (W - pl - pr) * (i / max(1, len(curve) - 1))
    def Y(v): return pt + (H - pt - pb) * (1 - (v - lo) / (hi - lo))
    grid = ""
    step = 1000 if hi - lo > 3000 else 500
    v = lo
    while v <= hi:
        grid += f'<line x1="{pl}" x2="{W-pr}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="gl"/><text x="{pl-8}" y="{Y(v)+4:.1f}" class="ax" text-anchor="end">{money(v, False)}</text>'
        v += step
    pts = " ".join(f"{X(i):.1f},{Y(c[2]):.1f}" for i, c in enumerate(curve))
    area = f"{X(0):.1f},{Y(lo):.1f} " + pts + f" {X(len(curve)-1):.1f},{Y(lo):.1f}"
    dots = ""
    for i, c in enumerate(curve):
        prev = curve[i - 1][2] if i else c[2]
        cls = "up" if c[2] > prev else "down" if c[2] < prev else "flat"
        lab = c[1].replace("после ", "")
        dots += (f'<circle cx="{X(i):.1f}" cy="{Y(c[2]):.1f}" r="6.5" class="dot {cls}"><title>{E(c[1])}: {money(c[2], False)} ₽</title></circle>'
                 f'<text x="{X(i):.1f}" y="{H-14}" class="ax" text-anchor="middle">{E(lab)}</text>')
    base_y = Y(BASE_BANK)
    svg = (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Банк по дням" class="chart">'
           f'<defs><linearGradient id="ar" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffb36b" stop-opacity=".45"/>'
           f'<stop offset="1" stop-color="#ffb36b" stop-opacity=".04"/></linearGradient></defs>{grid}'
           f'<line x1="{pl}" x2="{W-pr}" y1="{base_y:.1f}" y2="{base_y:.1f}" class="base"/>'
           f'<text x="{W-pr}" y="{base_y-6:.1f}" class="ax" text-anchor="end">старт {money(BASE_BANK, False)}</text>'
           f'<polygon points="{area}" fill="url(#ar)"/><polyline points="{pts}" class="ln"/>{dots}</svg>')

    def gtable(g, title, legs=True):
        tr = ""
        for k, x in sorted(g.items(), key=lambda kv: -(kv[1]["n"] + kv[1]["lw"] + kv[1]["ll"])):
            roi = (100.0 * x["profit"] / x["turn"]) if x["turn"] else None
            hit = f'{100.0*x["w"]/(x["w"]+x["l"]):.0f}%' if x["w"] + x["l"] else "—"
            lg = f'{x["lw"]}/{x["lw"]+x["ll"]}' if x["lw"] + x["ll"] else "—"
            pc = "pos" if x["profit"] > 0 else "neg" if x["profit"] < 0 else ""
            tr += (f'<tr><td>{E(k)}</td><td>{x["n"]}</td><td>{x["w"]}–{x["l"]}</td><td>{hit}</td>'
                   f'<td class="{pc}">{money(x["profit"]) if x["n"] else "—"}</td><td class="{pc}">{"—" if roi is None else f"{roi:+.1f}%".replace("-", "−")}</td>'
                   + (f'<td>{lg}</td>' if legs else "") + '</tr>')
        head = ('<tr><th></th><th>ставок</th><th>W–L</th><th>прох.</th><th>₽</th><th>ROI</th>'
                + ('<th>ноги эксп.</th>' if legs else "") + '</tr>')
        return f'<div class="card"><h3>{E(title)}</h3><div class="tw"><table class="gt">{head}{tr}</table></div></div>'

    # ---- per-day
    days_html = ""
    for d in sorted(st["days"], reverse=True):
        dr = [r for r in rows if r["date"] == d]
        main = [r for r in dr if r["kind"] != "leg"]
        dprof = sum(int(r["profit"] or 0) for r in main)
        is_open = any(r["result"] == "open" for r in main)
        sha, fc = hashes.get(d, ["", "-"])
        pub = dr[0]["published_at_utc"] if dr else ""
        try:
            pmsk = (dt.datetime.fromisoformat(pub.replace("Z", "+00:00")) + dt.timedelta(hours=3)).strftime("%d.%m %H:%M")
        except Exception:
            pmsk = pub
        fc_link = (f'<a href="{REPO_URL}/commit/{E(fc)}" target="_blank" rel="noopener">коммит {E(fc[:7])}</a>'
                   if fc and fc != "-" else "коммит — после пуша")
        cp = f'<a href="{REPO_URL}/blob/main/data/coupons/{d}.json" target="_blank" rel="noopener">sha256 {E(sha[:12])}…</a>' if sha else ""
        items = ""
        for r in main:
            meta = f'{E(r["rule"])} · кэф <b>{E(r["odds"])}</b> · {E(r["stake"])} ₽'
            if r["kind"] == "single":
                items += (f'<div class="bet"><div class="bt">{match_html(r["match"])}</div>'
                          f'<div class="bm"><span class="pk">{E(r["pick"])}</span><span class="mu">{meta}</span>'
                          f'<span class="sc">{E(r["score"] or "—")}</span>{badge(r)}</div>'
                          + rnote(r) + '</div>')
            else:
                legs = [x for x in dr if x["kind"] == "leg" and x["express_id"] == r["bet_id"]]
                lh = "".join(
                    f'<div class="leg"><div class="bt">{match_html(l["match"])}</div><div class="bm"><span class="pk">{E(l["pick"])}</span>'
                    f'<span class="mu">{E(l["league"])} · {E(l["rule"])} · {E(l["odds"])}</span><span class="sc">{E(l["score"] or "—")}</span>{badge(l)}</div>'
                    + rnote(l) + '</div>' for l in legs)
                items += (f'<div class="bet ex"><div class="bm"><span class="pk">Экспресс {E(r["odds"])}</span>'
                          f'<span class="mu">{E(r["stake"])} ₽ · {len(legs)} события</span>{badge(r)}</div>{lh}'
                          + rnote(r) + '</div>')
        dd = f"{int(d[8:10])}.{d[5:7]}"
        tot = ('<span class="badge open">в игре</span>' if is_open else
               f'<span class="badge {"win" if dprof > 0 else "loss" if dprof < 0 else "void"}">{money(dprof)} ₽</span>')
        cjs = os.path.join(CPN_DIR, f"{d}.json")
        cnote = json.load(open(cjs, encoding="utf-8")).get("note", "") if os.path.exists(cjs) else ""
        mb = st["morning"].get(d)
        days_html += (f'<article class="card day"><div class="dh"><div><h3>{dd}.2026</h3><div class="mu">'
                      f'банк утром {money(mb, False)} ₽ · опубликован {E(pmsk)} МСК</div></div>{tot}</div>{items}'
                      f'<div class="fp">🔒 Отпечаток купона: {cp} · {fc_link}'
                      + (f'<br>✏️ {E(cnote)}' if cnote else "") + '</div></article>')

    roi_s = f'{st["roi"]:+.1f}%'.replace("-", "−")
    pc = "pos" if st["profit"] > 0 else "neg" if st["profit"] < 0 else ""
    kpis = [
        ("Ставок рассчитано", str(st["bets"]), ""),
        ("Выигрыши / проигрыши", f'{st["wins"]} / {st["losses"]}', ""),
        ("Проходимость", f'{st["hit"]:.1f}%', ""),
        ("Прибыль", money(st["profit"]) + " ₽", pc),
        ("ROI (прибыль / оборот)", roi_s, pc),
        ("Оборот", money(st["turnover"], False) + " ₽", ""),
        ("Текущий банк", money(st["bank"], False) + " ₽", "bank"),
        ("Открыто сейчас", f'{st["open"]} · {money(st["open_sum"], False)} ₽', ""),
    ]
    kp = "".join(f'<div class="kpi {c}"><div class="k">{E(k)}</div><div class="v">{E(v)}</div></div>' for k, v, c in kpis)
    upd = utcnow()
    return TEMPLATE.format(kpis=kp, svg=svg, base=money(BASE_BANK, False), bank=money(st["bank"], False),
                           open_sum=money(st["open_sum"], False),
                           g_league=gtable(st["by_league"], "По лигам (одиночки; ноги экспрессов — отдельно)"),
                           g_type=gtable(st["by_type"], "Одиночки и экспрессы", legs=False),
                           g_rule=gtable(st["by_rule"], "По правилу расчёта"),
                           g_stake=gtable(st["by_stake"], "По размеру ставки", legs=False),
                           days=days_html, updated=E(upd), repo=REPO_URL)


TEMPLATE = r"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"/>
<title>Статистика — Capper Day</title>
<meta name="description" content="Capper Day: открытый журнал всех ставок с 12 октября 2026 — проходимость, прибыль, ROI, банк по дням и отпечатки купонов в git. Минусы не прячем. 18+."/>
<meta property="og:title" content="Статистика — Capper Day"/>
<meta property="og:description" content="Все ставки, проходимость, ROI и банк по дням. Каждый купон зафиксирован в git до матча. 18+."/>
<meta name="theme-color" content="#8fd0ff"/>
<link rel="icon" href="favicon.ico?v=3" sizes="any"/>
<link rel="icon" type="image/png" sizes="32x32" href="favicon-32.png?v=3"/>
<link rel="apple-touch-icon" href="apple-touch-icon.png?v=3"/>
<link rel="manifest" href="manifest.json?v=3"/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="https://fonts.googleapis.com/css2?family=Baloo+2:wght@600;800&family=Nunito:wght@400;600;700;800;900&display=swap" rel="stylesheet"/>
<style>
*{{box-sizing:border-box;margin:0}}
:root{{--bg:#fdf5e8;--bg2:#cfeaff;--card:#fffdf8;--card2:#fff6ea;--line:rgba(52,84,122,.12);--text:#26354d;--muted:#6f7d92;--soft:#46556d;--chip:#fff;--ice:#f1f7fd;--sky:#3c9be6;--sky2:#7cc4f5;--orange:#ff8b3d;--orange2:#ffb36b;--ok:#2aa866;--bad:#e2564b;--warn:#e0922a;--clay:0 12px 26px rgba(52,84,122,.14),0 3px 6px rgba(52,84,122,.08),inset 0 -5px 0 rgba(52,84,122,.06),inset 0 2px 0 rgba(255,255,255,.9);--clay-sm:0 6px 14px rgba(52,84,122,.13),inset 0 -3px 0 rgba(52,84,122,.07),inset 0 2px 0 rgba(255,255,255,.85)}}
body.light{{--bg:#f3e6d6;--bg2:#ffd9b8;--card:#fffaf2;--card2:#fdeedd;--line:rgba(110,70,40,.14);--text:#3a2c22;--muted:#86705e;--soft:#5b4636;--chip:#fffaf2;--ice:#fbf0e3;--sky:#4a8fd0;--sky2:#8fbfe8;--orange:#f27a2e;--orange2:#ffab66}}
body{{font-family:Nunito,system-ui,sans-serif;color:var(--text);min-height:100dvh;background:radial-gradient(700px 380px at 0% 0%,rgba(255,200,140,.35),transparent 70%),radial-gradient(800px 420px at 100% 0%,rgba(150,210,255,.45),transparent 70%),linear-gradient(180deg,var(--bg2),var(--bg) 420px);background-attachment:fixed}}
html{{background:#fdf5e8}}
.wrap{{max-width:880px;margin:0 auto}}
a{{color:var(--sky);font-weight:800;text-decoration:none}}
.hero{{position:relative;height:200px;border-radius:0 0 36px 36px;overflow:hidden;background:radial-gradient(120px 60px at 18% 30%,rgba(255,255,255,.95),rgba(255,255,255,0) 70%),radial-gradient(150px 70px at 52% 18%,rgba(255,255,255,.85),rgba(255,255,255,0) 70%),linear-gradient(180deg,#8fd0ff 0%,#bfe5ff 55%,#e9f6ff 100%)}}
body.light .hero{{background:radial-gradient(120px 60px at 18% 30%,rgba(255,240,225,.9),rgba(255,240,225,0) 70%),linear-gradient(180deg,#f7a86b 0%,#ffc999 50%,#ffe9d2 100%)}}
.hero:before{{content:"";position:absolute;left:-10%;right:-10%;bottom:-60px;height:120px;border-radius:50%;background:linear-gradient(180deg,#f4fbff,#dcefff);box-shadow:inset 0 6px 0 rgba(255,255,255,.9)}}
body.light .hero:before{{background:linear-gradient(180deg,#fff6ec,#f7e3cf)}}
.hero:after{{content:"";position:absolute;right:20px;top:12px;width:120px;height:120px;border-radius:50%;background:url(mascot-hero.webp?v=3) center/cover no-repeat;border:5px solid #fff;box-shadow:0 10px 22px rgba(52,84,122,.2)}}
.hero-in{{position:relative;z-index:2;display:flex;justify-content:space-between;align-items:flex-start;gap:12px;padding:18px 160px 0 16px}}
.brand{{font-family:"Baloo 2",Nunito,sans-serif;font-weight:800;font-size:32px;line-height:1;color:#24406a;background:rgba(255,255,255,.72);padding:12px 18px 10px;border-radius:24px;box-shadow:var(--clay-sm)}}
.brand b{{color:var(--orange)}}
.brand small{{display:block;font-family:Nunito,sans-serif;font-size:12.5px;color:var(--soft);font-weight:800;margin-top:4px}}
.tools{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}}
.lamp{{width:44px;height:44px;border-radius:50%;border:0;background:radial-gradient(circle at 35% 30%,#fff7d6,#ffd66b 70%,#f5b83d);font-size:20px;cursor:pointer;box-shadow:var(--clay-sm)}}
body.light .lamp{{background:radial-gradient(circle at 35% 30%,#fff,#e8edf5 70%,#cfd8e6)}}
.pill{{display:inline-flex;align-items:center;gap:6px;height:44px;padding:0 16px;border-radius:999px;background:var(--chip);color:var(--soft);font:900 13px Nunito,sans-serif;box-shadow:var(--clay-sm);white-space:nowrap}}
.pill.tg{{background:linear-gradient(180deg,var(--sky2),var(--sky));color:#fff}}
.pill.back{{background:linear-gradient(180deg,var(--orange2),var(--orange));color:#fff}}
h2{{margin:22px 18px 4px;color:var(--sky);font-size:12.5px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}}
h3{{font-family:"Baloo 2",Nunito,sans-serif;font-weight:800;font-size:20px;line-height:1.15}}
.lead{{margin:16px 16px 0;color:var(--soft);font-size:14px;line-height:1.55;font-weight:600}}
.card{{position:relative;margin:14px 14px;background:linear-gradient(170deg,var(--card),var(--card2));border:1px solid var(--line);border-radius:28px;padding:16px;box-shadow:var(--clay)}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:14px}}
.kpi{{background:linear-gradient(170deg,var(--card),var(--card2));border-radius:24px;padding:14px;box-shadow:var(--clay);border:1px solid var(--line)}}
.kpi .k{{color:var(--muted);font-size:11.5px;font-weight:800}}
.kpi .v{{font-family:"Baloo 2",Nunito,sans-serif;font-weight:800;font-size:26px;margin-top:4px;line-height:1.1}}
.kpi.pos .v,.pos{{color:var(--ok)}}
.kpi.neg .v,.neg{{color:var(--bad)}}
.kpi.bank .v{{color:var(--orange)}}
.chart{{width:100%;height:auto;display:block}}
.cw{{overflow-x:auto}}
.gl{{stroke:var(--line);stroke-width:1.5;stroke-dasharray:4 6}}
.base{{stroke:#9fb3c8;stroke-width:2;stroke-dasharray:2 5}}
.ax{{fill:var(--muted);font:800 11.5px Nunito,sans-serif}}
.ln{{fill:none;stroke:var(--orange);stroke-width:5;stroke-linecap:round;stroke-linejoin:round}}
.dot{{stroke:#fff;stroke-width:3.5}}
.dot.up{{fill:var(--ok)}}.dot.down{{fill:var(--bad)}}.dot.flat{{fill:var(--sky)}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:0}}
.tw{{overflow-x:auto}}
table.gt{{width:100%;border-collapse:collapse;margin-top:8px;font-size:13.5px}}
.gt th{{color:var(--muted);font-size:11px;font-weight:800;text-align:right;padding:6px 6px}}
.gt td{{padding:9px 6px;border-top:2px dashed var(--line);text-align:right;font-weight:800;white-space:nowrap}}
.gt td:first-child,.gt th:first-child{{text-align:left;white-space:normal}}
.badge{{font-size:11.5px;font-weight:900;border-radius:999px;padding:5px 12px;white-space:nowrap;box-shadow:inset 0 -2px 0 rgba(0,0,0,.06)}}
.badge.win{{background:#dff5e8;color:var(--ok)}}.badge.loss{{background:#fde3df;color:var(--bad)}}
.badge.open{{background:#fff0d6;color:var(--warn)}}.badge.void{{background:var(--ice);color:var(--muted)}}
.day .dh{{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:6px}}
.mu{{color:var(--muted);font-size:12px;font-weight:700}}
.bet{{padding:12px 0;border-top:2px dashed var(--line)}}
.bet.ex{{background:var(--ice);border:0;border-radius:20px;padding:12px 12px 4px;margin:10px 0 4px}}
.leg{{padding:10px 0 8px;border-top:2px dashed var(--line)}}
.bt{{display:flex;align-items:center;gap:8px;font-weight:900;font-size:15px}}
.mt em{{font-style:normal;color:var(--muted);margin:0 6px;font-weight:700}}
.bm{{display:flex;flex-wrap:wrap;align-items:center;gap:6px 12px;margin-top:6px}}
.pk{{font-weight:900;color:var(--soft)}}
.sc{{font-weight:900;background:#fff;border-radius:12px;padding:3px 10px;box-shadow:var(--clay-sm);font-size:13px}}
.bm .badge{{margin-left:auto}}
.bn{{color:var(--muted);font-size:12px;line-height:1.45;margin-top:6px}}
.lg{{flex:none;width:34px;height:34px;border-radius:12px;background:#fff;display:grid;place-items:center;box-shadow:0 4px 10px rgba(52,84,122,.16),inset 0 -3px 0 rgba(52,84,122,.07)}}
.lg img{{width:26px;height:26px;object-fit:contain}}
.lg i{{display:none;font-style:normal;font-size:11px;font-weight:900;color:var(--soft)}}
.lg.ini i{{display:block}}
.fp{{margin-top:10px;font-size:12px;color:var(--muted);font-weight:700;line-height:1.5}}
.foot{{color:var(--muted);font-size:12px;margin:12px 18px;line-height:1.55}}
.tgcta{{display:flex;align-items:center;justify-content:space-between;gap:14px;margin:20px 14px 28px;padding:18px;border-radius:30px;background:linear-gradient(135deg,#fff4e3,#e3f3ff);box-shadow:var(--clay)}}
.tgcta b{{display:block;font-weight:900;font-size:20px}}
.tgcta span{{display:block;color:var(--soft);font-size:13px;margin-top:3px}}
.tgcta a{{flex:none;padding:13px 20px;border-radius:999px;background:linear-gradient(180deg,var(--orange2),var(--orange));color:#fff;font:900 14px Nunito,sans-serif;white-space:nowrap}}
@media(max-width:700px){{.kpis{{grid-template-columns:1fr 1fr}}.grid2{{grid-template-columns:1fr}}.kpi .v{{font-size:22px}}}}
@media(max-width:600px){{.hero{{height:auto;padding-bottom:46px}}.hero:after{{width:84px;height:84px;right:10px;top:10px;border-width:4px}}.hero-in{{flex-direction:column;padding:14px 100px 0 14px}}.brand{{font-size:26px}}.bm .badge{{margin-left:0}}.tgcta{{flex-direction:column;align-items:flex-start}}.chart{{min-width:640px}}}}
</style>
</head>
<body>
<main class="wrap">
<div class="hero"><div class="hero-in"><div class="brand">CAPPER <b>DAY</b><small>📊 Статистика · все ставки с 12 октября</small></div>
<div class="tools"><a class="pill back" href="index.html">← Купон дня</a><a class="pill tg" href="https://t.me/capperday" target="_blank" rel="noopener">✈️ Telegram</a><button class="lamp" id="theme" type="button" aria-label="Тема">💡</button></div></div></div>
<p class="lead">Здесь каждая ставка Capper Day с 12 октября 2026 года: выигрыши и проигрыши, без удалений. Каждый купон лежит в git, его коммит сделан до начала матчей — задним числом купон не подменить. Старт банка {base} ₽, открытые ставки ({open_sum} ₽) из банка не вычитаются до расчёта.</p>
<div class="kpis">{kpis}</div>
<h2>Банк по дням</h2>
<div class="card"><div class="cw">{svg}</div><p class="mu" style="margin-top:6px">Точка — банк после расчёта дня. Зелёная — день в плюс, красная — в минус. Сейчас {bank} ₽.</p></div>
<h2>Разбивка</h2>
<div class="grid2">{g_type}{g_stake}</div>
{g_league}
{g_rule}
<h2>Все ставки по дням</h2>
{days}
<p class="foot">Как проверить: открой отпечаток дня — это файл data/coupons/ДАТА.json; <code>sha256sum</code> этого файла должен совпасть с хэшем на странице и в <a href="{repo}/blob/main/data/coupons/hashes.txt">hashes.txt</a>. Время публикации — время пуша на GitHub (лента событий репозитория), коммит — первый, где купон появился в исправленном виде. Для купонов 12–20 октября доказательство — коммит сайта index.html того утра (отпечаток json сделан позже, 21.10, из этих коммитов). Проходимость — доля выигрышей среди рассчитанных одиночек и экспрессов. ROI — прибыль, делённая на оборот. Полный журнал: <a href="{repo}/blob/main/data/bets.csv">data/bets.csv</a>. Обновлено {updated}. Ставки — риск, играй на то, что не жалко потерять. 18+.</p>
<aside class="tgcta"><div><b>Capper Day в Telegram</b><span>Утренний купон, разборы и честные итоги — каждый день в 08:00 МСК. 18+.</span></div><a href="https://t.me/capperday" target="_blank" rel="noopener">✈️ Открыть @capperday</a></aside>
</main>
<script>document.getElementById('theme').onclick=()=>document.body.classList.toggle('light');</script>
</body>
</html>
"""


def cmd_build(a):
    rows = read_rows()
    h = read_hashes()
    changed = False
    for d, v in h.items():
        if v[1] in ("-", ""):
            sha = git("log", "--diff-filter=A", "--format=%H", "--", f"data/coupons/{d}.json").splitlines()
            if sha:
                v[1] = sha[-1][:12]
                changed = True
                for r in rows:
                    if r["date"] == d and not r["first_commit"]:
                        r["first_commit"] = v[1]
    if changed:
        write_hashes(h)
        write_rows(rows)
    st = compute(rows)
    for m in check_site_bank(st):
        print("РАСХОЖДЕНИЕ:", m, file=sys.stderr)
    with open(STATS, "w", encoding="utf-8") as f:
        f.write(build_html(rows, st))
    print(f"stats.html: ставок {st['bets']}, {st['wins']}W/{st['losses']}L, проходимость {st['hit']:.1f}%, "
          f"прибыль {st['profit']} ₽, оборот {st['turnover']} ₽, ROI {st['roi']:.2f}%, банк {st['bank']} ₽, "
          f"открыто {st['open']} ({st['open_sum']} ₽)")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("add-coupon"); a.add_argument("date")
    a.add_argument("--json"); a.add_argument("--index"); a.add_argument("--stake", type=int)
    a.add_argument("--published-at"); a.add_argument("--first-commit"); a.add_argument("--notes")
    a.add_argument("--force", action="store_true"); a.set_defaults(f=cmd_add_coupon)
    s = sp.add_parser("settle"); s.add_argument("date"); s.add_argument("--json")
    s.add_argument("--set", nargs=3, action="append", metavar=("ID", "RESULT", "SCORE")); s.set_defaults(f=cmd_settle)
    b = sp.add_parser("build"); b.set_defaults(f=cmd_build)
    v = sp.add_parser("verify"); v.set_defaults(f=cmd_verify)
    args = p.parse_args()
    args.f(args)


if __name__ == "__main__":
    main()
