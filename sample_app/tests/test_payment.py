import pytest

from sample_app.payment_service import process_payment, process_payment_fixed


def test_buggy_implementation_rejects_zero():
    with pytest.raises(ValueError, match="Invalid payment amount"):
        process_payment(0)


def test_fixed_implementation_accepts_zero():
    assert process_payment_fixed(0) == "Payment processed"