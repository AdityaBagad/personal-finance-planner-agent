from finance_planner.tools.parser_tools import parse_financial_file
from finance_planner.tools.budget_tools import evaluate_monthly_budget
from finance_planner.tools.sip_tools import calculate_goal_sip_plan
from finance_planner.utils.privacy import mask_sensitive_text

def test_privacy_masking():
    masked = mask_sensitive_text("Transfer to A/C 987654321012 via ravi@okicici")
    assert "987654321012" not in masked
    assert "XXXX-XXXX-1012" in masked
    assert "r***@okicici" in masked

def test_csv_parsing_duplicates_and_invalid_rows():
    res = parse_financial_file("data/sample/synthetic_statement.csv")
    assert res["status"] == "success"
    assert res["valid_count"] == 13
    dups = [t for t in res["transactions"] if t["is_duplicate"]]
    assert len(dups) == 2
    assert {d["transaction_id"] for d in dups} == {"TXN-1003", "TXN-1004"}

def test_unsupported_file_rejection():
    res = parse_financial_file("README.md")
    assert res["status"] == "error"
    assert "Unsupported file format" in res["message"]

def test_budget_thresholds():
    sample_txns = [{"amount": 8500, "type": "debit", "category": "Groceries", "is_duplicate": False}]
    warn = evaluate_monthly_budget(overall_monthly_budget=10000, inline_transactions=sample_txns)
    assert warn["overall_alert_level"] == "WARNING"

    crit = evaluate_monthly_budget(overall_monthly_budget=8000, inline_transactions=sample_txns)
    assert crit["overall_alert_level"] == "CRITICAL"

def test_sip_calculator_and_feasibility():
    res = calculate_goal_sip_plan(
        target_amount_inr=2000000,
        horizon_years=10,
        monthly_investible_surplus_inr=10000,
        existing_corpus_inr=200000,
        risk_profile="moderate",
        expected_annual_return_pct=12.0,
    )
    assert res["status"] == "success"
    assert res["required_monthly_sip_inr"] > 0
    assert "disclaimer" in res
