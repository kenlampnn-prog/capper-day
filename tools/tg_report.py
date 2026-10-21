#!/usr/bin/env python3
"""Capper Day: morning results report for Telegram (HTML, honest: losses are shown too).

Usage:
  python3 tools/tg_report.py report.json [--dry-run] [--chat @capperday] [--state state.json] [--md reports/YYYY-MM-DD.md]

JSON: {"id": "report-YYYY-MM-DD", "date": "19.10", "bank_before": 8998, "sport": "hockey",
       "bets": [{"text": "«Амур» — «Барыс», П1 2.20 (осн.)", "score": "5:2", "win": true, "pnl": 1200}, ...]}
Header: wins >= half and pnl > 0 -> "✅ ДВА ИЗ ТРЁХ! Банк X ₽ (+Y)"; otherwise "❌ МИМО: ОДИН ИЗ ТРЁХ. Банк X ₽ (−Y)".
Bank = bank_before + sum(pnl) (computed, checked against "bank_after" if given). Max 1000 chars.
Token: env TG_BOT_TOKEN only, never printed. Output: "ok <id> <message_id>" / "skip ..." / "dry-run <id> <chars>".
"""
import argparse, html, json, os, sys, time, urllib.error, urllib.parse, urllib.request

e = html.escape
MAX = 1000
SIG = {"hockey": "Шайба в деле, банк в плюсе! 🔞", "football": "Мяч в деле, банк в плюсе! 🔞"}
NUM = {0: "НОЛЬ", 1: "ОДИН", 2: "ДВА", 3: "ТРИ", 4: "ЧЕТЫРЕ", 5: "ПЯТЬ"}
GEN = {1: "ОДНОГО", 2: "ДВУХ", 3: "ТРЁХ", 4: "ЧЕТЫРЁХ", 5: "ПЯТИ"}

def rub(n):
    return f"{abs(int(n)):,}".replace(",", " ")

def sign(n):
    return ("+" if n > 0 else "−" if n < 0 else "±") + rub(n)

def render(r):
    bets = r["bets"]; w = sum(1 for b in bets if b["win"]); n = len(bets)
    pnl = sum(int(b["pnl"]) for b in bets); bank = int(r["bank_before"]) + pnl
    if "bank_after" in r and int(r["bank_after"]) != bank:
        raise SystemExit(f"error bank mismatch {bank} != {r['bank_after']}")
    score = f"{NUM.get(w, w)} ИЗ {GEN.get(n, n)}"
    if w == n:
        head = f"✅ {score}! Чистый день."
    elif pnl > 0:
        head = f"✅ {score}!"
    else:
        head = f"❌ МИМО: {score}."
    L = [f"<b>{head} Банк {rub(bank)} ₽ ({sign(pnl)})</b>", f"Итоги {e(r['date'])}, ставка {rub(int(r.get('stake', 500)))} ₽:"]
    for b in bets:
        mark = "зашло ✅" if b["win"] else "мимо ❌"
        L.append(f"▫️ {e(b['text'])} · {e(b['score'])} — {mark} {sign(int(b['pnl']))}")
    if r.get("note"):
        L.append(e(r["note"]))
    L.append(SIG[r.get("sport", "hockey")])
    t = "\n".join(L)
    if len(t) > MAX:
        raise SystemExit(f"error report {len(t)} > {MAX}")
    return t

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json"); ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--chat", default="@capperday"); ap.add_argument("--state"); ap.add_argument("--md")
    a = ap.parse_args()
    r = json.load(open(a.json, encoding="utf-8")); rid = r.get("id", "report"); t = render(r)
    if a.dry_run:
        print("dry-run", rid, len(t)); return
    state = json.load(open(a.state, encoding="utf-8")) if a.state and os.path.exists(a.state) else {}
    if rid in state:
        print("skip", rid, state[rid]); return
    token = os.environ.get("TG_BOT_TOKEN")
    if not token:
        print("error TG_BOT_TOKEN not set"); sys.exit(1)
    data = urllib.parse.urlencode({"chat_id": a.chat, "text": t, "parse_mode": "HTML",
                                   "disable_web_page_preview": "true",
                                   "link_preview_options": json.dumps({"is_disabled": True})}).encode()
    try:
        res = json.load(urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data, timeout=60))
    except urllib.error.HTTPError as ex:
        res = json.load(ex)
    if not res.get("ok"):
        print("error", rid, res.get("error_code"), res.get("description")); sys.exit(1)
    mid = res["result"]["message_id"]; print("ok", rid, mid)
    if a.state:
        state[rid] = mid; json.dump(state, open(a.state, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if a.md:
        with open(a.md, "a", encoding="utf-8") as f:
            f.write(f"\n## Telegram {a.chat}: отчёт по итогам\n- {rid}: message_id {mid}\n")

if __name__ == "__main__":
    main()
