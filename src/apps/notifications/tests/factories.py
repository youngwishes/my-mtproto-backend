from __future__ import annotations

import factory

from apps.notifications.enums import ContextResolverType, FilterType, MailingStatus
from apps.notifications.models import Mailing, NotificationTemplate


class NotificationTemplateFactory(factory.django.DjangoModelFactory):
    slug = factory.Sequence(lambda n: f"template-{n}")
    title = factory.Sequence(lambda n: f"Template {n}")
    text = "Default text"
    button_text = ""
    button_url = ""
    include_payment_buttons = False

    class Meta:
        model = NotificationTemplate


class MailingFactory(factory.django.DjangoModelFactory):
    template = factory.SubFactory(NotificationTemplateFactory)
    filter_type = FilterType.ALL_ACTIVE
    filter_params = factory.LazyFunction(dict)
    context = factory.LazyFunction(dict)
    context_resolver = ContextResolverType.NONE
    status = MailingStatus.DRAFT

    class Meta:
        model = Mailing
