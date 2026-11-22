import json
import os
from datetime import datetime, timezone
from finance_planner.config import DATA_DIR, STANDARD_CATEGORIES

MERCHANT_MAP_FILE = os.path.join(DATA_DIR, "merchant_map.json")
APPROVED_TXN_FILE = os.path.join(DATA_DIR, "approved_transactions.json")
AUDIT_LOG_FILE = os.path.join(DATA_DIR, "audit_trail.jsonl")

def _load_json(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_json(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def log_audit_event(action: str, details: dict) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "details": details
    }
    with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

def lookup_known_merchants(merchants: list[str]) -> dict:
    """Checks stored user-approved merchant-to-category mappings before LLM guessing."""
    merchant_map = _load_json(MERCHANT_MAP_FILE, {})
    matches = {}
    for m in merchants:
        key = m.strip().lower()
        if key in merchant_map:
            matches[m] = merchant_map[key]
    return {"known_mappings": matches, "allowed_categories": STANDARD_CATEGORIES}

def save_approved_transactions(transactions: list[dict], user_confirmed: bool = False) -> dict:
    """
    Saves categorized transactions and updates merchant memory ONLY after explicit user approval.
    """
    if not user_confirmed:
        return {
            "status": "approval_required",
            "message": "Action blocked: Present the normalized table and low-confidence flags to the user and ask for explicit confirmation before saving."
        }

    existing = _load_json(APPROVED_TXN_FILE, [])
    merchant_map = _load_json(MERCHANT_MAP_FILE, {})

    saved_count = 0
    for tx in transactions:
        if tx.get("is_duplicate"):
            continue

        category = str(tx.get("category") or "Other").strip()
        raw_type = str(tx.get("type") or tx.get("direction") or "").strip().upper()

        # Infer CREDIT if LLM omitted 'type' on an Income transaction
        if raw_type not in {"DEBIT", "CREDIT"}:
            raw_type = "CREDIT" if category.lower() == "income" else "DEBIT"

        tx["category"] = category
        tx["type"] = raw_type
        tx["amount"] = float(tx.get("amount", 0.0))

        existing.append(tx)
        merchant_key = tx["merchant"].strip().lower()
        merchant_map[merchant_key] = category
        saved_count += 1

    _save_json(APPROVED_TXN_FILE, existing)
    _save_json(MERCHANT_MAP_FILE, merchant_map)
    log_audit_event("SAVE_APPROVED_TRANSACTIONS", {"saved_count": saved_count})

    return {
        "status": "saved",
        "saved_count": saved_count,
        "message": f"Successfully saved {saved_count} approved transactions and updated merchant memory."
    }

def get_saved_transactions() -> list[dict]:
    """Retrieves all user-approved transactions stored so far."""
    return _load_json(APPROVED_TXN_FILE, [])
