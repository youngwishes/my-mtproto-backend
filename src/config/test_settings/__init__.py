from config.settings import *

LOGGING["root"]["level"] = "CRITICAL"
LOGGING["loggers"]["config.middlewares"]["level"] = "CRITICAL"
LOGGING["loggers"]["django.request"] = {
    "handlers": ["console"],
    "level": "CRITICAL",
    "propagate": False,
}
