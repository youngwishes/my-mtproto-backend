def build_production_logging() -> dict[str, object]:
    return {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "{levelname} {asctime} {message}",
            "style": "{",
        },
    },
    "filters": {
        "redact_subscription_path": {
            "()": "config.logging_filters.SubscriptionPathRedactionFilter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "filters": ["redact_subscription_path"],
        },
        "mail_admins": {
            "class": "django.utils.log.AdminEmailHandler",
            "level": "ERROR",
            "filters": ["redact_subscription_path"],
            "include_html": False,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "config.middlewares": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console", "mail_admins"],
            "filters": ["redact_subscription_path"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.server": {
            "handlers": ["console", "mail_admins"],
            "filters": ["redact_subscription_path"],
            "level": "ERROR",
            "propagate": False,
        },
    },
    }


LOGGING = build_production_logging()
