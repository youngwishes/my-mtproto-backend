# MTProto Keys Landing Page — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single-file Russian landing page for mtprotokeys.ru with GSAP animations, an interactive animated Telegram bot mockup, and sections for features, pricing, referrals, and FAQ.

**Architecture:** One self-contained `static/landing/index.html` file. All CSS is inline `<style>`, all JS is inline `<script>`. GSAP 3 + ScrollTrigger loaded from CDN. No build step — drop the file onto the server. Nginx gets a new server block for `mtprotokeys.ru` that serves this file as the root.

**Tech Stack:** HTML5, Vanilla CSS (custom properties), GSAP 3.12 + ScrollTrigger (CDN), Nginx static serve.

**Design spec:** `docs/superpowers/specs/2026-06-12-mtproto-keys-landing-design.md`

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `static/landing/index.html` | The entire landing page — HTML, CSS, JS in one file |
| Modify | `nginx/nginx.conf` | Add `mtprotokeys.ru` server block serving the landing file |

---

## Task 1: HTML Skeleton, CSS Foundation, GSAP CDN

**Files:**
- Create: `static/landing/index.html`

This task produces a valid HTML document with CSS custom properties, a CSS reset, and GSAP loaded. Nothing visible yet — just the foundation.

- [ ] **Step 1: Create the file with base skeleton**

Create `static/landing/index.html`:

```html
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="MTProto-прокси для Telegram. Работает там, где Telegram заблокирован. Первые 7 дней бесплатно.">
  <title>MTProto Keys — Telegram без ограничений</title>

  <!-- GSAP + ScrollTrigger -->
  <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/ScrollTrigger.min.js"></script>

  <style>
    /* ── CSS Custom Properties ── */
    :root {
      --bg:         #09090f;
      --bg-card:    rgba(255,255,255,0.03);
      --border:     rgba(255,255,255,0.07);
      --border-accent: rgba(167,139,250,0.3);
      --purple-1:   #667eea;
      --purple-2:   #764ba2;
      --accent:     #a78bfa;
      --accent-blue:#60a5fa;
      --text:       #ffffff;
      --text-muted: rgba(255,255,255,0.45);
      --text-dim:   rgba(255,255,255,0.25);
      --grad-text:  linear-gradient(135deg, #a78bfa, #60a5fa);
      --grad-btn:   linear-gradient(135deg, #667eea, #764ba2);
      --section-pad: 90px 40px;
      --radius-card: 16px;
      --radius-btn:  12px;
    }

    /* ── Reset ── */
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html { scroll-behavior: smooth; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      overflow-x: hidden;
      -webkit-font-smoothing: antialiased;
    }
    a { text-decoration: none; color: inherit; }
    button { font-family: inherit; cursor: pointer; border: none; }
    ul { list-style: none; }

    /* ── Utility ── */
    .grad-text {
      background: var(--grad-text);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    .section-label {
      display: inline-block;
      background: rgba(167,139,250,0.1);
      border: 1px solid var(--border-accent);
      color: var(--accent);
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 2px;
      text-transform: uppercase;
      padding: 3px 12px;
      border-radius: 20px;
      margin-bottom: 12px;
    }
    .section-header {
      text-align: center;
      margin-bottom: 56px;
    }
    .section-header h2 {
      font-size: clamp(28px, 4vw, 40px);
      font-weight: 800;
      letter-spacing: -1px;
      margin-bottom: 10px;
    }
    .section-header p {
      color: var(--text-muted);
      font-size: 16px;
      max-width: 480px;
      margin: 0 auto;
    }
    .section-wrap {
      padding: var(--section-pad);
      max-width: 1100px;
      margin: 0 auto;
    }
    .divider {
      border: none;
      border-top: 1px solid rgba(255,255,255,0.05);
      margin: 0 40px;
    }
  </style>
</head>
<body>

  <!-- sections go here -->

  <script>
    gsap.registerPlugin(ScrollTrigger);
    // animations go here
  </script>
</body>
</html>
```

- [ ] **Step 2: Open in browser and verify**

Open `static/landing/index.html` in a browser. Expected: blank dark page (`#09090f` background), no console errors (GSAP loads from CDN, needs internet).

- [ ] **Step 3: Commit**

```bash
git add static/landing/index.html
git commit -m "feat: landing — skeleton, CSS foundation, GSAP CDN"
```

---

## Task 2: Navbar

**Files:**
- Modify: `static/landing/index.html` — add navbar HTML + CSS

- [ ] **Step 1: Add navbar CSS inside `<style>`**

Add after the `.divider` rule:

```css
/* ── Navbar ── */
.nav {
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 40px;
  background: rgba(9,9,15,0.75);
  border-bottom: 1px solid rgba(255,255,255,0.05);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}
.nav-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 700;
  font-size: 15px;
  letter-spacing: 0.3px;
}
.nav-logo-icon {
  width: 32px;
  height: 32px;
  background: var(--grad-btn);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
}
.nav-logo span { color: var(--accent); }
.nav-links {
  display: flex;
  gap: 28px;
}
.nav-links a {
  color: var(--text-muted);
  font-size: 13px;
  transition: color 0.2s;
}
.nav-links a:hover { color: var(--text); }
.nav-cta {
  background: var(--grad-btn);
  color: #fff;
  padding: 8px 18px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  transition: opacity 0.2s;
}
.nav-cta:hover { opacity: 0.85; }
```

