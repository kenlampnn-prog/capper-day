#!/usr/bin/env python3
"""Capper Day: compact per-match breakdowns for Telegram (HTML), one message per match.

Usage:
  python3 tools/tg_matches.py matches.json [--dry-run] [--chat @capperday] [--state state.json]
          [--md reports/YYYY-MM-DD.md] [--pause 1.0]
  python3 tools/tg_matches.py --delete 7-23 [--chat @capperday]      # deleteMessage for those ids

Compact template (max 500 chars, dry-run fails if exceeded):
  {emoji} <b>{league} · {title}</b> · {time}
  📋 {line}
  📈 Линия: {move}            (default "данных нет")
  🔑 {facts joined by " · "}
  🎯 Прогноз: {pick}[ ✅ {coupon}]
  ⏱ Периоды: {periods joined by " · "}
Item: {id, emoji, league, title, time, line, move, facts[], pick, coupon, periods[]} or {id, text} (one-line note).
Token: env TG_BOT_TOKEN only, never printed. Ids already in the state file are skipped.
Output: dry-run -> "<id> <chars>"; live -> "ok <id> <message_id>" / "skip <id> <message_id>".
"""
import argparse, html, json, os, sys, time, urllib.error, urllib.parse, urllib.request

e = html.escape
MAX = 500

def render(m):
    if "text" in m:
        return m["text"]
    L = [f"{m.get('emoji', '🏒')} <b>{e(m['league'])} · {e(m['title'])}</b> · {e(m['time'])}"]
    if m.get("line"):
        L.append(f"📋 {e(m['line'])}")
    L.append(f"📈 Линия: {e(m.get('move') or 'данных нет')}")
    if m.get("facts"):
        L.append("🔑 " + " · ".join(e(x) for x in m["facts"]))
    if m.get("pick"):
        L.append(f"🎯 Прогноз: {e(m['pick'])}" + (f" ✅ {e(m['coupon'])}" if m.get("coupon") else ""))
    if m.get("periods"):
        L.append("⏱ Периоды: " + " · ".join(e(x) for x in m["periods"]))
    return "\n".join(L)

def api(token, method, params):
    data = urllib.parse.urlencode(params).encode()
    try:
        r = json.load(urllib.request.urlopen(f"https://api.telegram.org/bot{token}/{method}", data, timeout=60))
    except urllib.error.HTTPError as ex:
        r = json.load(ex)
    return r

def get_token():
    t = os.environ.get("TG_BOT_TOKEN")
    if not t:
        print("error TG_BOT_TOKEN not set"); sys.exit(1)
    return t

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json", nargs="?"); ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--chat", default="@capperday"); ap.add_argument("--state"); ap.add_argument("--md")
    ap.add_argument("--pause", type=float, default=1.0); ap.add_argument("--delete")
    a = ap.parse_args()
    if a.delete:
        token = get_token()
        ids = []
        for part in a.delete.split(","):
            lo, _, hi = part.partition("-")
            ids += list(range(int(lo), int(hi or lo) + 1))
        for i in ids:
            r = api(token, "deleteMessage", {"chat_id": a.chat, "message_id": i})
            print("deleted" if r.get("ok") else "fail", i, "" if r.get("ok") else r.get("description"))
            time.sleep(0.3)
        return
    data = json.load(open(a.json, encoding="utf-8"))
    matches = data["matches"] if isinstance(data, dict) else data
    texts = [(m["id"], render(m)) for m in matches]
    too_long = [(i, len(t)) for i, t in texts if len(t) > MAX]
    if a.dry_run:
        for i, t in texts:
            print(i, len(t))
        if too_long:
            print("FAIL over", MAX, too_long); sys.exit(2)
        return
    if too_long:
        print("FAIL over", MAX, too_long); sys.exit(2)
    token = get_token()
    state = json.load(open(a.state, encoding="utf-8")) if a.state and os.path.exists(a.state) else {}
    new = []
    for i, t in texts:
        if i in state:
            print("skip", i, state[i]); continue
        r = api(token, "sendMessage", {"chat_id": a.chat, "text": t, "parse_mode": "HTML",
                                       "disable_web_page_preview": "true",
                                       "link_preview_options": json.dumps({"is_disabled": True})})
        if not r.get("ok"):
            print("error", i, r.get("error_code"), r.get("description")); break
        mid = r["result"]["message_id"]
        state[i] = mid; new.append((i, mid)); print("ok", i, mid)
        if a.state:
            json.dump(state, open(a.state, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        time.sleep(a.pause)
    if a.md and new:
        with open(a.md, "a", encoding="utf-8") as f:
            f.write(f"\n## Telegram {a.chat}: компактные разборы\n" + "".join(f"- {i}: message_id {m}\n" for i, m in new))

if __name__ == "__main__":
    main()
