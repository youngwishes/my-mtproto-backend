from __future__ import annotations

from django.db import models
from django.utils import timezone

from apps.core.models import BaseDjangoModel
from apps.notifications.enums import ContextResolverType, FilterType, MailingStatus


class NotificationTemplate(BaseDjangoModel):
    slug = models.SlugField("Идентификатор", max_length=64, unique=True)
    title = models.CharField("Название", max_length=255)
    text = models.TextField("Текст сообщения (HTML, поддерживает {переменные})")
    button_text = models.CharField(
        "Текст кнопки", max_length=128, blank=True, default="",
    )
    button_url = models.CharField(
        "URL кнопки (поддерживает {переменные})", max_length=512, blank=True, default="",
    )
    button_callback_data = models.CharField(
        "callback_data кнопки", max_length=128, blank=True, default="",
    )
    include_payment_buttons = models.BooleanField(
        "Прикрепить кнопки оплаты", default=False,
    )

    class Meta:
        verbose_name = "Шаблон уведомления"
        verbose_name_plural = "Шаблоны уведомлений"

    def __str__(self) -> str:
        return self.title

    def render(self, context: dict | None = None) -> RenderedMessage:
        from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

        ctx = context or {}
        text = self.text.format(**ctx)
        keyboard_rows: list = []

        if self.button_text and self.button_url:
            keyboard_rows.append(
                [InlineKeyboardButton(
                    text=self.button_text,
                    url=self.button_url.format(**ctx),
                )]
            )
        elif self.button_text and self.button_callback_data:
            keyboard_rows.append(
                [InlineKeyboardButton(
                    text=self.button_text,
                    callback_data=self.button_callback_data,
                )]
            )

        if self.include_payment_buttons:
            keyboard_rows.append(
                [InlineKeyboardButton(
                    text="❤️ Поддержать",
                    callback_data="boost_paid",
                )]
            )

        markup = InlineKeyboardMarkup(keyboard=keyboard_rows) if keyboard_rows else None
        return RenderedMessage(text=text, markup=markup)


class RenderedMessage:
    """Результат рендеринга шаблона."""

    __slots__ = ("text", "markup")

    def __init__(self, text: str, markup=None) -> None:
        self.text = text
        self.markup = markup


class Mailing(BaseDjangoModel):
    template = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.CASCADE,
        verbose_name="Шаблон",
    )
    filter_type = models.IntegerField(
        "Фильтр получателей",
        choices=FilterType.choices(),
    )
    filter_params = models.JSONField(
        "Параметры фильтра", default=dict, blank=True,
    )
    context = models.JSONField(
        "Статический контекст для шаблона", default=dict, blank=True,
    )
    context_resolver = models.IntegerField(
        "Персональный контекст",
        choices=ContextResolverType.choices(),
        default=ContextResolverType.NONE,
    )
    status = models.IntegerField(
        "Статус",
        choices=MailingStatus.choices(),
        default=MailingStatus.DRAFT,
    )
    sent_at = models.DateTimeField("Отправлена", null=True, blank=True)
    sent_count = models.PositiveIntegerField("Отправлено", default=0)
    failed_count = models.PositiveIntegerField("Ошибок", default=0)

    class Meta:
        verbose_name = "Рассылка"
        verbose_name_plural = "Рассылки"

    def __str__(self) -> str:
        return f"{self.template.title} — {self.get_status_display()}"

    def mark_as_sending(self) -> None:
        self.status = MailingStatus.SENDING
        self.save(update_fields=["status"])

    def mark_as_completed(self) -> None:
        self.status = MailingStatus.COMPLETED
        self.sent_at = timezone.now()
        self.save(update_fields=["status", "sent_at"])

    def mark_as_failed(self) -> None:
        self.status = MailingStatus.FAILED
        self.sent_at = timezone.now()
        self.save(update_fields=["status", "sent_at"])

    def mark_as_partially_completed(self) -> None:
        self.status = MailingStatus.PARTIALLY_COMPLETED
        self.sent_at = timezone.now()
        self.save(update_fields=["status", "sent_at"])
