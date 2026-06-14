from __future__ import annotations

from unittest import mock

from django.test import TestCase

from apps.notifications.enums import ContextResolverType, FilterType, MailingStatus
from apps.notifications.services.send_mailing_service import SendMailingService
from apps.notifications.tests.factories import MailingFactory, NotificationTemplateFactory
from apps.users.tests.factories import SystemUserFactory


@mock.patch("apps.notifications.services.send_mailing_service.time.sleep")
class TestSendMailingService(TestCase):
    @mock.patch("apps.notifications.services.send_mailing_service.send_telegram_message")
    def test_sends_to_all_active_users(self, mock_send: mock.Mock, _mock_sleep: mock.Mock) -> None:
        user1 = SystemUserFactory(username="111", is_active=True)
        user2 = SystemUserFactory(username="222", is_active=True)
        SystemUserFactory(username="333", is_active=False)

        template = NotificationTemplateFactory(
            slug="mailing-test",
            text="Привет всем!",
            button_text="",
            button_url="",
        )
        mailing = MailingFactory(
            template=template,
            filter_type=FilterType.ALL_ACTIVE,
            context_resolver=ContextResolverType.NONE,
            status=MailingStatus.DRAFT,
        )

        SendMailingService(mailing=mailing)()

        self.assertEqual(mock_send.call_count, 2)
        mailing.refresh_from_db()
        self.assertEqual(mailing.status, MailingStatus.COMPLETED)
        self.assertIsNotNone(mailing.sent_at)

    @mock.patch("apps.notifications.services.send_mailing_service.send_telegram_message")
    def test_merges_static_and_personal_context(self, mock_send: mock.Mock, _mock_sleep: mock.Mock) -> None:
        user = SystemUserFactory(username="555", is_active=True)

        template = NotificationTemplateFactory(
            slug="mailing-merge",
            text="Привет! Промо: {promo}",
            button_text="",
            button_url="",
        )
        mailing = MailingFactory(
            template=template,
            filter_type=FilterType.ALL_ACTIVE,
            context={"promo": "SALE2026"},
            context_resolver=ContextResolverType.NONE,
            status=MailingStatus.DRAFT,
        )

        SendMailingService(mailing=mailing)()

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args.kwargs
        self.assertIn("SALE2026", call_kwargs["text"])

    @mock.patch("apps.notifications.services.send_mailing_service.send_telegram_message")
    def test_marks_as_failed_when_all_sends_fail(self, mock_send: mock.Mock, _mock_sleep: mock.Mock) -> None:
        SystemUserFactory(username="666", is_active=True)
        SystemUserFactory(username="777", is_active=True)
        mock_send.side_effect = Exception("Telegram API error")

        template = NotificationTemplateFactory(
            slug="mailing-fail",
            text="Привет!",
            button_text="",
            button_url="",
        )
        mailing = MailingFactory(
            template=template,
            filter_type=FilterType.ALL_ACTIVE,
            context_resolver=ContextResolverType.NONE,
            status=MailingStatus.DRAFT,
        )

        SendMailingService(mailing=mailing)()

        mailing.refresh_from_db()
        self.assertEqual(mailing.status, MailingStatus.FAILED)
        self.assertEqual(mailing.sent_count, 0)
        self.assertEqual(mailing.failed_count, 2)

    @mock.patch("apps.notifications.services.send_mailing_service.send_telegram_message")
    def test_marks_as_partially_completed_when_some_fail(self, mock_send: mock.Mock, _mock_sleep: mock.Mock) -> None:
        SystemUserFactory(username="888", is_active=True)
        SystemUserFactory(username="999", is_active=True)
        mock_send.side_effect = [None, Exception("Telegram API error")]

        template = NotificationTemplateFactory(
            slug="mailing-partial",
            text="Привет!",
            button_text="",
            button_url="",
        )
        mailing = MailingFactory(
            template=template,
            filter_type=FilterType.ALL_ACTIVE,
            context_resolver=ContextResolverType.NONE,
            status=MailingStatus.DRAFT,
        )

        SendMailingService(mailing=mailing)()

        mailing.refresh_from_db()
        self.assertEqual(mailing.status, MailingStatus.PARTIALLY_COMPLETED)
        self.assertEqual(mailing.sent_count, 1)
        self.assertEqual(mailing.failed_count, 1)

    @mock.patch("apps.notifications.services.send_mailing_service.send_telegram_message")
    def test_sets_counters_on_full_success(self, mock_send: mock.Mock, _mock_sleep: mock.Mock) -> None:
        SystemUserFactory(username="101", is_active=True)
        SystemUserFactory(username="102", is_active=True)

        template = NotificationTemplateFactory(
            slug="mailing-counters",
            text="Привет!",
            button_text="",
            button_url="",
        )
        mailing = MailingFactory(
            template=template,
            filter_type=FilterType.ALL_ACTIVE,
            context_resolver=ContextResolverType.NONE,
            status=MailingStatus.DRAFT,
        )

        SendMailingService(mailing=mailing)()

        mailing.refresh_from_db()
        self.assertEqual(mailing.status, MailingStatus.COMPLETED)
        self.assertEqual(mailing.sent_count, 2)
        self.assertEqual(mailing.failed_count, 0)
