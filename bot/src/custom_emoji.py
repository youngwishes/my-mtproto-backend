from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Awaitable, Callable, final

from aiogram.client.session.middlewares.base import BaseRequestMiddleware

if TYPE_CHECKING:
    from aiogram import Bot
    from aiogram.methods import TelegramMethod


_CUSTOM_EMOJI: dict[str, tuple[str, str]] = {
    "👋": ("5472055112702629499", "👋"),
    "👇": ("5470177992950946662", "👇"),
    "🔙": ("5393368163628905240", "⬅️"),
    "⚡️": ("5431449001532594346", "⚡️"),
    "⚡": ("5431449001532594346", "⚡️"),
    "🌐": ("5399898266265475100", "🌍"),
    "🔁": ("5264727218734524899", "🔄"),
    "🎁": ("5199749070830197566", "🎁"),
    "🎉": ("5436040291507247633", "🎉"),
    "📝": ("5334882760735598374", "📝"),
    "⏳": ("5451732530048802485", "⏳"),
    "🤝": ("5357080225463149588", "🤝"),
    "📡": ("5357163595073356754", "🛜"),
    "🔄": ("5264727218734524899", "🔄"),
    "✅": ("5427009714745517609", "✅"),
    "❓": ("5467666648263564704", "❓"),
    "🔒": ("5472308992514464048", "🔐"),
    "📱": ("5407025283456835913", "📱"),
    "🔧": ("5355005786323976431", "🔧"),
    "⭐️": ("5435957248314579621", "⭐️"),
    "⭐": ("5435957248314579621", "⭐️"),
    "👥": ("5372926953978341366", "👥"),
    "💳": ("5445353829304387411", "💳"),
    "📅": ("5431897022456145283", "📆"),
    "💎": ("5471952986970267163", "💎"),
    "🔐": ("5472308992514464048", "🔐"),
    "🔗": ("5375129357373165375", "🔗"),
    "⚙️": ("5357427684022453456", "⚙️"),
    "⚙": ("5357427684022453456", "⚙️"),
    "🧹": ("5188365693803830912", "🧽"),
    "💬": ("5465300082628763143", "💬"),
    "📣": ("5469903029144657419", "📣"),
    "📢": ("5469903029144657419", "📣"),
    "📜": ("5226512880362332956", "📖"),
    "📖": ("5226512880362332956", "📖"),
    "🔑": ("5330115548900501467", "🔑"),
    "🎡": ("5226711870492126219", "🎡"),
    "⚠️": ("5467519850576354798", "❕"),
    "⚠": ("5467519850576354798", "❕"),
    "👉": ("5471978009449731768", "👉"),
    "✨": ("5472164874886846699", "✨"),
    "🔥": ("5420315771991497307", "🔥"),
    "👀": ("5424885441100782420", "👀"),
    "🗓": ("5431897022456145283", "📆"),
    "📩": ("5406631276042002796", "📨"),
    "❌": ("5465665476971471368", "❌"),
    "🇫🇮": ("5382151560182642075", "🇫🇮"),
    "🇰🇿": ("5228718354658769982", "🇰🇿"),
    "🇺🇸": ("5202021044105257611", "🇺🇸"),
    "🇳🇱": ("5411124743841524806", "🇳🇱"),
    "🇩🇪": ("5409360418520967565", "🇩🇪"),
}

_EMOJI_RE = re.compile(
    "|".join(re.escape(emoji) for emoji in sorted(_CUSTOM_EMOJI, key=len, reverse=True))
)
_PROTECTED_HTML_RE = re.compile(
    r"(<tg-emoji\b[^>]*>.*?</tg-emoji>|<code\b[^>]*>.*?</code>|"
    r"<pre\b[^>]*>.*?</pre>)",
    re.DOTALL,
)


def _customize_text(text: str) -> str:
    parts = _PROTECTED_HTML_RE.split(text)
    for index in range(0, len(parts), 2):
        parts[index] = _EMOJI_RE.sub(_render_emoji, parts[index])
    return "".join(parts)


def _render_emoji(match: re.Match[str]) -> str:
    emoji_id, fallback = _CUSTOM_EMOJI[match.group(0)]
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


def _customize_markup(markup: Any) -> None:
    rows = getattr(markup, "inline_keyboard", None)
    if rows is None:
        return
    for row in rows:
        for button in row:
            if button.icon_custom_emoji_id is not None:
                continue
            match = _EMOJI_RE.search(button.text)
            if match is None:
                continue
            emoji_id, _ = _CUSTOM_EMOJI[match.group(0)]
            button.text = (
                button.text[: match.start()] + button.text[match.end() :]
            ).strip()
            button.icon_custom_emoji_id = emoji_id


@final
class PremiumEmojiMiddleware(BaseRequestMiddleware):
    async def __call__(
        self,
        make_request: Callable[[Bot, TelegramMethod[Any]], Awaitable[Any]],
        bot: Bot,
        method: TelegramMethod[Any],
    ) -> Any:
        premium_emoji = method.model_extra.pop("premium_emoji", True)
        if premium_emoji:
            text = getattr(method, "text", None)
            if isinstance(text, str):
                method.text = _customize_text(text)
            reply_markup = getattr(method, "reply_markup", None)
            if reply_markup is not None:
                _customize_markup(reply_markup)
        return await make_request(bot, method)
