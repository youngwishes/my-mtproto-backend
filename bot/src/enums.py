from enum import StrEnum


class FreeAvailable(StrEnum):
    MONTH = "MONTH"
    TWO_WEEK = "TWO_WEEK"
    WEEK = "WEEK"
    NOT_AVAILABLE = "NOT_AVAILABLE"