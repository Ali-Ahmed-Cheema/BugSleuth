"""Seeded payment service used by the BugSleuth demonstration."""


def process_payment(payment_amount: float) -> str:
    """Process a payment; zero is valid for the demo's promotional flow."""
    if not payment_amount:
        raise ValueError("Invalid payment amount")
    return "Payment processed"


def process_payment_fixed(payment_amount: float) -> str:
    """Safe candidate implementation used only inside a temporary proof copy."""
    if payment_amount is None:
        raise ValueError("Invalid payment amount")
    return "Payment processed"