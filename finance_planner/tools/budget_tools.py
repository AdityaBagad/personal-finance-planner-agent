from typing import Optional
from finance_planner.config import WARNING_THRESHOLD, CRITICAL_THRESHOLD
from finance_planner.tools.memory_tools import get_saved_transactions, log_audit_event

def evaluate_monthly_budget(
    overall_monthly_budget: float,
    category_limits: Optional[dict[str, float]] = None,
    warning_pct: float = WARNING_THRESHOLD,
    critical_pct: float = CRITICAL_THRESHOLD,
    inline_transactions: Optional[list[dict]] = None
) -> dict:
    """
    Calculates spent amount, remaining budget, percentage used, and triggers Warning (>=80%) or Critical (>=100%) alerts.
    Uses saved approved transactions unless inline_transactions are supplied for preview.
    """
    if overall_monthly_budget <= 0:
        return {"status": "error", "message": "Monthly budget must be greater than zero."}

    txns = inline_transactions if inline_transactions is not None else get_saved_transactions()
    if not txns:
        return {"status": "error", "message": "No transactions available to evaluate budget."}

    debits = [
        t for t in txns
        if str(t.get("type", "DEBIT")).upper() == "DEBIT"
        and str(t.get("category", "")).lower() != "income"
        and not t.get("is_duplicate")
    ]
    category_spend: dict[str, float] = {}
    for t in debits:
        cat = t.get("category", "Other")
        category_spend[cat] = round(category_spend.get(cat, 0.0) + float(t["amount"]), 2)

    total_spent = round(sum(category_spend.values()), 2)
    remaining = round(overall_monthly_budget - total_spent, 2)
    pct_used = round((total_spent / overall_monthly_budget) * 100, 2)

    def _get_status(pct: float) -> str:
        if pct >= critical_pct:
            return "CRITICAL"
        if pct >= warning_pct:
            return "WARNING"
        return "OK"

    alerts = []
    overall_status = _get_status(pct_used)
    if overall_status != "OK":
        alerts.append(f"{overall_status}: Overall monthly spend is {pct_used}% (₹{total_spent:,.2f} of ₹{overall_monthly_budget:,.2f}).")

    category_breakdown = {}
    limits = category_limits or {}
    for cat, spent in sorted(category_spend.items(), key=lambda x: x[1], reverse=True):
        limit = limits.get(cat)
        cat_pct = round((spent / limit) * 100, 2) if limit and limit > 0 else None
        status = _get_status(cat_pct) if cat_pct is not None else "NO_LIMIT_SET"
        if status in {"WARNING", "CRITICAL"}:
            alerts.append(f"{status}: '{cat}' spend is {cat_pct}% (₹{spent:,.2f} of ₹{limit:,.2f} limit).")
        category_breakdown[cat] = {
            "spent_inr": spent,
            "limit_inr": limit,
            "percent_used": cat_pct,
            "status": status
        }

    # Top discretionary categories to support data-grounded reduction suggestions
    non_fixed = {k: v for k, v in category_spend.items() if k not in {"Rent", "Education", "Healthcare", "Investment"}}
    top_spending_categories = sorted(non_fixed.items(), key=lambda x: x[1], reverse=True)[:2]

    result = {
        "status": "success",
        "overall_budget_inr": overall_monthly_budget,
        "total_spent_inr": total_spent,
        "remaining_budget_inr": remaining,
        "overall_percent_used": pct_used,
        "overall_alert_level": overall_status,
        "alerts": alerts,
        "category_breakdown": category_breakdown,
        "top_discretionary_categories": top_spending_categories
    }
    log_audit_event("BUDGET_EVALUATED", {"overall_status": overall_status, "pct_used": pct_used})
    return result
