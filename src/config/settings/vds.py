import os

VDS_REQUEST_TIMEOUT = int(os.getenv("VDS_REQUEST_TIMEOUT", 5))

# Глобальный потолок активных валидных ключей. Проверяется в IssueKeyService.
# TODO(step4): подтвердить точное прод-значение у владельца перед перепроводкой выдачи.
GLOBAL_KEYS_LIMIT = int(os.getenv("GLOBAL_KEYS_LIMIT", 1000))