- [ ] **Step 2: Add navbar HTML inside `<body>` (before `<script>`)**

```html
<nav class="nav">
  <div class="nav-logo">
    <div class="nav-logo-icon">🔑</div>
    MTProto <span>Keys</span>
  </div>
  <div class="nav-links">
    <a href="#how">Как работает</a>
    <a href="#pricing">Тарифы</a>
    <a href="#referral">Рефералы</a>
    <a href="#faq">FAQ</a>
  </div>
  <a href="https://t.me/mtproto_keys_bot" target="_blank" rel="noopener">
    <button class="nav-cta">Открыть бота</button>
  </a>
</nav>
```

- [ ] **Step 3: Verify in browser**

Refresh. Expected: sticky dark navbar with blur, logo on left, 4 nav links in center, purple button on right.

- [ ] **Step 4: Commit**

```bash
git add static/landing/index.html
git commit -m "feat: landing — navbar"
```

---

## Task 3: Hero Section

**Files:**
- Modify: `static/landing/index.html`

Ultra-minimal: headline → one-liner → CTA button → "7 дней бесплатно" footnote.

- [ ] **Step 1: Add hero CSS**

```css
/* ── Hero ── */
.hero {
  position: relative;
  min-height: 92vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 80px 24px 60px;
  overflow: hidden;
}
.hero-bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 80% 55% at 50% -5%, rgba(102,126,234,0.28) 0%, transparent 62%),
    radial-gradient(ellipse 45% 35% at 80% 85%, rgba(118,75,162,0.18) 0%, transparent 50%);
  pointer-events: none;
}
.hero h1 {
  font-size: clamp(52px, 8vw, 80px);
  font-weight: 800;
  letter-spacing: -3px;
  line-height: 1.0;
  margin-bottom: 22px;
  position: relative;
}
.hero-sub {
  font-size: clamp(15px, 2vw, 17px);
  color: var(--text-muted);
  margin-bottom: 36px;
  position: relative;
  line-height: 1.5;
}
.hero-cta {
  background: var(--grad-btn);
  color: #fff;
  padding: 15px 34px;
  border-radius: var(--radius-btn);
  font-size: 15px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  box-shadow: 0 10px 36px rgba(102,126,234,0.35);
  transition: transform 0.2s, box-shadow 0.2s;
  position: relative;
}
.hero-cta:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 44px rgba(102,126,234,0.45);
}
.hero-footnote {
  margin-top: 18px;
  font-size: 13px;
  color: var(--text-dim);
  position: relative;
}
.hero-footnote span { color: var(--accent); }
```

- [ ] **Step 2: Add hero HTML (after `</nav>`, before `<script>`)**

```html
<section class="hero">
  <div class="hero-bg"></div>
  <h1>Telegram<br><span class="grad-text">без границ</span></h1>
  <p class="hero-sub">MTProto-прокси. Работает там, где Telegram заблокирован.</p>
  <a href="https://t.me/mtproto_keys_bot" target="_blank" rel="noopener">
    <button class="hero-cta">✈ Открыть бота</button>
  </a>
  <p class="hero-footnote">Первые <span>7 дней бесплатно</span></p>
</section>
```

- [ ] **Step 3: Add GSAP entry animation (inside `<script>`, after `gsap.registerPlugin`)**

```js
// Hero entry — stagger in
gsap.from(['.hero h1', '.hero-sub', '.hero-cta', '.hero-footnote'], {
  opacity: 0,
  y: 30,
  duration: 0.7,
  stagger: 0.12,
  ease: 'power3.out',
  delay: 0.1,
});
```

- [ ] **Step 4: Verify in browser**

Refresh. Expected: large two-line headline with gradient "без границ", purple button, elements animate in on load.

- [ ] **Step 5: Commit**

```bash
git add static/landing/index.html
git commit -m "feat: landing — hero section + entry animation"
```

---

## Task 4: User Journey Section

**Files:**
- Modify: `static/landing/index.html`

Two-column layout. Left: 4 clickable steps. Right: Telegram chat mockup where messages swap when steps change. Auto-cycles on scroll into view.

- [ ] **Step 1: Add journey CSS**

