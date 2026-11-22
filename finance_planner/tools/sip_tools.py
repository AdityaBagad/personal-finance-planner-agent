import json
import os
from finance_planner.config import DATA_DIR
from finance_planner.tools.memory_tools import log_audit_event

SIP_PLAN_FILE = os.path.join(DATA_DIR, "latest_sip_plan.json")

RISK_RETURN_DEFAULTS = {
    "conservative": 8.0,
    "moderate": 11.0,
    "aggressive": 13.5,
}


def get_latest_sip_plan() -> dict | None:
    """Retrieves the most recently calculated goal SIP plan for dashboard visualization."""
    if not os.path.exists(SIP_PLAN_FILE):
        return None
    with open(SIP_PLAN_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def calculate_goal_sip_plan(
    target_amount_inr: float,
    horizon_years: float,
    monthly_investible_surplus_inr: float,
    existing_corpus_inr: float = 0.0,
    risk_profile: str = "moderate",
    expected_annual_return_pct: float | None = None,
) -> dict:
    """
    Deterministically computes the required monthly SIP to reach a financial goal,
    accounting for compounding on any existing corpus, and checks feasibility against monthly surplus.
    """
    if target_amount_inr <= 0 or horizon_years <= 0:
        return {"status": "error", "message": "Target amount and horizon must be positive numbers."}
    if existing_corpus_inr < 0 or monthly_investible_surplus_inr < 0:
        return {"status": "error", "message": "Existing corpus and monthly surplus cannot be negative."}

    profile_key = risk_profile.strip().lower()
    annual_rate = (
        expected_annual_return_pct
        if expected_annual_return_pct is not None
        else RISK_RETURN_DEFAULTS.get(profile_key, 11.0)
    )

    if annual_rate <= 0 or annual_rate > 30:
        return {"status": "error", "message": "Expected annual return must be between 0.1% and 30%."}

    months = int(round(horizon_years * 12))
    monthly_rate = (annual_rate / 100.0) / 12.0

    fv_existing = existing_corpus_inr * ((1 + monthly_rate) ** months)
    remaining_target = max(0.0, target_amount_inr - fv_existing)

    if remaining_target == 0:
        required_sip = 0.0
    else:
        factor = (((1 + monthly_rate) ** months) - 1) / monthly_rate * (1 + monthly_rate)
        required_sip = remaining_target / factor

    required_sip = round(required_sip, 2)
    fits_surplus = monthly_investible_surplus_inr >= required_sip
    gap = round(required_sip - monthly_investible_surplus_inr, 2)

    # Build year-by-year compounding schedule for dashboard charting
    yearly_schedule = []
    corpus = existing_corpus_inr
    invested = existing_corpus_inr
    for m in range(1, months + 1):
        corpus = (corpus + required_sip) * (1 + monthly_rate)
        invested += required_sip
        if m % 12 == 0 or m == months:
            yearly_schedule.append({
                "Year": round(m / 12, 1),
                "Total Invested (₹)": round(invested, 2),
                "Projected Corpus (₹)": round(corpus, 2),
            })

    result = {
        "status": "success",
        "target_amount_inr": round(target_amount_inr, 2),
        "horizon_years": horizon_years,
        "risk_profile": profile_key,
        "assumed_annual_return_pct": annual_rate,
        "existing_corpus_inr": round(existing_corpus_inr, 2),
        "projected_existing_corpus_fv_inr": round(fv_existing, 2),
        "required_monthly_sip_inr": required_sip,
        "monthly_investible_surplus_inr": round(monthly_investible_surplus_inr, 2),
        "feasibility": "FEASIBLE" if fits_surplus else "SHORTFALL",
        "monthly_shortfall_inr": 0.0 if fits_surplus else gap,
        "yearly_schedule": yearly_schedule,
        "disclaimer": "Educational planning support only — not regulated financial advice. Mutual fund investments are subject to market risks; returns are not guaranteed.",
    }

    with open(SIP_PLAN_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    log_audit_event("SIP_CALCULATED", {"required_sip": required_sip, "feasibility": result["feasibility"]})
    return result
