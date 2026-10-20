#!/usr/bin/env python3
"""Capper Day: render a 1080x1350 bet-slip card («КУПОН CAPPER DAY», own design) and post it to Telegram.

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
BG1, BG2 = (5, 7, 15), (11, 15, 36)
CYAN, MAG, GREEN, PINK = (0, 240, 255), (177, 75, 255), (61, 255, 168), (255, 77, 125)
TEXT, MUTED, SOFT = (241, 245, 255), (143, 155, 191), (201, 210, 240)

FONT_DIRS = ["/usr/share/fonts/truetype/sand-box/google", "/usr/share/fonts/truetype", "/usr/share/fonts"]

def _find(name):
    for d in FONT_DIRS:
        for root, _, files in os.walk(d):
            if name in files:
                return os.path.join(root, name)
    return None

def font(kind, size, weight=None):
    cands = {"head": ["Oswald-VariableFont_wght.ttf", "DejaVuSans-Bold.ttf"],
             "body": ["Manrope-VariableFont_wght.ttf", "DejaVuSans.ttf"]}[kind]
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
    img = Image.new("RGB", (W, H), BG1)
    px = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        px.line([(0, y), (W, y)], fill=tuple(int(BG2[i] * (1 - t) + BG1[i] * t) for i in range(3)))
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    g = ImageDraw.Draw(glow)
    g.ellipse([-300, -350, 600, 450], fill=(90, 30, 140))
    g.ellipse([600, -200, 1400, 500], fill=(0, 90, 110))
    g.ellipse([300, 1050, 1300, 1700], fill=(50, 20, 100))
    glow = glow.filter(ImageFilter.GaussianBlur(160))
    return Image.blend(img, Image.composite(glow, img, Image.new("L", (W, H), 255)), 0.55).convert("RGBA")

def glass(img, box, r=28, glow_col=None):
    x0, y0, x1, y1 = box
    if glow_col:
        gl = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(gl).rounded_rectangle([x0 - 4, y0 - 4, x1 + 4, y1 + 4], r + 4, outline=glow_col + (200,), width=6)
        img.alpha_composite(gl.filter(ImageFilter.GaussianBlur(10)))
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, r, fill=(255, 255, 255, 20), outline=(255, 255, 255, 46), width=2)
    img.alpha_composite(layer)

def grad_text(img, xy, s, f, c1=CYAN, c2=MAG):
    d = ImageDraw.Draw(img)
    w_ = int(tw(d, s, f)) + 4; h_ = f.size + 20
    mask = Image.new("L", (w_, h_), 0)
    ImageDraw.Draw(mask).text((0, 0), s, font=f, fill=255)
    grad = Image.new("RGBA", (w_, h_))
    gd = ImageDraw.Draw(grad)
    for x in range(w_):
        t = x / max(w_ - 1, 1)
        gd.line([(x, 0), (x, h_)], fill=tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3)) + (255,))
    img.paste(grad, xy, mask)

def badge(img, x_right, y, s, f, col):
    d = ImageDraw.Draw(img)
    w_ = tw(d, s, f) + 40; h_ = f.size + 22
    box = [x_right - w_, y, x_right, y + h_]
    gl = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(gl).rounded_rectangle(box, h_ // 2, fill=col + (90,))
    img.alpha_composite(gl.filter(ImageFilter.GaussianBlur(12)))
    d.rounded_rectangle(box, h_ // 2, fill=(10, 20, 30), outline=col, width=3)
    d.text((box[0] + 20, y + 7), s, font=f, fill=col)
    return w_

SIG = {"hockey": "Шайба в деле, банк в плюсе! 🔞", "football": "Мяч в деле, банк в плюсе! 🔞"}

def rub(n):
    return f"{int(round(n)):,}".replace(",", " ") + " ₽"

def perforation(img, y, M):
    """Ticket tear line: dashed line with half-circle notches (own design, no BK UI)."""
    d = ImageDraw.Draw(img)
    for x in range(M + 40, W - M - 40, 26):
        d.line([(x, y), (x + 13, y)], fill=(255, 255, 255, 70), width=3)
    for cx in (M, W - M):
        d.ellipse([cx - 22, y - 22, cx + 22, y + 22], fill=BG1)

def slip_row(img, d, y, M, c, stake, accent, f):
    """One bet as a slip row. Returns new y."""
    x0, x1 = M + 26, W - M - 26
    h_ = 196
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(lay).rounded_rectangle([x0, y, x1, y + h_], 20, fill=(255, 255, 255, 14), outline=accent + (120,), width=2)
    img.alpha_composite(lay)
    d.rounded_rectangle([x0, y + 18, x0 + 8, y + h_ - 18], 4, fill=accent)
    d.text((x0 + 30, y + 16), f"{c['league']} · {c['time']} МСК", font=f["lbl"], fill=MUTED)
    ow = tw(d, c["odds"], f["odds"])
    d.text((x1 - 26 - ow, y + 14), c["odds"], font=f["odds"], fill=accent)
    bk = f"кэф {c['bk']}"
    d.text((x1 - 26 - tw(d, bk, f["lbl"]), y + 98), bk, font=f["lbl"], fill=MUTED)
    d.text((x0 + 30, y + 46), fit(d, c["match"], f["t"], x1 - x0 - ow - 100), font=f["t"], fill=TEXT)
    pk = c["pick"]
    d.text((x0 + 30, y + 96), pk, font=f["s"], fill=accent)
    lx = x0 + 30 + tw(d, pk, f["s"]) + 16
    lb = c["label"]; lw = tw(d, lb, f["lbl"]) + 24
    d.rounded_rectangle([lx, y + 96, lx + lw, y + 128], 16, outline=accent, width=2)
    d.text((lx + 12, y + 100), lb, font=f["lbl"], fill=accent)
    if stake:
        d.line([(x0 + 30, y + 150), (x1 - 26, y + 150)], fill=(255, 255, 255, 30), width=1)
        d.text((x0 + 30, y + 158), f"Ставка {rub(stake)}", font=f["lbl"], fill=SOFT)
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
    f = {"h": font("head", 76, 700), "date": font("body", 28, 700), "t": font("body", 32, 800), "s": font("body", 27, 800),
         "lbl": font("body", 22, 700), "odds": font("head", 64, 700), "bank": font("head", 58, 700), "sig": font("body", 28, 800), "s2": font("head", 44, 700)}
    stake = int(data["stake"])
    # ticket body
    glass(img, [M, 36, W - M, H - 36], 34, glow_col=CYAN)
    grad_text(img, (M + 40, 62), "КУПОН CAPPER DAY", f["h"])
    n_bets = len(data["singles"]) + (1 if data.get("express") else 0)
    d.text((M + 42, 162), f"{data['date']} · {n_bets} ставки · фикс {rub(stake)}", font=f["date"], fill=SOFT)
    perforation(img, 214, M)
    y = 240
    d.text((M + 30, y), "ОДИНАРЫ", font=f["lbl"], fill=GREEN); y += 34
    for c in data["singles"]:
        y = slip_row(img, d, y, M, c, stake, GREEN, f)
    ex = data.get("express")
    if ex:
        y += 4
        d.text((M + 30, y), "ЭКСПРЕСС", font=f["lbl"], fill=MAG)
        s = f"итог {ex['total']}"; d.text((W - M - 52 - tw(d, s, f["s"]), y - 6), s, font=f["s"], fill=MAG)
        y += 34
        x0, x1 = M + 26, W - M - 26
        h_ = 30 + 92 * len(ex["legs"]) + 56
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(lay).rounded_rectangle([x0, y, x1, y + h_], 20, fill=(255, 255, 255, 14), outline=MAG + (120,), width=2)
        img.alpha_composite(lay)
        d.rounded_rectangle([x0, y + 18, x0 + 8, y + h_ - 18], 4, fill=MAG)
        for i, l in enumerate(ex["legs"]):
            yy = y + 22 + i * 92
            d.text((x0 + 30, yy), fit(d, f"{l['match']} · {l['time']}", f["lbl"], 560), font=f["lbl"], fill=MUTED)
            d.text((x0 + 30, yy + 30), f"{l['pick']} · {l['label']}", font=f["s"], fill=TEXT)
            o = l["odds"]; d.text((x1 - 26 - tw(d, o, f["s2"]), yy - 4), o, font=f["s2"], fill=MAG)
            b = f"кэф {l['bk']}"; d.text((x1 - 26 - tw(d, b, f["lbl"]), yy + 50), b, font=f["lbl"], fill=MUTED)
        yy = y + h_ - 48
        d.line([(x0 + 30, yy - 6), (x1 - 26, yy - 6)], fill=(255, 255, 255, 30), width=1)
        d.text((x0 + 30, yy + 4), f"Ставка {rub(stake)}", font=f["lbl"], fill=SOFT)
        s = f"Возможный выигрыш {rub(stake * float(ex['total']))}"
        d.text((x1 - 26 - tw(d, s, f["lbl"]), yy + 4), s, font=f["lbl"], fill=TEXT)
        y += h_ + 16
    # bottom: totals + bank
    pot = sum(stake * float(c["odds"]) for c in data["singles"]) + (stake * float(ex["total"]) if ex else 0)
    yb = H - 280
    perforation(img, yb, M)
    d.text((M + 40, yb + 26), f"В игре {rub(stake * n_bets)} · если зайдёт всё: {rub(pot)}", font=f["lbl"], fill=SOFT)
    d.text((M + 40, yb + 64), "БАНК", font=f["lbl"], fill=CYAN)
    grad_text(img, (M + 40, yb + 88), f"{data['bank']} ₽", f["bank"], c1=CYAN, c2=GREEN)
    sig = SIG.get(data.get("sport", "hockey")).replace(" 🔞", "")
    bw = badge(img, W - M - 40, yb + 112, "18+", f["lbl"], PINK)
    d.text((W - M - 56 - bw - tw(d, sig, f["sig"]), yb + 114), sig, font=f["sig"], fill=TEXT)
    foot = data.get("site", "").replace("https://", "").rstrip("/")
    d.text((M + 40, H - 96), foot, font=f["lbl"], fill=MUTED)
    s = "открытые ставки вычитаются из банка только после расчёта"
    d.text((M + 40, H - 68), s, font=f["lbl"], fill=MUTED)
    img.convert("RGB").save(out, "PNG")
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
