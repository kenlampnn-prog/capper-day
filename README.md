# Capper Day
Страница: https://kenlampnn-prog.github.io/capper-day/

## Telegram CTA (не удалять при ежедневном обновлении)
В `index.html` есть кнопка `a.tgbtn` в шапке (рядом с лампой темы) и блок `aside#tgcta` перед `<script>`. Обе ссылки ведут на https://t.me/capperday. Ежедневное обновление меняет только данные; эти элементы и их CSS (`.tgbtn`, `.tgcta`) нужно сохранять.

## Бренд (не откатывать)
`<title>`, `og:title` и `twitter:title` = «Capper Day — купон КХЛ/НХЛ». В `manifest.json`: name «Capper Day — купон КХЛ/НХЛ», short_name «Capper Day». В шапке написано `CAPPER <b>DAY</b>` (класс `.brand`, стиль прежний). Ежедневная рутина должна оставлять это как есть и не возвращать «KHL Bet». Название Telegram-канала: «Capper Day | Ставки КХЛ НХЛ, купон дня».