```css
/* ── Journey ── */
#how { scroll-margin-top: 80px; }
.journey-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 56px;
  align-items: center;
}
.journey-steps { display: flex; flex-direction: column; gap: 6px; }
.step {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  padding: 16px 18px;
  border-radius: 14px;
  border: 1px solid transparent;
  cursor: pointer;
  transition: background 0.25s, border-color 0.25s;
}
.step.active {
  background: rgba(167,139,250,0.07);
  border-color: var(--border-accent);
}
.step-num {
  width: 32px;
  height: 32px;
  min-width: 32px;
  border-radius: 50%;
  background: rgba(102,126,234,0.15);
  border: 1px solid rgba(167,139,250,0.25);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  color: var(--accent);
  transition: background 0.25s, border-color 0.25s, color 0.25s;
}
.step.active .step-num {
  background: var(--grad-btn);
  border-color: transparent;
  color: #fff;
}
.step-text h4 { font-size: 14px; font-weight: 600; margin-bottom: 3px; }
.step-text p { font-size: 12px; color: var(--text-muted); line-height: 1.5; }

/* Telegram phone mockup */
.tg-phone {
  background: #1c1c1e;
  border-radius: 24px;
  border: 1px solid rgba(255,255,255,0.08);
  box-shadow: 0 32px 80px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.04);
  overflow: hidden;
  max-width: 290px;
  margin: 0 auto;
}
.tg-header {
  background: #2c2c2e;
  padding: 14px 16px;
  display: flex;
  align-items: center;
  gap: 10px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
}
.tg-avatar {
  width: 36px; height: 36px;
  background: var(--grad-btn);
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 15px;
}
.tg-name { font-size: 13px; font-weight: 600; }
.tg-status { font-size: 10px; color: #4cd964; }
.tg-messages {
  padding: 14px 12px;
  min-height: 240px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.msg-bot {
  background: #2c2c2e;
  border-radius: 12px 12px 12px 4px;
  padding: 10px 12px;
  font-size: 12px;
  line-height: 1.5;
  color: rgba(255,255,255,0.85);
  max-width: 90%;
}
.msg-user {
  background: var(--grad-btn);
  border-radius: 12px 12px 4px 12px;
  padding: 8px 12px;
  font-size: 12px;
  color: #fff;
  max-width: 65%;
  align-self: flex-end;
}
.msg-card {
  background: rgba(102,126,234,0.1);
  border: 1px solid rgba(102,126,234,0.3);
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 11px;
}
.msg-card .card-label { color: var(--text-muted); font-size: 10px; margin-bottom: 4px; }
.msg-card .card-val { color: var(--accent); font-family: monospace; word-break: break-all; }
.tg-btn-row { display: flex; gap: 6px; }
.tg-btn {
  flex: 1;
  text-align: center;
  background: rgba(102,126,234,0.15);
  border: 1px solid rgba(102,126,234,0.3);
  border-radius: 8px;
  padding: 7px 4px;
  font-size: 10px;
  color: var(--accent);
  font-weight: 500;
}

/* Screen slots — only active screen visible */
.tg-screen { display: none; flex-direction: column; gap: 8px; }
.tg-screen.active { display: flex; }
```

- [ ] **Step 2: Add journey HTML (after `</section>` of hero, before `<script>`)**

```html
<hr class="divider">

<section class="section-wrap" id="how">
  <div class="section-header">
    <div class="section-label">Как это работает</div>
    <h2>Ключ за 30 секунд</h2>
    <p>Всё через Telegram-бота — никаких сайтов и регистраций</p>
  </div>
  <div class="journey-grid">
    <div class="journey-steps">
      <div class="step active" data-step="0" onclick="setStep(0)">
        <div class="step-num">1</div>
        <div class="step-text">
          <h4>Открываешь бота</h4>
          <p>Пишешь /start — бот проверяет право на пробный период</p>
        </div>
      </div>
      <div class="step" data-step="1" onclick="setStep(1)">
        <div class="step-num">2</div>
        <div class="step-text">
          <h4>Получаешь бесплатный ключ</h4>
          <p>7 дней бесплатно для новых пользователей</p>
        </div>
      </div>
      <div class="step" data-step="2" onclick="setStep(2)">
        <div class="step-num">3</div>
        <div class="step-text">
          <h4>Один клик — и ты в сети</h4>
          <p>Ссылка tg://proxy открывается прямо в Telegram</p>
        </div>
      </div>
      <div class="step" data-step="3" onclick="setStep(3)">
        <div class="step-num">4</div>
        <div class="step-text">
          <h4>Продлеваешь при желании</h4>
          <p>Оплата через YuKassa или Telegram Stars</p>
        </div>
      </div>
    </div>

    <div class="tg-phone">
      <div class="tg-header">
        <div class="tg-avatar">🔑</div>
        <div>
          <div class="tg-name">MTProto Keys Bot</div>
          <div class="tg-status">● онлайн</div>
        </div>
      </div>
      <div class="tg-messages">
        <!-- Screen 0: /start -->
        <div class="tg-screen active" id="screen-0">
          <div class="msg-user">/start</div>
          <div class="msg-bot">👋 Привет! Вам доступен <strong>бесплатный период 7 дней</strong>.</div>
          <div class="tg-btn-row">
            <div class="tg-btn">🎁 Получить бесплатно</div>
          </div>
        </div>
        <!-- Screen 1: getting key -->
        <div class="tg-screen" id="screen-1">
          <div class="msg-bot">Выдаю ваш прокси-ключ...</div>
          <div class="msg-bot">✅ <strong>Ключ активирован</strong> на 7 дней!</div>
          <div class="tg-btn-row">
            <div class="tg-btn">🔗 Подключить</div>
            <div class="tg-btn">📋 Скопировать</div>
          </div>
        </div>
        <!-- Screen 2: proxy link -->
        <div class="tg-screen" id="screen-2">
          <div class="msg-card">
            <div class="card-label">Ваш прокси-ключ</div>
            <div class="card-val">tg://proxy?server=n1.mtprotokeys.ru&amp;port=443&amp;secret=ee…</div>
          </div>
          <div class="tg-btn-row">
            <div class="tg-btn">⚡ Подключить сейчас</div>
          </div>
          <div class="msg-bot" style="font-size:11px;color:var(--text-muted);">Нажми «Подключить» — Telegram откроется автоматически</div>
        </div>
        <!-- Screen 3: renew -->
        <div class="tg-screen" id="screen-3">
          <div class="msg-bot">Выберите способ оплаты:</div>
          <div class="tg-btn-row">
            <div class="tg-btn">💳 99₽ / мес</div>
            <div class="tg-btn">⭐ 80★ / мес</div>
          </div>
          <div class="msg-bot" style="font-size:11px;color:var(--text-muted);">Ключ продлится мгновенно после оплаты</div>
        </div>
      </div>
    </div>
  </div>
</section>
```

