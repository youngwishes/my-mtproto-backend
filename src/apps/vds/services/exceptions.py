from apps.core.service import BaseServiceError


class VDSNotAvailable(BaseServiceError):
    """VDS not available"""


class VDSConnectionLimit(BaseServiceError):
    """VDS connection limit"""
