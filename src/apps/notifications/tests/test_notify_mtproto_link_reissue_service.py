from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.notifications.services import get_notify_mtproto_link_reissue_service
from apps.notifications.services.notify_mtproto_link_reissue_service import (
    NotifyMTPRotoLinkReissueService,
)
from apps.vds.models import MTPRotoKey
from apps.vds.tests.factories import MTPRotoKeyFactory

_SERVICE_MODULE = "apps.notifications.services.notify_mtproto_link_reissue_service"
_MESSAGE_TEXT = (
    "⚠️ <b>Пожалуйста, обновите ссылки MTProxy</b>\n\n"
    "Мы обновили настройки подключения, чтобы сохранить стабильную работу "
    "сервиса.\n\n"
    "Нажмите кнопку ниже и подтвердите перевыпуск. После этого добавьте новые "
    "ссылки в Telegram, а старые можно удалить.\n\n"
    "Это займёт меньше минуты."
)


def _user(telegram_id: int) -> SimpleNamespace:
    return SimpleNamespace(username=str(telegram_id))


def _assert_reissue_payload(test_case: SimpleTestCase, telegram_call) -> None:
    test_case.assertEqual(telegram_call.kwargs["text"], _MESSAGE_TEXT)
    keyboard = telegram_call.kwargs["markup"].keyboard
    test_case.assertEqual(len(keyboard), 1)
    test_case.assertEqual(len(keyboard[0]), 1)
    button = keyboard[0][0]
    test_case.assertEqual(button.text, "🔄 Перевыпустить ссылки")
    test_case.assertEqual(button.callback_data, "update_link")
    test_case.assertIsNone(button.url)


class TestNotifyMTPRotoLinkReissueService(SimpleTestCase):
    def _service(self, *, selector=None, sender=None, sleeper=None):
        return NotifyMTPRotoLinkReissueService(
            get_recipients=selector or mock.Mock(return_value=[]),
            send_message=sender or mock.Mock(),
            sleep=sleeper or mock.Mock(),
            admin_telegram_id=999,
        )

    def test_default_and_true_send_only_an_exact_preview_to_admin(self) -> None:
        for call_kwargs in ({}, {"preview": True}):
            with self.subTest(call_kwargs=call_kwargs):
                selector = mock.Mock(return_value=[_user(101)])
                sender = mock.Mock()

                self._service(selector=selector, sender=sender)(**call_kwargs)

                selector.assert_not_called()
                sender.assert_called_once()
                preview_call = sender.call_args
                self.assertEqual(preview_call.kwargs["chat_id"], 999)
                _assert_reissue_payload(self, preview_call)

    def test_false_sends_the_same_payload_once_to_each_recipient(self) -> None:
        sender = mock.Mock()
        service = self._service(
            selector=mock.Mock(return_value=[_user(101), _user(102)]),
            sender=sender,
        )

        service(preview=False)

        self.assertEqual(
            [call.kwargs["chat_id"] for call in sender.call_args_list],
            [101, 102, 999],
        )
        _assert_reissue_payload(self, sender.call_args_list[0])
        _assert_reissue_payload(self, sender.call_args_list[1])
        self.assertEqual(
            sender.call_args_list[2].kwargs["text"],
            "Рассылка завершена. Уведомлено пользователей: 2",
        )

    def test_sleeps_before_later_attempts_and_continues_after_error(self) -> None:
        events: list[tuple[str, int | float]] = []

        def send_message(*, chat_id: int, text: str, markup=None) -> None:
            events.append(("send", chat_id))
            if chat_id == 101:
                raise RuntimeError("blocked")

        def sleep(delay: float) -> None:
            events.append(("sleep", delay))

        service = self._service(
            selector=mock.Mock(return_value=[_user(101), _user(102), _user(103)]),
            sender=send_message,
            sleeper=sleep,
        )

        service(preview=False)

        self.assertEqual(
            events,
            [
                ("send", 101),
                ("sleep", 0.5),
                ("send", 102),
                ("sleep", 0.5),
                ("send", 103),
                ("send", 999),
            ],
        )

    def test_delivery_error_is_not_retried_or_reported_separately(self) -> None:
        def deliver(*, chat_id: int, text: str, markup=None) -> None:
            if chat_id == 101:
                raise RuntimeError("blocked")

        sender = mock.Mock(side_effect=deliver)
        service = self._service(
            selector=mock.Mock(return_value=[_user(101), _user(102)]),
            sender=sender,
        )

        service(preview=False)

        self.assertEqual(
            [call.kwargs["chat_id"] for call in sender.call_args_list],
            [101, 102, 999],
        )
        self.assertEqual(
            sender.call_args_list[-1].kwargs["text"],
            "Рассылка завершена. Уведомлено пользователей: 1",
        )

    def test_empty_or_fully_failed_pass_reports_zero(self) -> None:
        for recipients in ([], [_user(101), _user(102)]):
            with self.subTest(recipient_count=len(recipients)):
                def deliver(*, chat_id: int, text: str, markup=None) -> None:
                    if chat_id != 999:
                        raise RuntimeError("blocked")

                sender = mock.Mock(side_effect=deliver)
                service = self._service(
                    selector=mock.Mock(return_value=recipients),
                    sender=sender,
                )

                service(preview=False)

                self.assertEqual(
                    sender.call_args_list[-1].kwargs["text"],
                    "Рассылка завершена. Уведомлено пользователей: 0",
                )


@override_settings(MY_TELEGRAM_ID=999)
class TestGetNotifyMTPRotoLinkReissueService(SimpleTestCase):
    @mock.patch(f"{_SERVICE_MODULE}.time.sleep")
    @mock.patch(f"{_SERVICE_MODULE}.send_telegram_message")
    @mock.patch(f"{_SERVICE_MODULE}.get_mtproto_link_reissue_recipients")
    def test_wires_selector_transport_sleep_and_admin_id(
        self,
        selector: mock.Mock,
        sender: mock.Mock,
        sleeper: mock.Mock,
    ) -> None:
        selector.return_value = [_user(101), _user(102)]

        service = get_notify_mtproto_link_reissue_service()
        service(preview=False)

        selector.assert_called_once_with()
        sleeper.assert_called_once_with(0.5)
        self.assertEqual(
            [call.kwargs["chat_id"] for call in sender.call_args_list],
            [101, 102, 999],
        )


class TestNotifyMTPRotoLinkReissueServiceKeyState(TestCase):
    def setUp(self) -> None:
        self.key = MTPRotoKeyFactory(expired_date=timezone.now())

    def _key_state(self) -> list[dict]:
        return list(MTPRotoKey.objects.order_by("pk").values())

    def _service(self, *, sender: mock.Mock) -> NotifyMTPRotoLinkReissueService:
        return NotifyMTPRotoLinkReissueService(
            get_recipients=lambda: [self.key.user],
            send_message=sender,
            sleep=mock.Mock(),
            admin_telegram_id=999,
        )

    def test_preview_does_not_change_keys(self) -> None:
        before = self._key_state()

        self._service(sender=mock.Mock())()

        self.assertEqual(self._key_state(), before)

    def test_successful_pass_does_not_change_keys(self) -> None:
        before = self._key_state()

        self._service(sender=mock.Mock())(preview=False)

        self.assertEqual(self._key_state(), before)

    def test_failed_delivery_does_not_change_keys(self) -> None:
        def deliver(*, chat_id: int, text: str, markup=None) -> None:
            if chat_id != 999:
                raise RuntimeError("blocked")

        before = self._key_state()

        self._service(sender=mock.Mock(side_effect=deliver))(preview=False)

        self.assertEqual(self._key_state(), before)
