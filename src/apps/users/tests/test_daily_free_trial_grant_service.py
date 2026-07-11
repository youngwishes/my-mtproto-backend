from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.users.exceptions import AlreadyUsedFree
from apps.users.services.daily_free_trial_grant_service import DailyFreeTrialGrantService
from apps.users.services.dtos import IssuedKeyOut


def _user(username: str) -> SimpleNamespace:
    return SimpleNamespace(username=username)


class TestDailyFreeTrialGrantService(SimpleTestCase):
    def _service(
        self,
        *,
        candidates,
        activation=None,
        key=None,
        servers=None,
        sender=None,
    ):
        return DailyFreeTrialGrantService(
            get_candidates=lambda: candidates,
            activate_free_trial=activation
            or mock.Mock(return_value=IssuedKeyOut(expired_date="10.08.26")),
            get_active_key=lambda **_: key or SimpleNamespace(
                get_proxy_link=lambda *, server_name: f"tg://proxy?server={server_name}"
            ),
            get_active_servers=lambda: servers or [],
            send_message=sender or mock.Mock(),
            admin_telegram_id=999,
        )

    def test_activates_at_most_ten_users(self) -> None:
        activation = mock.Mock(return_value=IssuedKeyOut(expired_date="10.08.26"))
        service = self._service(
            candidates=[_user(str(index)) for index in range(12)],
            activation=activation,
        )

        service()

        self.assertEqual(activation.call_count, 10)
        self.assertEqual(
            [call.kwargs["username"] for call in activation.call_args_list],
            [str(index) for index in range(10)],
        )
        self.assertTrue(
            all(
                call.kwargs["notify_on_error"] is False
                for call in activation.call_args_list
            )
        )

    def test_continues_after_activation_error_until_ten_succeed(self) -> None:
        activation = mock.Mock(
            side_effect=[RuntimeError("failure")]
            + [IssuedKeyOut(expired_date="10.08.26")] * 10
        )
        service = self._service(
            candidates=[_user(str(index)) for index in range(12)],
            activation=activation,
        )

        service()

        self.assertEqual(activation.call_count, 11)

    def test_skips_user_already_activated_by_another_run(self) -> None:
        activation = mock.Mock(
            side_effect=[
                AlreadyUsedFree(telegram_id="1"),
                IssuedKeyOut(expired_date="10.08.26"),
            ]
        )
        sender = mock.Mock()
        service = self._service(
            candidates=[_user("1"), _user("2")],
            activation=activation,
            sender=sender,
        )

        service()

        self.assertEqual(activation.call_count, 2)
        self.assertEqual(sender.call_count, 2)  # one user notification and one report

    def test_sends_expiry_and_url_button_for_every_active_server(self) -> None:
        sender = mock.Mock()
        key = SimpleNamespace(
            get_proxy_link=lambda *, server_name: f"tg://proxy?server={server_name}"
        )
        servers = [
            SimpleNamespace(name="de", location="🇩🇪 Germany"),
            SimpleNamespace(name="nl", location="🇳🇱 Netherlands"),
        ]
        service = self._service(
            candidates=[_user("123")], key=key, servers=servers, sender=sender
        )

        service()

        notification = sender.call_args_list[0]
        self.assertEqual(notification.kwargs["chat_id"], 123)
        self.assertEqual(
            notification.kwargs["text"],
            (
                "🎁 <b>Для тебя открыт бесплатный доступ!</b>\n\n"
                "Теперь Telegram может работать быстрее и стабильнее — "
                "доступ активен до <b>10.08.26</b>.\n\n"
                "👇 <b>Выбери сервер и подключись прямо сейчас:</b>"
            ),
        )
        keyboard = notification.kwargs["markup"].keyboard
        self.assertEqual(
            [row[0].text for row in keyboard],
            ["🇩🇪 Germany", "🇳🇱 Netherlands"],
        )
        self.assertEqual(
            [row[0].url for row in keyboard],
            ["tg://proxy?server=de", "tg://proxy?server=nl"],
        )

    def test_delivery_error_keeps_activation_and_report_counts(self) -> None:
        sender = mock.Mock(side_effect=[RuntimeError("telegram"), None])
        service = self._service(candidates=[_user("123")], sender=sender)

        service()

        report = sender.call_args_list[-1]
        self.assertEqual(report.kwargs["chat_id"], 999)
        self.assertIn("Перебрано кандидатов: 1", report.kwargs["text"])
        self.assertIn("Активировано периодов: 1", report.kwargs["text"])
        self.assertIn("Уведомлено пользователей: 0", report.kwargs["text"])

    def test_empty_candidates_still_send_one_report(self) -> None:
        sender = mock.Mock()
        service = self._service(candidates=[], sender=sender)

        service()

        sender.assert_called_once()
        self.assertIn("Перебрано кандидатов: 0", sender.call_args.kwargs["text"])

    def test_report_error_does_not_escape(self) -> None:
        service = self._service(
            candidates=[], sender=mock.Mock(side_effect=RuntimeError)
        )

        service()
