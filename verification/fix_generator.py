def generate_fix() -> dict:
    return {
        "description": "Validate missing amounts explicitly so zero remains valid.",
        "diff": "-    if not payment_amount:\n+    if payment_amount is None:\n         raise ValueError(\"Invalid payment amount\")"
    }