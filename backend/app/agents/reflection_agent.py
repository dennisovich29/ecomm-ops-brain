from __future__ import annotations

from app.graph.state import OpsState

MAX_REFLECTION_PASSES = 3
CONFIDENCE_THRESHOLD = 0.70

_DOMAIN_FINDING_MAP = {
    "sales": "sales_findings",
    "inventory": "inventory_findings",
    "marketing": "marketing_findings",
    "support": "support_findings",
}


def _score_confidence(state: OpsState) -> float:
    domains = (state.get("intent") or {}).get("domains", [])
    if not domains:
        return 0.5

    populated = sum(
        1 for d in domains
        if state.get(_DOMAIN_FINDING_MAP.get(d, "")) is not None
    )
    base = populated / len(domains)

    # Boost if multiple domains corroborate each other
    corroborating = 0
    inv = state.get("inventory_findings") or {}
    mkt = state.get("marketing_findings") or {}
    sup = state.get("support_findings") or {}
    sal = state.get("sales_findings") or {}

    if inv.get("stockout_events") and sal.get("revenue_summary"):
        corroborating += 1
    if mkt.get("campaign_issues") and sal.get("revenue_summary"):
        corroborating += 1
    if sup.get("top_complaint_themes") and inv.get("stockout_events"):
        corroborating += 1

    boost = min(corroborating * 0.1, 0.3)
    return min(round(base + boost, 2), 1.0)


def reflect(state: OpsState) -> dict:
    domains = (state.get("intent") or {}).get("domains", [])
    gaps = []
    notes = []

    for domain in domains:
        field = _DOMAIN_FINDING_MAP.get(domain)
        if field and not state.get(field):
            gaps.append(f"missing_{domain}_data")
            notes.append(f"No findings from {domain} agent yet.")

    confidence = _score_confidence(state)

    if confidence >= CONFIDENCE_THRESHOLD:
        notes.append(f"Confidence {confidence:.0%} — sufficient evidence for synthesis.")
    else:
        notes.append(f"Confidence {confidence:.0%} — below threshold, checking gaps.")

    passes = state.get("reflection_passes", 0) + 1

    return {
        "gaps_identified": gaps,
        "confidence_score": confidence,
        "reflection_notes": notes,
        "reflection_passes": passes,
    }


def should_re_query(state: OpsState) -> str:
    if (
        state.get("gaps_identified")
        and state.get("reflection_passes", 0) < MAX_REFLECTION_PASSES
        and state.get("confidence_score", 0) < CONFIDENCE_THRESHOLD
    ):
        return "re_query"
    return "synthesize"
