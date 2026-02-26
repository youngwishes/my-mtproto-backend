from dataclasses import dataclass


@dataclass(kw_only=True, slots=True, frozen=True)
class NewDigitalPaymentDTO:
    name: str
    product_id: int
    product_name: str
    amount: float
    currency: str
    telegram_user_id: str
    purchase_created_at: str
    is_success: bool = False
