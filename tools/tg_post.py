#!/usr/bin/env python3
"""Capper Day: render a 1080x1350 bet-slip card («КУПОН CAPPER DAY», own soft cartoon design: cream/sky clay card, mascot, team logos from logos/map.json in white badges, no neon/glow) and post it to Telegram.

Usage:
  python3 tools/tg_post.py post.json [--out card.png] [--dry-run] [--chat @capperday]

JSON: date, bank, stake, site, hook, sport (hockey|football), footer,
  singles[{league, match, time, pick, label, odds, bk}], express{total, label, legs[{match, time, pick, label, odds, bk}]}.
  bk = the bookmaker/line source whose odds were actually used (never invent one).
The bot token is read from the TG_BOT_TOKEN environment variable only and is never printed.
Output: "ok <message_id>" (or "dry-run <png path>").
"""
import argparse, html, json, os, sys, urllib.request, uuid
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1350
# Soft cartoon palette (no neon, no glow): sky blue, warm orange, cream, ice white, soft red.
BG_TOP, BG_BOT = (191, 229, 255), (255, 241, 220)
CARD, CARD2 = (255, 253, 248), (255, 246, 234)
SKY, ORANGE, GREEN, RED = (60, 155, 230), (255, 139, 61), (42, 168, 102), (226, 86, 75)
NAVY = (36, 64, 106)
TEXT, MUTED, SOFT = (38, 53, 77), (111, 125, 146), (70, 85, 109)
ICE = (241, 247, 253)

FONT_DIRS = ["/usr/share/fonts/truetype/sand-box/google", "/usr/share/fonts/truetype", "/usr/share/fonts"]
MASCOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mascot.png")
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

def _norm(x):
    return " ".join(x.replace("ё", "е").replace("Ё", "Е").split()).lower()

try:
    _LOGOS = json.load(open(os.path.join(ROOT, "logos", "map.json"), encoding="utf-8"))["teams"]
except Exception:
    _LOGOS = {}
_NLOGOS = {_norm(k): v for k, v in _LOGOS.items()}

def teams_of(match):
    """'НХЛ · Миннесота @ Эдмонтон' / 'Локомотив — Нефтехимик' -> [team1, team2]."""
    m = match.split(" · ")[-1]
    for sep in (" — ", " @ ", " - "):
        if sep in m:
            return [t.strip() for t in m.split(sep)][:2]
    return [m.strip()]

def logo_path(team):
    rel = _LOGOS.get(team) or _NLOGOS.get(_norm(team))
    if not rel:
        print(f"warn: no logo for {team!r} in logos/map.json", file=sys.stderr)
        return None
    p = os.path.join(ROOT, rel)
    return p if os.path.exists(p) else None

def _find(name):
    for d in FONT_DIRS:
        for root, _, files in os.walk(d):
            if name in files:
                return os.path.join(root, name)
    return None

def font(kind, size, weight=None):
    cands = {"head": ["Nunito-VariableFont_wght.ttf", "DejaVuSans-Bold.ttf"],
             "body": ["Nunito-VariableFont_wght.ttf", "DejaVuSans.ttf"]}[kind]
    for c in cands:
        p = _find(c)
        if p:
            f = ImageFont.truetype(p, size)
            if weight and "Variable" in c:
                try:
                    f.set_variation_by_axes([weight])
                except Exception:
                    pass
            return f
    return ImageFont.load_default()

def tw(d, s, f):
    return d.textlength(s, font=f)

def fit(d, s, f, maxw):
    if tw(d, s, f) <= maxw:
        return s
    while s and tw(d, s + "…", f) > maxw:
        s = s[:-1]
    return s + "…"

def wrap(d, s, f, maxw, maxlines=2):
    words, lines, cur = s.split(), [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if tw(d, t, f) <= maxw:
            cur = t
        else:
            lines.append(cur); cur = w_
    if cur:
        lines.append(cur)
    if len(lines) > maxlines:
        lines = lines[:maxlines]; lines[-1] = fit(d, lines[-1] + " …", f, maxw)
    return lines

def background():
    """Sky-to-cream gradient with a few soft clouds (no glow)."""
    img = Image.new("RGB", (W, H), BG_BOT)
    px = ImageDraw.Draw(img)
    for y in range(H):
        t = min(1, y / (H * 0.7))
        px.line([(0, y), (W, y)], fill=tuple(int(BG_TOP[i] * (1 - t) + BG_BOT[i] * t) for i in range(3)))
    img = img.convert("RGBA")
    cl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    c = ImageDraw.Draw(cl)
    for x, y, r in ((120, 30, 70), (210, 10, 90), (300, 40, 60), (820, H - 120, 80), (930, H - 150, 100), (1030, H - 110, 70)):
        c.ellipse([x - r, y - r * 0.6, x + r, y + r * 0.6], fill=(255, 255, 255, 170))
    img.alpha_composite(cl.filter(ImageFilter.GaussianBlur(6)))
    return img

def soft_shadow(img, box, r, off=14, blur=22, alpha=46):
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    x0, y0, x1, y1 = box
    ImageDraw.Draw(sh).rounded_rectangle([x0, y0 + off, x1, y1 + off], r, fill=(52, 84, 122, alpha))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))

