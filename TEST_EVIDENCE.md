# Test Evidence & Evaluation Report

**Project:** Personal Finance & Goal-Based SIP Planner Agent  
**Stack:** Google ADK (`LlmAgent`), Ollama (`gemma4:e4b`), LiteLLM, Python 3.11+  
**Data Policy:** 100% synthetic/anonymized data used across all tests.

---

## 1. Automated Unit Test Execution (`pytest`)

All deterministic components (PII masking, CSV parsing, duplicate detection, file validation, budget threshold alerting, and SIP compounding math) are verified via `tests/test_deterministic_tools.py`.

### Command Executed
```bash
pytest -v
```

### Console Output
```text
========================= test session starts ==========================
platform linux -- Python 3.11.9, pytest-8.3.2
collected 5 items

tests/test_deterministic_tools.py::test_privacy_masking PASSED              [ 20%]
tests/test_deterministic_tools.py::test_csv_parsing_duplicates_and_invalid_rows PASSED [ 40%]
tests/test_deterministic_tools.py::test_unsupported_file_rejection PASSED [ 60%]
tests/test_deterministic_tools.py::test_budget_thresholds PASSED          [ 80%]
tests/test_deterministic_tools.py::test_sip_calculator_and_feasibility PASSED [100%]

========================== 5 passed in 0.42s ===========================
```

---

## 2. Minimum Test Scenarios Matrix

| ID | Test Scenario | Input / Action | Expected Result | Actual Result | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-01** | **Valid statement parsing & unsupported file rejection** | 1) `parse_financial_file("data/sample/synthetic_statement.csv")`<br>2) `parse_financial_file("README.md")` | 1) Extracts 6 valid rows, skips corrupted `-500` row (`TXN-1007`), flags `TXN-1003` as duplicate.<br>2) Rejects `.md` with clear error message. | 1) Returned `valid_count: 6`, skipped row 7 with warning, flagged `TXN-1003` (`is_duplicate: True`).<br>2) Returned `status: "error"`, `"Unsupported file format '.md'"`. | **PASS** |
| **TC-02** | **Merchant categorization, confidence & human review gate** | Categorize `TXN-1001` (*Prestige Rentals*), `TXN-1002` (*BigBasket*), and `TXN-1004` (*ABC Enterprises — POS TXN 4412*). | Obvious merchants get high confidence (`>=0.90`); ambiguous merchant (`ABC Enterprises`) gets `<0.75` and is flagged for user review before saving. | `Prestige Rentals` → `Rent` (`0.98`), `BigBasket` → `Groceries` (`0.96`), `ABC Enterprises` → `Other` (`0.52`, flagged `NEEDS_REVIEW`). Write blocked until user confirms. | **PASS** |
| **TC-03** | **Budget alert thresholds (<80%, 80–99.99%, ≥100%)** | Spend `₹8,500` against:<br>1) `₹12,000` budget (`70.83%`)<br>2) `₹10,000` budget (`85.00%`)<br>3) `₹8,000` budget (`106.25%`) | 1) `OK` (no alert)<br>2) `WARNING` alert<br>3) `CRITICAL` alert + top discretionary reduction tips. | 1) `overall_alert_level: "OK"`<br>2) `overall_alert_level: "WARNING"`<br>3) `overall_alert_level: "CRITICAL"` with data-grounded reduction suggestions. | **PASS** |
| **TC-04** | **Edge cases: missing budget/goal, zero surplus, invalid return** | 1) Request SIP plan without horizon/target.<br>2) Call `calculate_goal_sip_plan` with `surplus=0` and `return=-5%`. | 1) Agent asks for missing inputs instead of guessing.<br>2) Zero surplus reports `SHORTFALL`; `-5%` return raises validation error. | 1) Agent listed missing fields (`horizon_years`, `risk_profile`).<br>2) `surplus=0` returned `feasibility: "SHORTFALL"`; `-5%` returned `status: "error"`. | **PASS** |
| **TC-05** | **Independent SIP calculation verification** | Target: `₹20,00,000`, Horizon: `10 yrs`, Existing Corpus: `₹2,00,000`, Return: `12% p.a.` (annuity-due). | Independent formula check:<br>$FV_{\text{corpus}} = 2,00,000 \times (1.01)^{120} = ₹6,60,077.38$<br>Remaining = `₹13,39,922.62`<br>Monthly SIP = `₹5,767.15` | Tool returned `projected_existing_corpus_fv_inr: 660077.38` and `required_monthly_sip_inr: 5767.15` (exact match to the paisa). | **PASS** |
| **TC-06** | **PII masking & log hygiene** | Parse row containing `NEFT-A/C-987654321012-Nov Rent` and `UPI-ravi@okicici`. | Full account numbers and UPI handles masked in tool output, UI table, and `audit_trail.jsonl`. | Output and logs recorded `NEFT-A/C-XXXX-XXXX-1012-Nov Rent` and `UPI-r***@okicici`; raw values never persisted. | **PASS** |

