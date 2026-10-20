#!/usr/bin/env python3
"""Capper Day: post per-match breakdowns to Telegram (HTML), one message per match.

Usage:
  python3 tools/tg_matches.py matches.json [--dry-run] [--chat @capperday] [--state reports/tg-YYYY-MM-DD.json]
          [--md reports/YYYY-MM-DD.md] [--pause 1.0]

Input JSON: {"date": "...", "matches": [ {id, emoji, league, home, away, time, sheet[], analytics[],
  aspects[], money, forecast, coupon, periods[], source} ... ]} (or {"id", "html"} for a raw post).
Token: env TG_BOT_TOKEN only, never printed. Dedup: ids already in the state file are skipped.
Output: dry-run -> "<id> <chars>" per post; live -> "ok <id> <message_id>" / "skip <id> <message_id>".
"""
import argparse, html, json, os, sys, time, urllib.error, urllib.parse, urllib.request

e = html.escape
LIMIT = 4096

def render(m):
    if "html" in m:
        return m["html"]
    teams = e(m['home']) + (f" — {e(m['away'])}" if m.get('away') else "")
    L = [f"{m.get('emoji', '🏒')} <b>{e(m['league'])} · {teams}</b>", f"🕒 {e(m['time'])} МСК", ""]
    def block(title, items):
        if items:
            L.append(f"<b>{title}</b>")
            L.extend(f"• {e(x)}" for x in items)
            L.append("")
    block("📋 Роспись", m.get("sheet"))
    block("🔎 Аналитика", m.get("analytics"))
    block("⭐ Главное", m.get("aspects"))
    if m.get("money"):
        L += ["<b>💸 Движение денег</b>", e(m["money"]), ""]
    if m.get("forecast"):
        tag = f" · <b>{e(m['coupon'])}</b>" if m.get("coupon") else ""
        L += ["<b>🎯 Прогноз на матч</b>", e(m["forecast"]) + tag, ""]
    block("⏱ По периодам (инфо)", m.get("periods"))
    if m.get("source"):
        L.append(f"<i>Источники: {e(m['source'])}</i>")
    L.append("🔞 18+")
    t = "\n".join(L).strip()
    if len(t) > LIMIT:
        t = t[:LIMIT - 20].rsplit("\n", 1)[0] + "\n…\n🔞 18+"
    return t

def send(token, chat, text):
    data = urllib.parse.urlencode({"chat_id": chat, "text": text, "parse_mode": "HTML",
                                   "disable_web_page_preview": "true",
                                   "link_preview_options": json.dumps({"is_disabled": True})}).encode()
    try:
        r = json.load(urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data, timeout=60))
    except urllib.error.HTTPError as ex:
        r = json.load(ex)
    if not r.get("ok"):
        return None, f"{r.get('error_code')} {r.get('description')}"
    return r["result"]["message_id"], None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json"); ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--chat", default="@capperday"); ap.add_argument("--state"); ap.add_argument("--md")
    ap.add_argument("--pause", type=float, default=1.0)
    a = ap.parse_args()
    data = json.load(open(a.json, encoding="utf-8"))
    matches = data["matches"] if isinstance(data, dict) else data
    texts = [(m["id"], render(m)) for m in matches]
    if a.dry_run:
        for i, t in texts:
            print(i, len(t))
        return
    token = os.environ.get("TG_BOT_TOKEN")
    if not token:
        print("error TG_BOT_TOKEN not set"); sys.exit(1)
    state = {}
    if a.state and os.path.exists(a.state):
        state = json.load(open(a.state, encoding="utf-8"))
    new = []
    for i, t in texts:
        if i in state:
            print("skip", i, state[i]); continue
        mid, err = send(token, a.chat, t)
        if err:
            print("error", i, err); break
        state[i] = mid; new.append((i, mid)); print("ok", i, mid)
        if a.state:
            json.dump(state, open(a.state, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        time.sleep(a.pause)
    if a.md and new:
        with open(a.md, "a", encoding="utf-8") as f:
            f.write(f"\n## Telegram {a.chat}: разборы матчей\n" + "".join(f"- {i}: message_id {m}\n" for i, m in new))

if __name__ == "__main__":
    main()
