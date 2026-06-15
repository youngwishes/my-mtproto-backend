from src.enums import FreeAvailable

SITE_URL = "https://mtprotokeys.ru"
SUPPORT_URL = "https://t.me/mtproto_keys"
TERMS_URL = "https://mtprotokeys.ru/terms"
PRIVACY_URL = "https://mtprotokeys.ru/privacy"

_WELCOME_BODY = """
<b>⚡️ MTProto Keys Bot</b>

- 🌐 Не один сервер, а целая <b>сеть</b>
- 🔁 Упал один — <b>всегда есть резерв</b>
- 🌍 Серверы в <b>разных странах</b>
- 📱 Одна ссылка на <b>3 устройства</b>

👇 Жми «Ускорить» и подключайся!
"""

WELCOME_TEXT_MONTH = _WELCOME_BODY + "\nПервый месяц — бесплатно."

WELCOME_TEXT_WEEK = _WELCOME_BODY + "\nПервая неделя — бесплатно."

WELCOME_TEXT_TWO_WEEK = (
    _WELCOME_BODY + "\nВы пришли по приглашению — первые две недели бесплатно."
)

WELCOME_TEXT_NOT_FREE = _WELCOME_BODY

FREE_AVAILABLE_TEXT_MAPPING = {
    FreeAvailable.MONTH: WELCOME_TEXT_MONTH,
    FreeAvailable.WEEK: WELCOME_TEXT_WEEK,
    FreeAvailable.TWO_WEEK: WELCOME_TEXT_TWO_WEEK,
    FreeAvailable.NOT_AVAILABLE: WELCOME_TEXT_NOT_FREE,
}


KEY_GENERATED_TEXT = """
🎉 <b>Твой персональный ключ готов!</b>

📝 <b>Как активировать:</b>
1. Нажми «Мои серверы» ниже
2. Подключи <b>все серверы</b> в Telegram — при падении одного он автоматически переключится на другой

⏳ Действительно до: <b>{expired_date}</b>

<i>🤝 Подпишись на наш канал — там все новости: @mtproto_keys</i>
"""

MY_SERVERS_TEXT = """
📡 <b>Твои серверы</b>

Подключи все серверы в Telegram — при отказе одного Telegram автоматически переключится на другой.

⏳ Ключ действителен до: <b>{expired_date}</b>

<i>👇 Нажми на каждый сервер чтобы добавить его</i>
"""

FAQ_TEXT = """
❓ <b>Часто задаваемые вопросы:</b>

<b>1. Это законно?</b>
✅ Да, MTPRoto — это легальный прокси-сервис, <b>встроенный</b> в эко-систему Telegram.

<b>2. А если не заработает?</b>
🛠 Мы даем бесплатную <b>неделю</b> на тест. Не понравится — просто не покупай.

<b>3. На сколько устройств хватит?</b>
📱 Один ключ работает на трех устройствах (для связки — телефон + ПК + планшет)

<b>4. Нужно ли что-то устанавливать?</b>
🔧 Нет, только вставить ключ в настройках Telegram

<b>5. Какая скорость?</b>
⚡️ Ограничений нет, только возможности твоего интернета

<b>6. Какие способы оплаты?</b>
💳 Банковская карта, SberPay, ЮMoney, ⭐ Telegram Stars

Остались вопросы? Напиши @mtproto_keys
"""

REFERRAL_CABINET = """
<b>⚡️Твой реферальный кабинет </b>

• Общее количество инвайтов: <b>{total_referrals_count}</b>
• Активированные инвайты: <b>{active_referrals_count}</b>

🔗 Как только количество активированных инвайтов станет равно <b>5</b>, ты сможешь получить бесплатную ссылку <b>сроком действия 2 недели!</b>

👇 <b>Поделиться ссылкой</b>
"""

PAYMENT_METHODS_TEXT = f"""💰 <b>Выберите способ оплаты</b>

• 💳 <b>ЮKassa</b> — 99 ₽/месяц
  Банковская карта, SberPay, ЮMoney

• ⭐ <b>Telegram Stars</b> — 80 ★/месяц
  Оплата прямо в Telegram

<i>Оплачивая, вы принимаете <a href="{TERMS_URL}">Условия</a> и \
<a href="{PRIVACY_URL}">Политику конфиденциальности</a>.</i>
"""
