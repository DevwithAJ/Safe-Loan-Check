from __future__ import annotations


def decide(
    directory_status: str,
    risk_probability,
    cost_result: dict | None,
    high_risk_threshold: float,
    affordability_threshold: float,
    *,
    listing_signal_level: str = "Insufficient",
    directory_stale: bool = False,
    model_ready: bool = True,
):
    """Conservative production-candidate decision layer.

    Directory verification, experimental ML, public-listing risk signals and cost
    are kept distinct. The result is awareness guidance, not an approval/legal verdict.
    """
    directory_status = directory_status or "Unclear"
    model_risk_high = risk_probability is not None and float(risk_probability) >= float(high_risk_threshold)
    listing_level = str(listing_signal_level or "").lower()
    listing_risk_high = listing_level == "high"
    listing_review_needed = listing_level in {"high", "moderate"}
    risk_high = model_risk_high or listing_risk_high

    ratio = None
    if cost_result and cost_result.get("valid"):
        ratio = cost_result.get("emi_income_ratio")
    above_affordability = ratio is not None and ratio > affordability_threshold

    if directory_status == "Not listed" and risk_high:
        return {
            "verdict": "Red",
            "message": "Do not proceed without independent verification. No match was found in the loaded DLA directory copy and strong risk signals were observed.",
            "drivers": ["directory_not_listed", "risk_high"],
        }

    if directory_status == "Not listed":
        return {
            "verdict": "Amber",
            "message": "Unverified in the loaded directory copy. Ask for the regulated lender's name and Key Fact Statement and verify them independently before proceeding.",
            "drivers": ["directory_not_listed"],
        }

    if directory_status == "Unclear":
        return {
            "verdict": "Amber",
            "message": "The identity match is unclear. Confirm the exact developer and regulated lender before relying on the app.",
            "drivers": ["directory_unclear"],
        }

    if directory_status == "Listed" and above_affordability:
        return {
            "verdict": "Amber",
            "message": "A directory match was found, but the entered EMI is above the configured affordability threshold. Review the Key Fact Statement and compare alternatives.",
            "drivers": ["directory_listed", "above_affordability"],
        }

    if directory_status == "Listed" and (model_risk_high or listing_review_needed):
        if model_risk_high and listing_review_needed:
            source = "ML and public-listing"
        elif model_risk_high:
            source = "ML"
        else:
            source = "public-listing"
        return {
            "verdict": "Amber",
            "message": f"A directory match was found, but {source} risk signals need manual review before borrowing.",
            "drivers": ["directory_listed", "risk_review_needed"],
        }

    if directory_status == "Listed" and directory_stale:
        return {
            "verdict": "Amber",
            "message": "A match exists in the loaded directory copy, but the local snapshot is older than the configured freshness window. Refresh the RBI directory before relying on a Green result.",
            "drivers": ["directory_listed", "directory_stale"],
        }

    if directory_status == "Listed" and not model_ready:
        return {
            "verdict": "Amber",
            "message": "A directory match was found, but the ML risk service is unavailable. Treat the result as incomplete and review the app manually.",
            "drivers": ["directory_listed", "model_unavailable"],
        }

    if directory_status == "Listed":
        return {
            "verdict": "Green",
            "message": "A match was found in the loaded dated directory copy and no strong risk signal was triggered. This is not an approval or recommendation; still read the Key Fact Statement and verify the offer details.",
            "drivers": ["directory_listed", "no_strong_risk_signal"],
        }

    return {
        "verdict": "Amber",
        "message": "The available evidence is incomplete. Manual verification is recommended.",
        "drivers": ["insufficient_evidence"],
    }