- [ ] **Step 3: Add step-switching JS and auto-cycle (inside `<script>`)**

```js
// Journey: step switching
let journeyTimer = null;
let currentStep = 0;
const totalSteps = 4;

function setStep(n) {
  currentStep = n;
  document.querySelectorAll('.step').forEach((el, i) => {
    el.classList.toggle('active', i === n);
  });
  document.querySelectorAll('.tg-screen').forEach((el, i) => {
    el.classList.toggle('active', i === n);
  });
  // Animate new screen messages in
  const screen = document.getElementById('screen-' + n);
  const msgs = screen.querySelectorAll('.msg-bot, .msg-user, .msg-card, .tg-btn-row');
  gsap.from(msgs, { opacity: 0, y: 12, duration: 0.35, stagger: 0.1, ease: 'power2.out' });
}

function startJourneyCycle() {
  if (journeyTimer) return;
  journeyTimer = setInterval(() => {
    setStep((currentStep + 1) % totalSteps);
  }, 2500);
}

// Auto-start cycle when section scrolls into view
ScrollTrigger.create({
  trigger: '#how',
  start: 'top 70%',
  onEnter: startJourneyCycle,
  onLeave: () => { clearInterval(journeyTimer); journeyTimer = null; },
  onEnterBack: startJourneyCycle,
  onLeaveBack: () => { clearInterval(journeyTimer); journeyTimer = null; },
});

// Section reveal
gsap.from('#how .section-header', {
  scrollTrigger: { trigger: '#how', start: 'top 80%' },
  opacity: 0, y: 30, duration: 0.6, ease: 'power3.out',
});
gsap.from('.journey-steps .step', {
  scrollTrigger: { trigger: '.journey-steps', start: 'top 80%' },
  opacity: 0, x: -20, duration: 0.5, stagger: 0.1, ease: 'power2.out',
});
gsap.from('.tg-phone', {
  scrollTrigger: { trigger: '.tg-phone', start: 'top 85%' },
  opacity: 0, y: 30, duration: 0.7, ease: 'power3.out',
});
```

- [ ] **Step 4: Verify in browser**

Scroll to section. Expected: steps on left, Telegram mockup on right. After 2.5s the steps cycle automatically. Clicking a step switches the mockup messages with a fade animation.

- [ ] **Step 5: Commit**

```bash
git add static/landing/index.html
git commit -m "feat: landing — user journey section with animated Telegram mockup"
```

---

## Task 5: Features Section

**Files:**
- Modify: `static/landing/index.html`

- [ ] **Step 1: Add features CSS**

```css
/* ── Features ── */
#features { scroll-margin-top: 80px; }
.features-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
.feature-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: 24px;
  transition: border-color 0.25s, transform 0.25s, box-shadow 0.25s;
}
.feature-card:hover {
  border-color: var(--border-accent);
  transform: translateY(-4px);
  box-shadow: 0 8px 32px rgba(167,139,250,0.1);
}
.feature-icon {
  width: 44px; height: 44px;
  background: linear-gradient(135deg, rgba(102,126,234,0.18), rgba(118,75,162,0.18));
  border: 1px solid rgba(167,139,250,0.2);
  border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 20px;
  margin-bottom: 16px;
}
.feature-card h4 { font-size: 15px; font-weight: 600; margin-bottom: 6px; }
.feature-card p { font-size: 13px; color: var(--text-muted); line-height: 1.55; }
```

- [ ] **Step 2: Add features HTML (after journey `</section>`, before `<script>`)**

```html
<hr class="divider">

<section class="section-wrap" id="features">
  <div class="section-header">
    <div class="section-label">Преимущества</div>
    <h2>Почему MTProto Keys</h2>
    <p>Технология, которой доверяют тысячи пользователей</p>
  </div>
  <div class="features-grid">
    <div class="feature-card">
      <div class="feature-icon">📱</div>
      <h4>3 устройства</h4>
      <p>Один ключ работает на телефоне, планшете и компьютере одновременно</p>
    </div>
    <div class="feature-card">
      <div class="feature-icon">⚡</div>
      <h4>Авто-переключение</h4>
      <p>При падении сервера автоматически подключается к резервному узлу</p>
    </div>
    <div class="feature-card">
      <div class="feature-icon">🔒</div>
      <h4>FakeTLS маскировка</h4>
      <p>Трафик выглядит как обычный HTTPS — провайдер не видит Telegram</p>
    </div>
    <div class="feature-card">
      <div class="feature-icon">🌍</div>
      <h4>Несколько серверов</h4>
      <p>Ключ реплицируется на все узлы сети одновременно</p>
    </div>
    <div class="feature-card">
      <div class="feature-icon">🤖</div>
      <h4>Всё в боте</h4>
      <p>Никаких сторонних приложений — управление прямо в Telegram</p>
    </div>
    <div class="feature-card">
      <div class="feature-icon">💳</div>
      <h4>Удобная оплата</h4>
      <p>YuKassa или Telegram Stars — как удобнее</p>
    </div>
  </div>
</section>
```

- [ ] **Step 3: Add scroll animation (inside `<script>`)**

