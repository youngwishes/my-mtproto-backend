from apps.core.exceptions import BaseServiceError


class AlreadyUsedFree(BaseServiceError):
    """🔒 Вы уже получили беплатную ссылку. Если она не работает — напишите в поддержку: @mtprotokeys_support."""