def clay(img, box, r=40, fill=CARD, shadow=True):
    """Soft clay card: solid warm fill, gentle drop shadow, light top edge, subtle bottom inset."""
    if shadow:
        soft_shadow(img, box, r)
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(box, r, fill=fill)
    d.rounded_rectangle([x0, y1 - 18, x1, y1], min(r, 18), fill=tuple(max(0, v - 10) for v in fill))
    d.rounded_rectangle([x0, y0, x1, y1 - 6], r, fill=fill)

def pill(img, x, y, s, f, bg, fg, pad=18):
    d = ImageDraw.Draw(img)
    w_ = tw(d, s, f) + pad * 2; h_ = f.size + 18
    d.rounded_rectangle([x, y + 3, x + w_, y + h_ + 3], h_ // 2, fill=tuple(max(0, v - 30) for v in bg))
    d.rounded_rectangle([x, y, x + w_, y + h_], h_ // 2, fill=bg)
    d.text((x + pad, y + 6), s, font=f, fill=fg)
    return w_

def grad_text(img, xy, s, f, c1=NAVY, c2=None):
    ImageDraw.Draw(img).text(xy, s, font=f, fill=c1)

def logo_badge(img, x, y, size, team):
    """White rounded badge with a soft shadow and the team logo (letters if no logo)."""
    r = int(size * 0.3)
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([x, y + 5, x + size, y + size + 5], r, fill=(52, 84, 122, 50))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([x, y, x + size, y + size], r, fill=(255, 255, 255))
    p = logo_path(team)
    if p:
        lg = Image.open(p).convert("RGBA")
        inner = int(size * 0.76)
        lg.thumbnail((inner, inner), Image.LANCZOS)
        img.alpha_composite(lg, (x + (size - lg.width) // 2, y + (size - lg.height) // 2))
    else:
        f = font("body", int(size * 0.32), 900)
        t = team[:3].upper()
        d.text((x + (size - tw(d, t, f)) / 2, y + size * 0.3), t, font=f, fill=NAVY)

def badge(img, x_right, y, s, f, col):
    d = ImageDraw.Draw(img)
    w_ = tw(d, s, f) + 40
    return pill(img, x_right - w_, y, s, f, col, (255, 255, 255), pad=20)

SIG = {"hockey": "Шайба в деле, банк в плюсе! 🔞", "football": "Мяч в деле, банк в плюсе! 🔞"}

def rub(n):
    return f"{int(round(n)):,}".replace(",", " ") + " ₽"

def perforation(img, y, M, notch=None):
    """Ticket tear line: dashed line with round notches (own design, no BK UI)."""
    d = ImageDraw.Draw(img)
    for x in range(M + 40, W - M - 40, 26):
        d.rounded_rectangle([x, y - 2, x + 13, y + 2], 2, fill=(205, 216, 230))
    for cx in (M, W - M):
        col = notch or img.getpixel((cx if cx < W // 2 else W - 2, y))[:3]
        if cx < W // 2:
            col = img.getpixel((2, y))[:3]
        d.ellipse([cx - 22, y - 22, cx + 22, y + 22], fill=col)

def slip_row(img, d, y, M, c, stake, accent, f, tint=(234, 245, 255)):
    """One bet as a slip row. Returns new y."""
    x0, x1 = M + 26, W - M - 26
    h_ = 196
    d.rounded_rectangle([x0, y + 4, x1, y + h_ + 4], 28, fill=tuple(max(0, v - 14) for v in tint))
    d.rounded_rectangle([x0, y, x1, y + h_], 28, fill=tint)
    xs = x0
    tm = teams_of(c["match"])
    for i, t in enumerate(tm[:2]):
        logo_badge(img, x0 + 22, y + 18 + i * 62, 54, t)
    d = ImageDraw.Draw(img)
    x0 += 72
    d.text((x0 + 28, y + 16), f"{c['league']} · {c['time']} МСК", font=f["lbl"], fill=MUTED)
    ow = tw(d, c["odds"], f["odds"])
    d.text((x1 - 26 - ow, y + 8), c["odds"], font=f["odds"], fill=accent)
    bk = f"кэф {c['bk']}"
    d.text((x1 - 26 - tw(d, bk, f["lbl"]), y + 98), bk, font=f["lbl"], fill=MUTED)
    d.text((x0 + 28, y + 46), fit(d, c["match"], f["t"], x1 - x0 - ow - 100), font=f["t"], fill=TEXT)
    pk = c["pick"]
    d.text((x0 + 28, y + 96), pk, font=f["s"], fill=accent)
    lx = x0 + 28 + tw(d, pk, f["s"]) + 16
    pill(img, lx, y + 96, c["label"], f["lbl"], (255, 255, 255), accent, pad=12)
    if stake:
        d.line([(xs + 28, y + 148), (x1 - 26, y + 148)], fill=(205, 216, 230), width=2)
        d.text((xs + 28, y + 158), f"Ставка {rub(stake)}", font=f["lbl"], fill=SOFT)
        s = f"Возможный выигрыш {rub(stake * float(c['odds']))}"
        d.text((x1 - 26 - tw(d, s, f["lbl"]), y + 158), s, font=f["lbl"], fill=TEXT)
    return y + h_ + 16

def render(data, out):
    global H
    ex0 = data.get("express")
    H = 274 + len(data["singles"]) * 212 + ((54 + 30 + 92 * len(ex0["legs"]) + 56 + 16) if ex0 else 0) + 300
    H = max(H, 1080)
    img = background(); d = ImageDraw.Draw(img)
    M = 44
    f = {"h": font("head", 70, 1000), "date": font("body", 28, 800), "t": font("body", 32, 900), "s": font("body", 27, 900),
         "lbl": font("body", 22, 800), "odds": font("head", 62, 1000), "bank": font("head", 58, 1000), "sig": font("body", 27, 900), "s2": font("head", 44, 1000)}
    stake = int(data["stake"])
    # ticket body (clay card)
    clay(img, [M, 36, W - M, H - 36], 44)
    d = ImageDraw.Draw(img)
    d.text((M + 40, 60), "КУПОН ", font=f["h"], fill=NAVY)
    d.text((M + 40 + tw(d, "КУПОН ", f["h"]), 60), "CAPPER DAY", font=f["h"], fill=ORANGE)
    n_bets = len(data["singles"]) + (1 if data.get("express") else 0)
    d.text((M + 42, 154), f"{data['date']} · {n_bets} ставки · фикс {rub(stake)}", font=f["date"], fill=SOFT)
    if os.path.exists(MASCOT):
        try:
            m = Image.open(MASCOT).convert("RGBA").resize((170, 170), Image.LANCZOS)
            img.alpha_composite(m, (W - M - 182, 34))
        except Exception:
            pass
    perforation(img, 214, M)
    y = 236
    pill(img, M + 26, y - 4, "ОДИНАРЫ", f["lbl"], SKY, (255, 255, 255), pad=14); y += 44
    for c in data["singles"]:
        y = slip_row(img, d, y, M, c, stake, SKY, f)
    ex = data.get("express")
    if ex:
        y += 4
        pill(img, M + 26, y - 4, "ЭКСПРЕСС", f["lbl"], ORANGE, (255, 255, 255), pad=14)
        s = f"итог {ex['total']}"; d.text((W - M - 52 - tw(d, s, f["s"]), y - 2), s, font=f["s"], fill=ORANGE)
        y += 44
        x0, x1 = M + 26, W - M - 26
        h_ = 30 + 92 * len(ex["legs"]) + 56
        tint = (255, 240, 224)
        d.rounded_rectangle([x0, y + 4, x1, y + h_ + 4], 28, fill=(241, 224, 206))
        d.rounded_rectangle([x0, y, x1, y + h_], 28, fill=tint)
        for i, l in enumerate(ex["legs"]):
            yy = y + 22 + i * 92
            for j, t in enumerate(teams_of(l["match"])[:2]):
                logo_badge(img, x0 + 22 + j * 50, yy + 4, 46, t)
            d = ImageDraw.Draw(img)
            d.text((x0 + 128, yy), fit(d, f"{l['match']} · {l['time']}", f["lbl"], 470), font=f["lbl"], fill=MUTED)
            d.text((x0 + 128, yy + 30), f"{l['pick']} · {l['label']}", font=f["s"], fill=TEXT)
            o = l["odds"]; d.text((x1 - 26 - tw(d, o, f["s2"]), yy - 6), o, font=f["s2"], fill=ORANGE)
            b = f"кэф {l['bk']}"; d.text((x1 - 26 - tw(d, b, f["lbl"]), yy + 50), b, font=f["lbl"], fill=MUTED)
        yy = y + h_ - 48
        d.line([(x0 + 28, yy - 6), (x1 - 26, yy - 6)], fill=(226, 205, 184), width=2)
        d.text((x0 + 28, yy + 4), f"Ставка {rub(stake)}", font=f["lbl"], fill=SOFT)
        s = f"Возможный выигрыш {rub(stake * float(ex['total']))}"
        d.text((x1 - 26 - tw(d, s, f["lbl"]), yy + 4), s, font=f["lbl"], fill=TEXT)
        y += h_ + 16
    # bottom: totals + bank
    pot = sum(stake * float(c["odds"]) for c in data["singles"]) + (stake * float(ex["total"]) if ex else 0)
    yb = H - 280
    perforation(img, yb, M)
    d.text((M + 40, yb + 26), f"В игре {rub(stake * n_bets)} · если зайдёт всё: {rub(pot)}", font=f["lbl"], fill=SOFT)
    d.text((M + 40, yb + 64), "БАНК", font=f["lbl"], fill=MUTED)
    d.text((M + 40, yb + 84), f"{data['bank']} ₽", font=f["bank"], fill=GREEN)
    sig = SIG.get(data.get("sport", "hockey")).replace(" 🔞", "")
    bw = badge(img, W - M - 40, yb + 108, "18+", f["lbl"], RED)
    d.text((W - M - 56 - bw - tw(d, sig, f["sig"]), yb + 112), sig, font=f["sig"], fill=NAVY)
    foot = data.get("site", "").replace("https://", "").rstrip("/")
    d.text((M + 40, H - 100), foot, font=f["lbl"], fill=SKY)
    s = "открытые ставки вычитаются из банка только после расчёта"
    d.text((M + 40, H - 70), s, font=f["lbl"], fill=MUTED)
    img.convert("RGB").save(out, "PNG", optimize=True)
    return out

def q(match):
    """«Team» — «Team» (also for '@')."""
    for sep in (" — ", " @ "):
        if sep in match:
            return sep.join(f"«{t.strip()}»" for t in match.split(sep))
    return f"«{match}»"

def caption(data):
    e = html.escape
    stake = int(data["stake"])
    L = [f"🎟 <b>{e(data['hook'])}</b>", ""]
    for c in data["singles"]:
        L.append(f"▫️ {e(q(c['match']))}, {e(c['time'])} — {e(c['pick'])} <b>{e(c['odds'])}</b> ({e(c['label'])}), кэф {e(c['bk'])}")
    ex = data.get("express")
    if ex:
        legs = " × ".join(f"{e(q(l['pick']))} {e(l['odds'])} ({e(l['bk'])})" for l in ex["legs"])
        L.append(f"🔗 Экспресс <b>{e(ex['total'])}</b>: {legs}, {e(ex.get('label', 'с ОТ'))}")
    L += ["", f"💰 По {rub(stake)} на каждую · банк <b>{e(str(data['bank']))} ₽</b>"]
    if data.get("footer"):
        L.append(e(data["footer"]))
    L += ["", SIG.get(data.get("sport", "hockey"))]
    cap = "\n".join(L)
    if len(cap) > 1024:
        raise SystemExit(f"error caption {len(cap)} > 1024")
    return cap

def send(token, chat, png, cap):
    b = uuid.uuid4().hex
    parts = []
    for k, v in (("chat_id", chat), ("caption", cap), ("parse_mode", "HTML")):
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(f'--{b}\r\nContent-Disposition: form-data; name="photo"; filename="card.png"\r\nContent-Type: image/png\r\n\r\n'.encode()
                 + open(png, "rb").read() + b"\r\n")
    body = b"".join(parts) + f"--{b}--\r\n".encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendPhoto", data=body,
                                 headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=60))
    except urllib.error.HTTPError as ex:
        r = json.load(ex)
    if not r.get("ok"):
        print("error", r.get("error_code"), r.get("description")); sys.exit(1)
    return r["result"]["message_id"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json"); ap.add_argument("--out"); ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--chat", default="@capperday")
    a = ap.parse_args()
    data = json.load(open(a.json, encoding="utf-8"))
    out = a.out or os.path.splitext(a.json)[0] + ".png"
    render(data, out)
    cap = caption(data)
    if a.dry_run:
        print("dry-run", out, f"caption={len(cap)} chars"); return
    token = os.environ.get("TG_BOT_TOKEN")
    if not token:
        print("error TG_BOT_TOKEN not set"); sys.exit(1)
    print("ok", send(token, a.chat, out, cap))

if __name__ == "__main__":
    main()
