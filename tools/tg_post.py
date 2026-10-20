#!/usr/bin/env python3
"""Capper Day: render a 1080x1350 coupon card and post it to Telegram.

Usage:
  python3 tools/tg_post.py post.json [--out card.png] [--dry-run] [--chat @capperday]

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

def render(data, out):
    img = background(); d = ImageDraw.Draw(img)
    M = 60
    fH = font("head", 88, 700); fDate = font("body", 30, 700); fBank = font("head", 46, 700)
    fT = font("body", 32, 800); fS = font("body", 25, 600); fBadge = font("head", 34, 700); fLbl = font("body", 22, 700)
    grad_text(img, (M, 46), "CAPPER DAY", fH)
    d.text((M + 2, 160), f"{data['date']} · фикс {data['stake']} ₽ · 18+", font=fDate, fill=SOFT)
    bank = f"{data['bank']} ₽"
    bw = tw(d, bank, fBank) + 44
    glass(img, [W - M - bw, 62, W - M, 140], 22, glow_col=CYAN)
    d.text((W - M - bw + 22, 70), bank, font=fBank, fill=TEXT)
    d.text((W - M - bw + 6, 146), "банк", font=fLbl, fill=MUTED)
    y = 214
    # yesterday
    res = data.get("yesterday", [])
    if res:
        h_ = 54 + 40 * len(res)
        glass(img, [M, y, W - M, y + h_], 24)
        d.text((M + 28, y + 14), "ВЧЕРА", font=fLbl, fill=CYAN)
        for i, r in enumerate(res):
            yy = y + 48 + i * 40
            col = GREEN if str(r["result"]).startswith("+") else PINK
            d.text((M + 28, yy), fit(d, r["text"], fS, W - 2 * M - 220), font=fS, fill=SOFT)
            s = str(r["result"]); d.text((W - M - 28 - tw(d, s, fT), yy - 4), s, font=fT, fill=col)
        y += h_ + 26
    d.text((M + 4, y), "КУПОН ДНЯ", font=fLbl, fill=CYAN); y += 38
    for c in data["singles"]:
        h_ = 150
        glass(img, [M, y, W - M, y + h_], 26, glow_col=GREEN)
        d.text((M + 28, y + 18), f"{c['league']} · {c['time']} МСК", font=fLbl, fill=MUTED)
        bwid = badge(img, W - M - 26, y + 18, c["odds"], fBadge, GREEN)
        d.text((M + 28, y + 50), fit(d, c["match"], fT, W - 2 * M - bwid - 80), font=fT, fill=TEXT)
        d.text((M + 28, y + 98), fit(d, f"{c['pick']} · {c['label']}", fS, W - 2 * M - 60), font=fS, fill=GREEN)
        y += h_ + 20
    ex = data.get("express")
    if ex:
        h_ = 74 + 46 * len(ex["legs"])
        glass(img, [M, y, W - M, y + h_], 26, glow_col=MAG)
        d.text((M + 28, y + 18), "ЭКСПРЕСС", font=fLbl, fill=MAG)
        badge(img, W - M - 26, y + 14, ex["total"], fBadge, MAG)
        for i, l in enumerate(ex["legs"]):
            yy = y + 66 + i * 46
            d.text((M + 28, yy), fit(d, f"{l['pick']} ({l['match']}, {l['time']})", fS, W - 2 * M - 220), font=fS, fill=TEXT)
            s = f"{l['odds']} · {l['label_short']}"
            d.text((W - M - 28 - tw(d, s, fS), yy), s, font=fS, fill=SOFT)
        y += h_ + 20
    per = data.get("periods", [])
    if per:
        fP = font("body", 22, 600)
        lines = [fit(d, "• " + p, fP, W - 2 * M - 56) for p in per]
        h_ = 54 + 34 * len(lines)
        if y + h_ < H - 110:
            glass(img, [M, y, W - M, y + h_], 24)
            d.text((M + 28, y + 14), "ПО ПЕРИОДАМ · ИНФО, НЕ В КУПОНЕ", font=fLbl, fill=CYAN)
            for i, s in enumerate(lines):
                d.text((M + 28, y + 50 + i * 34), s, font=fP, fill=SOFT)
    fF = font("body", 24, 700)
    foot = data.get("site", "").replace("https://", "")
    d.line([(M, H - 92), (W - M, H - 92)], fill=(255, 255, 255, 40), width=2)
    d.text((M, H - 70), foot, font=fF, fill=CYAN)
    s = "18+ · ставки связаны с риском"; d.text((W - M - tw(d, s, fF), H - 70), s, font=fF, fill=MUTED)
    img.convert("RGB").save(out, "PNG")
    return out

def caption(data):
    e = html.escape
    L = [f"🏒 <b>CAPPER DAY · {e(data['date'])}</b>", ""]
    if data.get("yesterday"):
        L.append("📊 <b>Вчера</b>")
        for r in data["yesterday"]:
            L.append(f"{'✅' if str(r['result']).startswith('+') else '❌'} {e(r['text'])} <b>{e(str(r['result']))}</b>")
        L.append("")
    L.append(f"🎯 <b>Купон</b> · фикс {e(str(data['stake']))} ₽")
    for c in data["singles"]:
        L.append(f"▫️ {e(c['match'])}, {e(c['time'])} — {e(c['pick'])} <b>{e(c['odds'])}</b> ({e(c['label'])})")
    ex = data.get("express")
    if ex:
        legs = " × ".join(f"{e(l['pick'])} {e(l['odds'])}" for l in ex["legs"])
        L.append(f"🔗 Экспресс <b>{e(ex['total'])}</b>: {legs} ({e(ex.get('label', 'с ОТ и буллитами'))})")
    L += ["", f"💰 Банк: <b>{e(str(data['bank']))} ₽</b>", f"🌐 {e(data.get('site', ''))}", "", "🔞 18+. Ставки связаны с риском."]
    cap = "\n".join(L)
    if len(cap) > 1024:
        cap = cap[:1000].rsplit("\n", 1)[0] + "\n🔞 18+. Ставки связаны с риском."
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
