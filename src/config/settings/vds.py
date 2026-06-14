import os

VDS_REQUEST_TIMEOUT = int(os.getenv("VDS_REQUEST_TIMEOUT", 5))

# Домен маскировки FakeTLS, зашиваемый в секрет ключа (get_secret_token).
# Одинаков на всём флоте VDS. НЕ путать с {name}.beatvault.ru — это хост в proxy-URL.
TLS_DOMAIN = os.getenv("TLS_DOMAIN", "beatvault.ru")

# Глобальный потолок активных валидных ключей. Проверяется в IssueKeyService.
# TODO(step4): подтвердить точное прод-значение у владельца перед перепроводкой выдачи.
GLOBAL_KEYS_LIMIT = int(os.getenv("GLOBAL_KEYS_LIMIT", 1000))
