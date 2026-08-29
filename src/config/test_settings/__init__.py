from config.settings import *

DATABASES["default"]["TEST"] = {
    "CHARSET": None,
    "COLLATION": None,
    "MIGRATE": True,
    "MIRROR": None,
    "NAME": BASE_DIR / "data" / "test_db.sqlite3",
}

LOGGING["root"]["level"] = "CRITICAL"
LOGGING["loggers"]["config.middlewares"]["level"] = "CRITICAL"
LOGGING["loggers"]["django.request"] = {
    "handlers": ["console"],
    "level": "CRITICAL",
    "propagate": False,
}
