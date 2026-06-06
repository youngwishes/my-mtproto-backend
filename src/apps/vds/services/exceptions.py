from apps.core.exceptions import BaseInfraError


class VDSNotAvailable(BaseInfraError):
    """VDS not available"""


class VDSConnectionLimit(BaseInfraError):
    """VDS connection limit"""
