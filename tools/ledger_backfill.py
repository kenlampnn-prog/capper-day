#!/usr/bin/env python3
"""One-off backfill 12–20.10.2026 for data/bets.csv + data/coupons/*.json (run 21.10.2026).

Source of every pick/odds/score: git history of index.html (commit named per day), the
archive block «Итоги» on the site and reports/YYYY-MM-DD.md. Times: GitHub push time from
data/coupons/github-push-events.json (server side). Kept in the repo for transparency.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import ledger as L

R, O = L.RULE_REG, L.RULE_OT
K, N, NO = "КХЛ", "НХЛ", "Норвегия"

def S(league, match, pick, rule, odds, src, res, score, note=""):
    return dict(kind="single", league=league, match=match, pick=pick, rule=rule, odds=odds, odds_source=src,
                _res=res, _score=score, _note=note)

def G(league, match, pick, rule, odds, src, res, score, note=""):
    return dict(league=league, match=match, pick=pick, rule=rule, odds=odds, odds_source=src,
                _res=res, _score=score, _note=note)

def X(odds, legs, note=""):
    return dict(kind="express", odds=odds, legs=legs, _note=note)

DAYS = [
 ("2026-10-12", 200, "580dd30", "2026-10-12T05:08:46Z",
  "Купон в 2907bc4 (05:07) был другим (Амур/Салават + Барыс×Драконы), исправлен в 580dd30. Банк утра на сайте сначала 9 412, в 94174f5 заменён на базу 9 708.", [
  S(K, "Ак Барс — Сочи", "П1 Ак Барс", R, 1.72, "не указан на сайте", "loss", "2:3"),
  S(K, "Торпедо — Металлург", "П2 Металлург", R, 2.10, "не указан на сайте", "loss", "2:3 ОТ (2:2 осн.)"),
  X(8.31, [G(K, "Салават Юлаев — Нефтехимик", "П1 Салават", R, 1.85, "не указан на сайте", "win", "4:3"),
           G(K, "Шанхай — Динамо Минск", "П2 Динамо Минск", R, 1.95, "не указан на сайте", "win", "2:3"),
           G(NO, "KFUM Oslo — Vålerenga", "П2 Vålerenga", R, 2.30, "не указан на сайте", "loss", "2:1")],
    "экспресс из 3 событий; на сайте кэф 8.31, произведение 1.85×1.95×2.30 = 8.30"),
 ]),
 ("2026-10-13", 1000, "d0c7d19", "2026-10-13T12:35:04Z",
  "Утренний купон 13.10 (cc98e36, 05:04 UTC, 200 ₽: Филадельфия 60 мин + экспресс Колумбус×Рейнджерс×Оттава 8.35) заменён до матчей: 206ffca 12:24 UTC (1000 ₽, экспресс 3.29), d0c7d19 12:35 UTC (Сиэтл вместо Филадельфии).", [
  S(K, "Северсталь — СКА", "П1 Северсталь", R, 2.60, "Winline (Бет-М 2.55, Бетсити 2.65)", "win", "2:0",
    "в d0cfeb7 кэф был 2.65, в 206ffca возвращён 2.60"),
  S(N, "Сиэтл @ Филадельфия", "Сиэтл победа", O, 2.02, "DraftKings +102", "win", "3:2 Б",
    "заменил Филадельфию (60 мин, 1.85) в d0c7d19, 12:35 UTC"),
  X(3.29, [G(N, "Флорида @ Колумбус", "Колумбус победа", O, 1.80, "DraftKings −125", "loss", "7:3"),
           G(N, "Сент-Луис @ Оттава", "Оттава победа", O, 1.83, "DraftKings −120", "loss", "7:2")]),
 ]),
 ("2026-10-14", 1000, "e140cc6", "2026-10-14T05:12:39Z",
  "Купон 29c03a7 (два экспресса, дубли, Strømsgodset ниже 1.80) исправлен в 245be52/e140cc6; ставка 200 → 1000 в 906975a (05:16:50 UTC).", [
  S(K, "ЦСКА — Динамо М", "П1 ЦСКА", R, 1.85, "Винлайн/Metaratings", "win", "1:0", "ставка 1000 ₽ с 906975a, 05:16 UTC"),
  S(N, "Монреаль @ Вашингтон", "Вашингтон победа", O, 1.77, "DraftKings −130 / Covers", "win", "4:5", "ставка 1000 ₽ с 906975a, 05:16 UTC"),
  X(3.76, [G(K, "Шанхай — Трактор", "П1 Шанхай", R, 1.95, "Metaratings/Винлайн", "loss", "2:6"),
           G(NO, "Sogndal — Odd", "П2 Odd", R, 1.93, "среднее OddsSafari (bet365 1.91)", "win", "0:1")],
    "ставка 1000 ₽ с 906975a, 05:16 UTC"),
 ]),
 ("2026-10-15", 1000, "ceef4d5", "2026-10-15T08:10:55Z",
  "На origin в 05:09 был купон 8b790ea (Локомотив + экспресс Локомотив×Rangers, 200 ₽) — с нарушением правил. Исправленный купон (коммит ceef4d5 05:14 UTC) попал на GitHub в мердже 0b04d01 в 08:10:55 UTC, до матчей.", [
  S(N, "Юта @ Эдмонтон", "Эдмонтон победа", O, 1.78, "Covers/FanDuel −126", "loss", "4:2"),
  S(N, "Виннипег @ Чикаго", "Виннипег победа", O, 1.76, "Covers (открытие −131)", "loss", "3:4 ОТ"),
  X(3.56, [G(K, "Северсталь — Локомотив", "П2 Локомотив", R, 2.07, "Винлайн/Выберу.Спорт", "loss", "5:2"),
           G(N, "Филадельфия @ Детройт", "Детройт победа", O, 1.72, "Covers/SportsJaw", "win", "1:2")]),
 ]),
 ("2026-10-16", 200, "493d703", "2026-10-16T05:09:25Z",
  "Купоны 1297c72/3529574 (Торпедо 1.74, Бостон, экспресс Спартак×Мангейм) исправлены в 493d703 за 30 секунд до 05:09:25 UTC.", [
  S(K, "Торпедо — Динамо М", "П1 Торпедо", R, 2.24, "среднее по 15 БК, BMbets", "win", "5:4"),
  S(K, "Адмирал — Спартак", "П2 Спартак", R, 1.99, "Выберу.Спорт (BMbets 2.05)", "win", "1:5"),
  X(4.37, [G(K, "Авангард — Автомобилист", "П1 Авангард", R, 2.30, "BMbets", "win", "4:2"),
           G(N, "Бостон @ Анахайм", "Бостон победа", O, 1.90, "Covers −111", "win", "4:2")]),
 ]),
 ("2026-10-17", 200, "245e3bf", "2026-10-17T05:12:07Z",
  "Купон 61a946f (05:09, Сибирь 2.44, экспресс Оттава×Kristiansund 3.76) исправлен в 245e3bf.", [
  S(K, "Сибирь — Барыс", "П1 Сибирь", R, 2.40, "BetBoom (Винлайн/PARI 2.35)", "loss", "0:1"),
  S(N, "Нью-Джерси @ Вашингтон", "Вашингтон победа", O, 1.80, "DraftKings −125, ESPN", "win", "2:4"),
  X(4.08, [G(NO, "Кристиансунн — Олесунн", "П1 Кристиансунн", R, 2.40, "BetWay (bet365 2.35, Pinnacle 2.47)", "loss", "1:4"),
           G(N, "Эдмонтон @ Юта", "Юта победа", O, 1.70, "DraftKings −142", "loss", "6:2")]),
 ]),
 ("2026-10-18", 200, "348f7e9", "2026-10-18T05:13:01Z",
  "Купон 7f08620 (05:10, Штраубинг + два экспресса) исправлен в 348f7e9.", [
  S(K, "Металлург Мг — Автомобилист", "П1 Металлург", R, 1.85, "Винлайн/Фонбет", "win", "4:2"),
  S(K, "Авангард — Трактор", "П1 Авангард", R, 1.90, "Винлайн", "loss", "2:1 Б (1:1 осн.)"),
  X(4.14, [G(K, "Динамо Минск — Ак Барс", "П1 Динамо Минск", R, 2.30, "Винлайн", "loss", "1:4"),
           G(NO, "Strømsgodset — Haugesund", "П1 Strømsgodset", R, 1.80, "LegalSport/OddStorm", "win", "5:0")]),
 ]),
 ("2026-10-19", 1000, "431f54f", "2026-10-19T05:11:00Z",
  "Купон 8a0bd85 (Северсталь 2.25, экспресс 3.70) исправлен по кэфам в 431f54f. Ставка 200 → 1000 ₽ поднята в a0c4b7c в 10:18 UTC — уже после начала матчей Амур — Барыс (12:00 МСК) и Адмирал — Салават (12:30 МСК).", [
  S(K, "Амур — Барыс", "П1 Амур", R, 2.20, "Фонбет/Винлайн", "win", "5:2",
    "ставка поднята до 1000 ₽ в 10:18 UTC, после начала матча (12:00 МСК = 09:00 UTC)"),
  S(K, "Северсталь — Торпедо", "П1 Северсталь", R, 2.10, "Винлайн/PARI", "win", "4:1", "ставка 1000 ₽ с a0c4b7c, 10:18 UTC"),
  X(3.55, [G(K, "Адмирал — Салават Юлаев", "П2 Салават", R, 1.97, "Фонбет/Винлайн", "loss", "2:0"),
           G(K, "Сочи — Шанхай", "П2 Шанхай", R, 1.80, "Винлайн/Фонбет", "win", "2:5")],
    "ставка поднята до 1000 ₽ в 10:18 UTC, после начала матча Адмирал — Салават (12:30 МСК = 09:30 UTC)"),
 ]),
 ("2026-10-20", 1000, "3275dd6", "2026-10-20T05:10:01Z",
  "Купон d81788a (05:06, 200 ₽, экспресс ~6.81) исправлен в 3275dd6. Ставку переключали на 200 в e9010ac (05:11 UTC) и вернули 1000 в c6a7d5b (08:14 UTC) — до матчей.", [
  S(K, "СКА — Автомобилист", "П1 СКА", R, 2.05, "Фонбет/Винлайн", "loss", "1:3"),
  S(K, "Локомотив — Нефтехимик", "Ф1 (−1.5) Локомотив", R, 2.10, "Фонбет/Винлайн", "loss", "0:1"),
  X(3.37, [G(N, "Миннесота @ Эдмонтон", "Эдмонтон победа", O, 1.80, "DraftKings −125", "win", "3:4 ОТ"),
           G(N, "Тампа-Бэй @ Вегас", "Вегас победа", O, 1.87, "VSiN −115", "loss", "6:2")]),
 ]),
]

def main():
    rows = [r for r in L.read_rows() if r["date"] not in {d[0] for d in DAYS}]
    hashes = L.read_hashes()
    for date, stake, commit, pushed, cnote, bets in DAYS:
        full = L.git("rev-parse", commit)[:12] or commit
        raw = {"stake": stake, "bets": [{k: v for k, v in b.items() if not k.startswith("_")} | (
            {"legs": [{k: v for k, v in l.items() if not k.startswith("_")} for l in b["legs"]]} if b["kind"] == "express" else {})
            for b in bets],
               "proof": f"backfill 21.10.2026 из git: купон впервые на GitHub в коммите {full} ({pushed}, до начала матчей)",
               "note": cnote}
        c = L.normalise_coupon(date, raw, pushed)
        data = L.canonical(c)
        path = os.path.join(L.CPN_DIR, f"{date}.json")
        open(path, "wb").write(data)
        hashes[date] = [L.hashlib.sha256(data).hexdigest(), full]
        notes, results = {}, {}
        for b, cb in zip(bets, c["bets"]):
            notes[cb["id"]] = b.get("_note", "")
            if b["kind"] == "single":
                results[cb["id"]] = {"result": b["_res"], "score": b["_score"]}
            else:
                for l, cl in zip(b["legs"], cb["legs"]):
                    notes[cl["id"]] = l.get("_note", "")
                    results[cl["id"]] = {"result": l["_res"], "score": l["_score"]}
        dr = L.rows_from_coupon(c, full, notes)
        dr = L.settle_rows(dr, date, results)
        rows += dr
    L.write_rows(rows)
    L.write_hashes(hashes)
    print("backfilled", len(DAYS), "days")

if __name__ == "__main__":
    main()
