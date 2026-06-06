from apps.core.service import BaseServiceError


class AlreadyUsedFree(BaseServiceError):
    """🔒 Вы уже получили беплатную ссылку. Если она не работает — напишите нам в личные сообщения канала @mtproto_keys."""


class AlreadyUsedProgram(BaseServiceError):
    """🔒 Вы уже воспользовались реферальной программой."""


class NotEnoughReferrals(BaseServiceError):
    """🔒 Пригласите как минимум 5 пользователей. Используйте для этого вашу реферальную ссылку. Каждый приглашенный пользователь должен воспользоваться бесплатным периодом в 14 дней по вашей реферальной ссылке."""
