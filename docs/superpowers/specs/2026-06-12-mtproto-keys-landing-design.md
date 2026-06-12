# MTProto Keys — Landing Page Design Spec

**Date:** 2026-06-12  
**Domain:** mtprotokeys.ru  
**Bot:** @mtproto_keys_bot  

---

## Overview

A single-page Russian-language marketing landing site for MTProto Keys — a subscription-based MTProto proxy service. The goal is to explain what the service is, show the user journey in the Telegram bot, present pricing, and drive traffic to @mtproto_keys_bot.

---

## Tech Stack

- **Format:** Single self-contained HTML file (`index.html`)
- **Animations:** GSAP 3 via CDN (ScrollTrigger plugin)
- **Styling:** Vanilla CSS (no frameworks, no build step)
- **Deployment:** Served as a static file via existing Nginx config

No build pipeline, no npm, no dependencies to install. Drop the file into the server.

---

## Visual Style

- **Palette:** Deep dark background (`#09090f`), purple-to-blue gradients (`#667eea → #764ba2`), accent `#a78bfa` / `#60a5fa`
- **Aesthetic:** Atmospheric gradient, glassmorphism panels, lots of whitespace
- **Typography:** System sans-serif (`-apple-system, BlinkMacSystemFont, Segoe UI`), heavy weights for headings
- **Language:** Russian throughout

---

## Page Structure

### 1. Navbar
- Sticky, `backdrop-filter: blur(12px)`, semi-transparent background
- Left: logo icon + "MTProto **Keys**" (Keys in purple)
- Center: anchor links — Как работает / Тарифы / Рефералы / FAQ
- Right: primary CTA button "Открыть бота" → `https://t.me/mtproto_keys_bot`

---

### 2. Hero (ultra-minimal)

Content — nothing more, nothing less:
```
[headline]  Telegram
            без границ

[subline]   MTProto-прокси. Работает там, где Telegram заблокирован.

[CTA]       ✈ Открыть бота

[footnote]  Первые 7 дней бесплатно
```

- Animated radial gradient background (no particles, no extra elements)
- **Entry animation (GSAP):** headline → subline → button → footnote stagger in with fade + translateY

---

### 3. User Journey ("Ключ за 30 секунд")

Two-column layout:

**Left — Steps (interactive):**
1. Открываешь бота — пишешь `/start`
2. Получаешь бесплатный ключ — 7 дней бесплатно
3. Один клик — и ты в сети — ссылка `tg://proxy` открывается в Telegram
4. Продлеваешь при желании — YuKassa или Telegram Stars

Each step is clickable. Active step is highlighted (purple border + background).

**Right — Telegram bot mockup:**
- Styled to look like a Telegram chat (dark theme)
- **Animation:** when a step becomes active (click or auto-play on scroll), the corresponding bot messages animate in one by one (typewriter-style or fade-in sequence)
- Step 1 → bot says "Привет! Вам доступен бесплатный период 7 дней"
- Step 2 → shows "Получить бесплатно" button message
- Step 3 → shows the proxy key card with `tg://proxy?...` link
- Step 4 → shows "Продлить подписку" options (99₽ / 80★)

Auto-play: on scroll into view, steps cycle automatically every 2.5s.

---

### 4. Features ("Почему MTProto Keys")

6-card grid (3×2):

| Icon | Title | Description |
|------|-------|-------------|
| 📱 | 3 устройства | Один ключ на телефоне, планшете и компьютере одновременно |
| ⚡ | Авто-переключение | При падении сервера автоматически подключается к резервному узлу |
| 🔒 | FakeTLS маскировка | Трафик выглядит как HTTPS — не виден провайдеру |
| 🌍 | Несколько серверов | Ключ реплицируется на все узлы сети одновременно |
| 🤖 | Всё в боте | Управление прямо в Telegram, без сторонних приложений |
| 💳 | Удобная оплата | YuKassa или Telegram Stars — как удобно |

- Cards: subtle border, dark background, hover → purple glow + slight lift (GSAP or CSS transition)
- Scroll-trigger: cards stagger-fade in when section enters viewport

---

### 5. Pricing ("Просто и честно")

3-card layout, center card elevated:

| | Пробный период | Месячная подписка | Telegram Stars |
|---|---|---|---|
| **Price** | 0₽ | 99₽/мес | 80★/мес |
| **Period** | первые 7 дней | в месяц | в месяц |
| **Features** | Полный доступ, 3 устройства, без карты | Все серверы, 3 устройства, приоритетная поддержка | Все серверы, 3 устройства, оплата внутри Telegram |
| **CTA** | Попробовать бесплатно | Оплатить картой | Оплатить Stars |
| **Style** | Outline | **Featured** (gradient border + badge "Популярный") | Outline |

All CTA buttons → `https://t.me/mtproto_keys_bot`

---

### 6. Referral Program ("Приглашай — получай бесплатно")

Two-column card:

**Left — 3 steps:**
1. Получаешь свою реферальную ссылку в боте
2. Друг переходит и получает **14 дней бесплатно**
3. После **5 активных приглашений** — ты получаешь 14 дней в подарок

**Right — Progress visualizer:**
- 5 circles in a row (dot indicators)
- 3 filled (example state), 2 empty
- Label: "Ещё 2 — и ключ бесплатно 🎁"
- Animation: circles fill one by one on scroll-enter

---

### 7. FAQ (Аккордеон)

5 questions, max-width 720px centered:

1. **Что такое MTProto-прокси?** — MTProto — протокол Telegram. Прокси маскирует трафик под HTTPS, провайдер не видит что вы используете Telegram.
2. **Почему Telegram заблокирован?** — В ряде стран и сетей Telegram ограничен на уровне DPI-фильтрации. MTProto-прокси обходит это.
3. **Сколько устройств можно подключить?** — Один ключ работает на 3 устройствах одновременно.
4. **Что будет когда закончится подписка?** — Бот пришлёт уведомление за сутки и за час. После окончания ключ деактивируется, данные сохраняются — можно продлить в любой момент.
5. **Безопасно ли это?** — Да. MTProto-прокси не расшифровывает трафик — только передаёт зашифрованные пакеты Telegram.

- Smooth expand/collapse animation (CSS max-height transition)
- Open item highlighted with purple border

---

### 8. Footer

Three columns, minimal:
- Left: "MTProto **Keys**" logo text
- Center: `mtprotokeys.ru · 2026`
- Right: `@mtproto_keys_bot`

---

## Animations Summary

| Element | Animation | Trigger |
|---------|-----------|---------|
| Hero content | Stagger fade+translateY, 0.15s delay between items | Page load |
| Section headings | Fade in from bottom | ScrollTrigger enter |
| Feature cards | Stagger fade+scale from bottom | ScrollTrigger enter |
| Telegram mockup messages | Sequential fade in (0.4s each) | Step activation |
| Journey steps | Auto-cycle every 2.5s; click to jump | Scroll enter / click |
| Referral dots | Fill one by one | ScrollTrigger enter |
| Pricing cards | Stagger slide up | ScrollTrigger enter |
| Card hover | Glow border + 4px lift | CSS :hover |

---

## Constraints

- No JS frameworks (no React, Vue, etc.)
- No build step — must work by opening `index.html` directly or serving as static file
- All assets inlined or loaded from CDN
- Must work in modern browsers (Chrome, Firefox, Safari, last 2 versions)
- Mobile-responsive (single column on < 768px)