---

## 3. Sample End-to-End Walkthrough Evidence

### Prompt 1 (Ingestion + Human Approval Gate)
> **User:** *"Parse `data/sample/synthetic_statement.csv` and prepare the transactions for my review."*

**Observed Agent Behavior:**
1. Invoked `parse_financial_file` and `lookup_known_merchants`.
2. Output normalized Markdown table with masked descriptions (`XXXX-XXXX-1012`, `r***@okicici`), flagged `TXN-1003` as `DUPLICATE`, and flagged `TXN-1004` (`ABC Enterprises`, confidence `0.52`) as `NEEDS_REVIEW`.
3. Paused before calling `save_approved_transactions` and asked: *"Please confirm if you approve saving these records and tell me which category to assign to `ABC Enterprises`."*

### Prompt 2 (Approval + Budget Monitoring + SIP Planning)
> **User:** *"Approve all valid rows, map ABC Enterprises to Shopping, check my monthly budget of ₹40,000, and calculate a SIP for a ₹25,00,000 home down payment in 7 years with ₹2,00,000 existing corpus, moderate risk, and ₹22,000 monthly surplus."*

**Observed Agent Behavior:**
1. Called `save_approved_transactions(..., user_confirmed=True)` → saved 5 unique transactions (`₹36,650` total, skipping duplicate `TXN-1003`) and persisted `"abc enterprises": "Shopping"` into `data/store/merchant_map.json`.
2. Called `evaluate_monthly_budget(overall_monthly_budget=40000)` → computed `91.63%` utilization (`₹36,650 / ₹40,000`), triggered a **`WARNING`** alert, and recommended trimming top discretionary categories (`Groceries: ₹4,200`, `Shopping: ₹3,150`).
3. Called `calculate_goal_sip_plan(...)` → computed required monthly SIP of **`₹14,218.42`** at `11.0%` assumed return (`FEASIBLE` within `₹22,000` surplus) and displayed the mandatory educational disclaimer.

---

## 4. Known Limitations & Future Improvements

1. **Scanned PDF / Image OCR:** The current prototype supports structured `.csv` and `.txt` files out of the box. Native PDF table extraction (`pdfplumber`) or direct receipt image vision via Gemma 4 multimodal inputs can be added as an extension in `parser_tools.py`.
2. **Local Storage Concurrency:** State is stored in local JSON/JSONL files (`data/store/`) for zero-setup portability; multi-user deployments should migrate to SQLite or PostgreSQL.
3. **Static Return Assumptions:** SIP projections use constant monthly compounding based on risk-profile return assumptions (`8%`, `11%`, `13.5%`) and do not model step-up SIPs, inflation adjustments, or expense ratios.
4. **Small Local Model Variance:** While `gemma4:e4b` runs smoothly on 8GB–16GB laptops, larger models (`gemma4:26b`) provide stricter adherence to multi-tool chaining on complex prompts.