```js
gsap.from('#features .section-header', {
  scrollTrigger: { trigger: '#features', start: 'top 80%' },
  opacity: 0, y: 30, duration: 0.6, ease: 'power3.out',
});
gsap.from('.feature-card', {
  scrollTrigger: { trigger: '.features-grid', start: 'top 85%' },
  opacity: 0, y: 30, scale: 0.97,
  duration: 0.5, stagger: 0.08, ease: 'power2.out',
});
```

- [ ] **Step 4: Verify in browser**

Scroll to features. Expected: 3×2 card grid, each card fades+scales in with a stagger. Hovering a card lifts it with a glow border.

- [ ] **Step 5: Commit**

```bash
git add static/landing/index.html
git commit -m "feat: landing — features section"
```

---

## Task 6: Pricing Section

**Files:**
- Modify: `static/landing/index.html`

- [ ] **Step 1: Add pricing CSS**

```css
/* ── Pricing ── */
#pricing { scroll-margin-top: 80px; }
.pricing-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  align-items: start;
}
.price-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 28px 24px;
  position: relative;
}
.price-card.featured {
  background: linear-gradient(160deg, rgba(102,126,234,0.12), rgba(118,75,162,0.08));
  border-color: var(--border-accent);
}
.price-badge {
  position: absolute;
  top: -13px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--grad-btn);
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  padding: 3px 14px;
  border-radius: 20px;
  white-space: nowrap;
  letter-spacing: 0.5px;
}
.price-label { font-size: 12px; color: var(--text-muted); margin-bottom: 8px; }
.price-amount {
  font-size: 42px;
  font-weight: 800;
  background: var(--grad-text);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  line-height: 1;
  margin-bottom: 4px;
}
.price-period { font-size: 12px; color: var(--text-dim); margin-bottom: 22px; }
.price-features { display: flex; flex-direction: column; gap: 9px; margin-bottom: 24px; }
.price-features li {
  font-size: 13px;
  color: rgba(255,255,255,0.6);
  display: flex;
  align-items: center;
  gap: 8px;
}
.price-features li::before {
  content: '✓';
  color: var(--accent);
  font-weight: 700;
  flex-shrink: 0;
}
.price-btn {
  width: 100%;
  padding: 12px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  transition: opacity 0.2s, transform 0.2s;
}
.price-btn:hover { opacity: 0.85; transform: translateY(-1px); }
.price-btn.primary {
  background: var(--grad-btn);
  color: #fff;
}
.price-btn.outline {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-muted);
}
```

- [ ] **Step 2: Add pricing HTML**

```html
<hr class="divider">

<section class="section-wrap" id="pricing">
  <div class="section-header">
    <div class="section-label">Тарифы</div>
    <h2>Просто и честно</h2>
    <p>Один тариф, два способа оплаты</p>
  </div>
  <div class="pricing-grid">
    <div class="price-card">
      <div class="price-label">Пробный период</div>
      <div class="price-amount">0₽</div>
      <div class="price-period">первые 7 дней</div>
      <ul class="price-features">
        <li>Полный доступ к сервису</li>
        <li>3 устройства</li>
        <li>Без привязки карты</li>
      </ul>
      <a href="https://t.me/mtproto_keys_bot" target="_blank" rel="noopener">
        <button class="price-btn outline">Попробовать бесплатно</button>
      </a>
    </div>
    <div class="price-card featured">
      <div class="price-badge">Популярный</div>
      <div class="price-label">Месячная подписка</div>
      <div class="price-amount">99₽</div>
      <div class="price-period">в месяц через YuKassa</div>
      <ul class="price-features">
        <li>Все серверы</li>
        <li>3 устройства</li>
        <li>Автопродление ключа</li>
        <li>Уведомления об истечении</li>
      </ul>
      <a href="https://t.me/mtproto_keys_bot" target="_blank" rel="noopener">
        <button class="price-btn primary">Оплатить картой</button>
      </a>
    </div>
    <div class="price-card">
      <div class="price-label">Telegram Stars</div>
      <div class="price-amount">80★</div>
      <div class="price-period">в месяц</div>
      <ul class="price-features">
        <li>Все серверы</li>
        <li>3 устройства</li>
        <li>Оплата внутри Telegram</li>
      </ul>
      <a href="https://t.me/mtproto_keys_bot" target="_blank" rel="noopener">
        <button class="price-btn outline">Оплатить Stars</button>
      </a>
    </div>
  </div>
</section>
```

- [ ] **Step 3: Add scroll animation**

```js
gsap.from('#pricing .section-header', {
  scrollTrigger: { trigger: '#pricing', start: 'top 80%' },
  opacity: 0, y: 30, duration: 0.6, ease: 'power3.out',
});
gsap.from('.price-card', {
  scrollTrigger: { trigger: '.pricing-grid', start: 'top 85%' },
  opacity: 0, y: 40, duration: 0.6, stagger: 0.12, ease: 'power3.out',
});
```

- [ ] **Step 4: Verify in browser**

Expected: 3 pricing cards, center one elevated with badge "Популярный" and stronger border. All buttons link to @mtproto_keys_bot.

- [ ] **Step 5: Commit**

```bash
git add static/landing/index.html
git commit -m "feat: landing — pricing section"
```

---

## Task 7: Referral Section

**Files:**
- Modify: `static/landing/index.html`

- [ ] **Step 1: Add referral CSS**

