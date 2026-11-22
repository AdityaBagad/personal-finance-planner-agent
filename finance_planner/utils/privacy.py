import re

def mask_sensitive_text(text: str) -> str:
    """Masks bank account numbers (9-18 digits), card numbers, and UPI handles."""
    if not text:
        return ""
    # Mask long digit sequences (account/card numbers), keeping last 4 digits
    text = re.sub(r"\b\d{5,14}(\d{4})\b", r"XXXX-XXXX-\1", text)
    # Mask UPI IDs (e.g., user@okicici -> u***@okicici)
    text = re.sub(r"\b([a-zA-Z0-9._-])[a-zA-Z0-9._-]+(@[a-zA-Z]+)\b", r"\1***\2", text)
    return text
