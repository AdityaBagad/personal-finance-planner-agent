import os
import uuid
import pandas as pd
from finance_planner.utils.privacy import mask_sensitive_text

SUPPORTED_EXTENSIONS = {".csv", ".txt"}
REQUIRED_CSV_COLUMNS = {
    "transaction_id",
    "date",
    "merchant_name",
    "raw_description",
    "amount_inr",
    "direction",
    "currency",
}


def parse_financial_file(file_path: str) -> dict:
    """
    Parses a synthetic bank statement CSV (with headers: transaction_id, date,
    merchant_name, raw_description, amount_inr, direction, currency) or receipt text file.
    Detects duplicates, flags invalid/negative rows, and masks sensitive identifiers.
    """
    if not os.path.exists(file_path):
        return {"status": "error", "message": f"File not found: {file_path}"}

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return {
            "status": "error",
            "message": f"Unsupported file format '{ext}'. Supported formats: CSV, TXT.",
        }

    if ext == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            raw_content = mask_sensitive_text(f.read())
        return {
            "status": "success",
            "source_type": "receipt_text",
            "masked_text": raw_content,
            "instruction": "Extract date, merchant, description, amount, currency, and type from masked_text.",
        }

    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        return {"status": "error", "message": f"Failed to read CSV: {str(e)}"}

    # Normalize column headers (strip whitespace / lowercase)
    df.columns = [c.strip().lower() for c in df.columns]
    missing_cols = REQUIRED_CSV_COLUMNS - set(df.columns)
    if missing_cols:
        return {
            "status": "error",
            "message": f"Missing required CSV columns: {sorted(missing_cols)}",
        }

    records = []
    warnings = []
    seen_signatures = set()

    for idx, row in df.iterrows():
        raw_amount = row["amount_inr"]
        merchant = mask_sensitive_text(str(row["merchant_name"]).strip())
        desc = mask_sensitive_text(str(row["raw_description"]).strip())
        date_val = str(row["date"]).strip()
        tx_id = str(row["transaction_id"]).strip() or f"TXN-{uuid.uuid4().hex[:6].upper()}"
        raw_dir = str(row["direction"]).strip().upper()
        currency = str(row["currency"]).strip().upper() or "INR"

        # Validate amount
        try:
            amount_val = float(raw_amount)
            if pd.isna(amount_val) or amount_val <= 0:
                warnings.append(f"Row {idx + 1} ({tx_id}): Skipped non-positive or missing amount ({raw_amount}).")
                continue
        except (ValueError, TypeError):
            warnings.append(f"Row {idx + 1} ({tx_id}): Skipped unreadable amount ({raw_amount}).")
            continue

        # Validate required text fields
        if not date_val or date_val.lower() == "nan" or not merchant or merchant.lower() == "nan":
            warnings.append(f"Row {idx + 1} ({tx_id}): Missing required date or merchant_name.")
            continue

        # Validate direction (DEBIT / CREDIT)
        if raw_dir not in {"DEBIT", "CREDIT"}:
            warnings.append(f"Row {idx + 1} ({tx_id}): Invalid direction '{raw_dir}' (expected DEBIT or CREDIT).")
            continue

        amount = round(amount_val, 2)
        tx_type = raw_dir.upper()

        # Duplicate detection signature
        sig = (date_val, merchant.lower(), amount, tx_type)
        is_dup = sig in seen_signatures
        seen_signatures.add(sig)
        if is_dup:
            warnings.append(f"Row {idx + 1} ({tx_id}): Flagged as potential duplicate transaction.")

        records.append({
            "transaction_id": tx_id,
            "date": date_val,
            "merchant": merchant,
            "description": desc,
            "amount": amount,
            "currency": currency,
            "type": tx_type,
            "source": os.path.basename(file_path),
            "is_duplicate": is_dup,
        })

    return {
        "status": "success",
        "source_type": "csv",
        "valid_count": len(records),
        "warnings": warnings,
        "transactions": records,
    }