```css
/* ── Referral ── */
#referral { scroll-margin-top: 80px; }
.referral-card {
  background: linear-gradient(160deg, rgba(102,126,234,0.09), rgba(118,75,162,0.06));
  border: 1px solid rgba(167,139,250,0.18);
  border-radius: 24px;
  padding: 52px 48px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 56px;
  align-items: center;
}
.ref-steps { display: flex; flex-direction: column; gap: 22px; }
.ref-step { display: flex; align-items: flex-start; gap: 16px; }
.ref-num {
  width: 36px; height: 36px; min-width: 36px;
  background: var(--grad-btn);
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 700;
  flex-shrink: 0;
}
.ref-step p { font-size: 14px; color: rgba(255,255,255,0.65); line-height: 1.5; padding-top: 6px; }
.ref-step p strong { color: var(--text); }
.ref-visual { text-align: center; }
.ref-counter {
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 28px 24px;
  display: inline-block;
  min-width: 200px;
}
.ref-counter-label {
  font-size: 11px;
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 16px;
}
.ref-dots {
  display: flex;
  gap: 10px;
  justify-content: center;
  margin-bottom: 18px;
}
.ref-dot {
  width: 30px; height: 30px;
  border-radius: 50%;
  border: 2px solid rgba(167,139,250,0.25);
  display: flex; align-items: center; justify-content: center;
  font-size: 12px;
  color: var(--text-dim);
  transition: background 0.4s, border-color 0.4s, color 0.4s;
}
.ref-dot.filled {
  background: var(--grad-btn);
  border-color: transparent;
  color: #fff;
  font-size: 13px;
}
.ref-reward {
  display: inline-block;
  font-size: 12px;
  background: rgba(167,139,250,0.1);
  border: 1px solid var(--border-accent);
  color: #c4b5fd;
  padding: 6px 16px;
  border-radius: 20px;
}
```

- [ ] **Step 2: Add referral HTML**

```html
<hr class="divider">

<section class="section-wrap" id="referral">
  <div class="section-header">
    <div class="section-label">Реферальная программа</div>
    <h2>Приглашай — получай бесплатно</h2>
    <p>Каждый друг приближает тебя к бесплатному месяцу</p>
  </div>
  <div class="referral-card">
    <div class="ref-steps">
      <div class="ref-step">
        <div class="ref-num">1</div>
        <p>Получаешь <strong>свою реферальную ссылку</strong> в боте</p>
      </div>
      <div class="ref-step">
        <div class="ref-num">2</div>
        <p>Друг переходит и получает <strong>14 дней бесплатно</strong></p>
      </div>
      <div class="ref-step">
        <div class="ref-num">3</div>
        <p>После <strong>5 активных приглашений</strong> — ты получаешь 14 дней в подарок</p>
      </div>
    </div>
    <div class="ref-visual">
      <div class="ref-counter">
        <div class="ref-counter-label">Прогресс рефералов</div>
        <div class="ref-dots">
          <div class="ref-dot" id="dot-0">1</div>
          <div class="ref-dot" id="dot-1">2</div>
          <div class="ref-dot" id="dot-2">3</div>
          <div class="ref-dot" id="dot-3">4</div>
          <div class="ref-dot" id="dot-4">5</div>
        </div>
        <div class="ref-reward">🎁 5 друзей → ключ бесплатно</div>
      </div>
    </div>
  </div>
</section>
```

- [ ] **Step 3: Add scroll animation with dots filling one-by-one**

```js
gsap.from('#referral .section-header', {
  scrollTrigger: { trigger: '#referral', start: 'top 80%' },
  opacity: 0, y: 30, duration: 0.6, ease: 'power3.out',
});
gsap.from('.referral-card', {
  scrollTrigger: { trigger: '.referral-card', start: 'top 85%' },
  opacity: 0, y: 30, duration: 0.7, ease: 'power3.out',
});

// Dots fill one by one when section enters view
ScrollTrigger.create({
  trigger: '.ref-dots',
  start: 'top 85%',
  once: true,
  onEnter: () => {
    [0,1,2,3,4].forEach((i) => {
      gsap.delayedCall(i * 0.25, () => {
        document.getElementById('dot-' + i).classList.add('filled');
        document.getElementById('dot-' + i).textContent = '✓';
      });
    });
  },
});
```

- [ ] **Step 4: Verify in browser**

Scroll to referral section. Expected: 3 steps on left, progress counter on right. When scrolled into view, dots fill one by one from left to right with ✓ marks.

- [ ] **Step 5: Commit**

```bash
git add static/landing/index.html
git commit -m "feat: landing — referral section with animated progress dots"
```

---

## Task 8: FAQ Section

**Files:**
- Modify: `static/landing/index.html`

- [ ] **Step 1: Add FAQ CSS**

```css
/* ── FAQ ── */
#faq { scroll-margin-top: 80px; }
.faq-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-width: 720px;
  margin: 0 auto;
}
.faq-item {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
  transition: border-color 0.25s;
}
.faq-item.open { border-color: var(--border-accent); }
.faq-q {
  padding: 18px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  gap: 12px;
  user-select: none;
}
.faq-icon {
  color: var(--accent);
  font-size: 20px;
  line-height: 1;
  transition: transform 0.25s;
  flex-shrink: 0;
}
.faq-item.open .faq-icon { transform: rotate(45deg); }
.faq-a {
  max-height: 0;
  overflow: hidden;
  transition: max-height 0.35s ease, padding 0.25s;
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.65;
  padding: 0 20px;
}
.faq-item.open .faq-a {
  max-height: 200px;
  padding: 0 20px 18px;
}
```

