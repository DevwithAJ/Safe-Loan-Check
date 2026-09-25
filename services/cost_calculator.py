from __future__ import annotations

import math
import numpy_financial as npf


def calculate_cost(
    loan_amount: float,
    processing_fee: float,
    other_upfront_fees: float,
    emi: float,
    tenure_months: int,
    monthly_income: float | None = None,
):
    loan_amount = float(loan_amount or 0)
    processing_fee = float(processing_fee or 0)
    other_upfront_fees = float(other_upfront_fees or 0)
    emi = float(emi or 0)
    tenure_months = int(tenure_months or 0)
    monthly_income = float(monthly_income or 0)

    values = [loan_amount, processing_fee, other_upfront_fees, emi, monthly_income]
    if any(not math.isfinite(x) for x in values):
        return {"valid": False, "error": "Loan inputs must be finite numbers."}
    if loan_amount <= 0 or emi <= 0 or tenure_months <= 0:
        return {"valid": False, "error": "Loan amount, EMI and tenure must all be greater than zero."}
    if processing_fee < 0 or other_upfront_fees < 0 or monthly_income < 0:
        return {"valid": False, "error": "Fees and income cannot be negative."}

    net_received = loan_amount - processing_fee - other_upfront_fees
    if net_received <= 0:
        return {"valid": False, "error": "Upfront fees must be lower than the loan amount."}

    cashflows = [-net_received] + [emi] * tenure_months
    try:
        monthly_irr = npf.irr(cashflows)
    except Exception:
        monthly_irr = None

    apr = None
    if monthly_irr is not None:
        try:
            if math.isfinite(float(monthly_irr)) and float(monthly_irr) > -1:
                apr = ((1 + float(monthly_irr)) ** 12 - 1) * 100
                if not math.isfinite(apr) or apr < 0:
                    apr = None
        except (TypeError, ValueError, OverflowError):
            apr = None

    total_repayable = emi * tenure_months
    financing_cost = total_repayable - net_received
    emi_income_ratio = (emi / monthly_income) if monthly_income > 0 else None

    return {
        "valid": True,
        "loan_amount": round(loan_amount, 2),
        "net_received": round(net_received, 2),
        "processing_fee": round(processing_fee, 2),
        "other_upfront_fees": round(other_upfront_fees, 2),
        "emi": round(emi, 2),
        "tenure_months": tenure_months,
        "total_repayable": round(total_repayable, 2),
        "financing_cost": round(financing_cost, 2),
        "apr_percent": round(apr, 2) if apr is not None else None,
        "emi_income_ratio": round(emi_income_ratio, 4) if emi_income_ratio is not None else None,
        "cashflow_method": "Net amount received at time 0, followed by equal monthly EMI outflows; monthly IRR annualised effectively.",
    }