- [ ] **Step 2: Add FAQ HTML**

```html
<hr class="divider">

<section class="section-wrap" id="faq">
  <div class="section-header">
    <div class="section-label">FAQ</div>
    <h2>Частые вопросы</h2>
  </div>
  <div class="faq-list">
    <div class="faq-item">
      <div class="faq-q" onclick="toggleFaq(this)">
        Что такое MTProto-прокси?
        <span class="faq-icon">+</span>
      </div>
      <div class="faq-a">MTProto — протокол Telegram. Прокси-сервер маскирует трафик под обычный HTTPS, поэтому интернет-провайдер не видит, что вы используете Telegram.</div>
    </div>
    <div class="faq-item">
      <div class="faq-q" onclick="toggleFaq(this)">
        Почему Telegram заблокирован?
        <span class="faq-icon">+</span>
      </div>
      <div class="faq-a">В ряде стран и корпоративных сетей Telegram ограничен на уровне DPI-фильтрации. MTProto-прокси делает трафик неотличимым от обычного HTTPS и обходит это ограничение.</div>
    </div>
    <div class="faq-item">
      <div class="faq-q" onclick="toggleFaq(this)">
        Сколько устройств можно подключить?
        <span class="faq-icon">+</span>
      </div>
      <div class="faq-a">Один ключ работает одновременно на 3 устройствах — телефон, планшет, компьютер в любой комбинации.</div>
    </div>
    <div class="faq-item">
      <div class="faq-q" onclick="toggleFaq(this)">
        Что будет когда закончится подписка?
        <span class="faq-icon">+</span>
      </div>
      <div class="faq-a">Бот пришлёт уведомление за сутки и за час до истечения. После окончания ключ деактивируется, но данные сохраняются — продлить можно в любой момент через бота.</div>
    </div>
    <div class="faq-item">
      <div class="faq-q" onclick="toggleFaq(this)">
        Это безопасно?
        <span class="faq-icon">+</span>
      </div>
      <div class="faq-a">Да. MTProto-прокси не расшифровывает ваш трафик — он только передаёт уже зашифрованные Telegram-пакеты. Переписка остаётся полностью приватной.</div>
    </div>
  </div>
</section>
```

- [ ] **Step 3: Add FAQ JS toggle + scroll animation**

```js
function toggleFaq(btn) {
  const item = btn.parentElement;
  const isOpen = item.classList.contains('open');
  // Close all
  document.querySelectorAll('.faq-item.open').forEach(el => el.classList.remove('open'));
  // Open clicked (if it was closed)
  if (!isOpen) item.classList.add('open');
}

gsap.from('#faq .section-header', {
  scrollTrigger: { trigger: '#faq', start: 'top 80%' },
  opacity: 0, y: 30, duration: 0.6, ease: 'power3.out',
});
gsap.from('.faq-item', {
  scrollTrigger: { trigger: '.faq-list', start: 'top 85%' },
  opacity: 0, y: 20, duration: 0.45, stagger: 0.08, ease: 'power2.out',
});
```

- [ ] **Step 4: Verify in browser**

Scroll to FAQ. Expected: 5 items, clicking opens one and closes others. Icon rotates 45° when open. Smooth max-height transition.

- [ ] **Step 5: Commit**

```bash
git add static/landing/index.html
git commit -m "feat: landing — FAQ accordion"
```

---

## Task 9: Footer

**Files:**
- Modify: `static/landing/index.html`

- [ ] **Step 1: Add footer CSS**

```css
/* ── Footer ── */
.footer {
  border-top: 1px solid rgba(255,255,255,0.05);
  padding: 28px 40px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: var(--text-dim);
  font-size: 12px;
  flex-wrap: wrap;
  gap: 12px;
}
.footer-logo { font-weight: 700; color: rgba(255,255,255,0.45); }
.footer-logo span { color: var(--accent); }
.footer a { color: var(--text-dim); transition: color 0.2s; }
.footer a:hover { color: var(--accent); }
```

- [ ] **Step 2: Add footer HTML (after last `</section>`, before `<script>`)**

```html
<footer class="footer">
  <div class="footer-logo">MTProto <span>Keys</span></div>
  <div>mtprotokeys.ru · 2026</div>
  <a href="https://t.me/mtproto_keys_bot" target="_blank" rel="noopener">@mtproto_keys_bot</a>
</footer>
```

- [ ] **Step 3: Verify in browser**

Expected: minimal 3-column footer at the bottom. Bot username is clickable.

- [ ] **Step 4: Commit**

```bash
git add static/landing/index.html
git commit -m "feat: landing — footer"
```

---

## Task 10: Mobile Responsiveness

**Files:**
- Modify: `static/landing/index.html`

- [ ] **Step 1: Add media queries (at end of `<style>`)**

```css
/* ── Mobile ── */
@media (max-width: 768px) {
  :root { --section-pad: 60px 20px; }

  .nav { padding: 14px 20px; }
  .nav-links { display: none; }

  .hero h1 { letter-spacing: -2px; }

  .journey-grid {
    grid-template-columns: 1fr;
  }
  .tg-phone { max-width: 100%; }

  .features-grid { grid-template-columns: 1fr 1fr; }

  .pricing-grid { grid-template-columns: 1fr; }

  .referral-card {
    grid-template-columns: 1fr;
    gap: 36px;
    padding: 36px 24px;
  }

  .footer { flex-direction: column; text-align: center; }

  .divider { margin: 0 20px; }
}

@media (max-width: 480px) {
  .features-grid { grid-template-columns: 1fr; }
}
```

- [ ] **Step 2: Verify on mobile viewport**

In browser DevTools, switch to mobile viewport (375px). Expected:
- Navbar hides nav links, keeps logo + CTA button
- Hero headline wraps cleanly
- Journey section stacks vertically (steps on top, phone below)
- Features 1 column on 480px, 2 columns on 768px
- Pricing stacks to 1 column
- Referral card stacks vertically

- [ ] **Step 3: Commit**

```bash
git add static/landing/index.html
git commit -m "feat: landing — mobile responsiveness"
```

---

## Task 11: Nginx Configuration

**Files:**
- Modify: `nginx/nginx.conf`

Add a new server block for `mtprotokeys.ru` that serves `index.html` as the root. The file is mounted at `/var/www/landing/` inside the Nginx container.

- [ ] **Step 1: Add HTTP → HTTPS redirect block for mtprotokeys.ru**

In `nginx/nginx.conf`, inside the existing `server { listen 80; ... }` block, add `mtprotokeys.ru` to the `server_name` line:

```nginx
server {
    listen 80;
    server_name beatvault.ru flower.beatvault.ru mtprotokeys.ru;
    ...
```

- [ ] **Step 2: Add HTTPS server block for mtprotokeys.ru (after the `flower.beatvault.ru` block)**

```nginx
server {
    listen 443 ssl;
    http2 on;
    server_name mtprotokeys.ru;
    server_tokens off;

    ssl_certificate     /etc/nginx/ssl/live/mtprotokeys.ru/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/live/mtprotokeys.ru/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    client_max_body_size 1M;

    # Serve landing page
    root /var/www/landing;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
        expires 1h;
        add_header Cache-Control "public, must-revalidate";
    }

    # Cache static assets aggressively
    location ~* \.(css|js|woff2?|ttf|svg|ico|png|jpg|webp)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

- [ ] **Step 3: Mount the landing directory in docker-compose.yml**

In `docker-compose.yml`, find the `nginx` service volumes section and add:

```yaml
- ./static/landing:/var/www/landing:ro
```

Do the same in `docker-compose.local.yml`.

- [ ] **Step 4: Verify nginx config syntax**

```bash
docker run --rm -v $(pwd)/nginx/nginx.conf:/etc/nginx/nginx.conf:ro nginx nginx -t
```

Expected output: `nginx: configuration file /etc/nginx/nginx.conf test is successful`

- [ ] **Step 5: Commit**

```bash
git add nginx/nginx.conf docker-compose.yml docker-compose.local.yml
git commit -m "feat: landing — nginx config for mtprotokeys.ru"
```

---

## Task 12: Final Polish Pass

**Files:**
- Modify: `static/landing/index.html`

Final visual touches: smooth navbar background on scroll, hero gradient subtle animation, consistent spacing check.

- [ ] **Step 1: Add animated hero gradient (CSS `@keyframes`)**

Add inside `<style>` after hero CSS:

```css
@keyframes gradientShift {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}
.hero-bg {
  animation: gradientShift 6s ease-in-out infinite;
}
```

- [ ] **Step 2: Add scroll-based navbar shadow (inside `<script>`)**

```js
// Navbar: add shadow when scrolled
window.addEventListener('scroll', () => {
  const nav = document.querySelector('.nav');
  nav.style.boxShadow = window.scrollY > 10
    ? '0 1px 20px rgba(0,0,0,0.4)'
    : 'none';
}, { passive: true });
```

- [ ] **Step 3: Verify full page in browser**

Scroll through the entire page and check:
- [ ] All 6 sections present and visually correct
- [ ] No console errors
- [ ] All CTA buttons link to `https://t.me/mtproto_keys_bot`
- [ ] GSAP animations trigger correctly on scroll
- [ ] Journey Telegram mockup cycles automatically and responds to clicks
- [ ] FAQ accordion opens/closes
- [ ] Referral dots animate in
- [ ] Mobile viewport (375px) looks correct

- [ ] **Step 4: Final commit**

```bash
git add static/landing/index.html
git commit -m "feat: landing — final polish, gradient animation, navbar scroll shadow"
```

---

## Self-Review Notes

**Spec coverage check:**
- ✅ Navbar — Task 2
- ✅ Hero ultra-minimal — Task 3
- ✅ User journey + Telegram mockup animation — Task 4
- ✅ Features 6-card grid — Task 5
- ✅ Pricing 3 cards (0₽ / 99₽ / 80★) — Task 6
- ✅ Referral section + progress dots — Task 7
- ✅ FAQ accordion — Task 8
- ✅ Footer — Task 9
- ✅ GSAP ScrollTrigger animations on all sections — Tasks 4–9 + 12
- ✅ Hero GSAP entry animation — Task 3
- ✅ Mobile responsiveness — Task 10
- ✅ Nginx config for mtprotokeys.ru — Task 11
- ✅ "7 дней бесплатно" throughout (not 30) — Tasks 3, 4, 6

**Type consistency:** All JS functions (`setStep`, `toggleFaq`, `startJourneyCycle`) defined before use. All DOM IDs (`screen-0..3`, `dot-0..4`, `#how`, `#pricing`, `#referral`, `#faq`) match between HTML and JS.
