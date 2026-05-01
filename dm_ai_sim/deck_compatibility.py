from __future__ import annotations

from collections import Counter
from typing import Any

from dm_ai_sim.card_database import CardDatabase, missing_official_data_fields, unknown_data_fields
from dm_ai_sim.deck_loader import DeckList, runtime_blocked_reasons
from dm_ai_sim.ruleset import Ruleset, validate_deck_against_ruleset


HIGH_PRIORITY_TAGS = {
    "DOUBLE_BREAKER",
    "SPEED_ATTACKER",
    "G_STRIKE",
    "SHIELD_TRIGGER",
    "TWINPACT",
    "REVOLUTION_CHANGE",
    "INVASION",
    "EVOLUTION",
    "ALTERNATE_WIN_CONDITION",
    "SAME_NAME_MORE_THAN_4_ALLOWED",
    "COST_REDUCTION",
    "LOCK",
    "META_EFFECT",
}


def analyze_deck_compatibility(
    decklist: DeckList,
    card_database: CardDatabase,
    ruleset: Ruleset | None = None,
) -> dict[str, Any]:
    fully_supported_count = 0
    partially_supported_count = 0
    unsupported_count = 0
    unknown_data_count = 0
    unsupported_cards: list[dict[str, Any]] = []
    unknown_cards: list[dict[str, Any]] = []
    unsupported_tags: Counter[str] = Counter()
    implemented_tags: Counter[str] = Counter()
    ability_tags: Counter[str] = Counter()
    runtime_convertible_count = 0
    runtime_blocked_count = 0
    blocked_reasons: Counter[str] = Counter()
    official_data_complete_count = 0
    missing_official_data_count = 0
    missing_fields_summary: Counter[str] = Counter()
    twinpact_count = 0
    twinpact_blocked_count = 0

    for entry in decklist.cards:
        card = card_database.get(entry.card_id)
        unknown_fields = unknown_data_fields(card)
        missing_fields = missing_official_data_fields(card)
        runtime_reasons = runtime_blocked_reasons(card)
        if card.is_twinpact:
            twinpact_count += entry.count
            if "twinpact_unsupported" in runtime_reasons:
                twinpact_blocked_count += entry.count
        if missing_fields:
            missing_official_data_count += entry.count
            missing_fields_summary.update({field: entry.count for field in missing_fields})
        else:
            official_data_complete_count += entry.count
        if runtime_reasons:
            runtime_blocked_count += entry.count
            blocked_reasons.update({reason: entry.count for reason in runtime_reasons})
        else:
            runtime_convertible_count += entry.count
        ability_tags.update({tag: entry.count for tag in card.ability_tags})
        implemented_tags.update({tag: entry.count for tag in card.implemented_tags})
        unsupported_tags.update({tag: entry.count for tag in card.unsupported_tags})
        if unknown_fields:
            unknown_data_count += entry.count
            unknown_cards.append(
                {
                    "card_id": card.card_id,
                    "name": card.name,
                    "count": entry.count,
                    "unknown_fields": list(unknown_fields),
                }
            )
        if not card.unsupported_tags and not unknown_fields:
            fully_supported_count += entry.count
        elif card.implemented_tags and not unknown_fields:
            partially_supported_count += entry.count
        else:
            unsupported_count += entry.count
        if card.unsupported_tags:
            unsupported_cards.append(
                {
                    "card_id": card.card_id,
                    "name": card.name,
                    "count": entry.count,
                    "unsupported_tags": list(card.unsupported_tags),
                }
            )

    total = decklist.total_cards
    risk_ratio = (unsupported_count + unknown_data_count) / total if total else 1.0
    reliability = "High" if unsupported_count == 0 and unknown_data_count == 0 else "Medium" if risk_ratio < 0.20 else "Low"
    ruleset_violations = validate_deck_against_ruleset(decklist, ruleset) if ruleset is not None else {
        "banned": [],
        "restricted": [],
        "not_allowed": [],
        "too_many_copies": [],
    }
    construction_legal = not any(ruleset_violations.values())
    same_name_exceptions_used = _same_name_exceptions_used(decklist, ruleset)
    high_priority_missing_tags = sorted(tag for tag in unsupported_tags if tag in HIGH_PRIORITY_TAGS)
    if runtime_convertible_count == total and not high_priority_missing_tags and construction_legal:
        simulation_readiness = "Ready"
    elif runtime_convertible_count > 0 and not high_priority_missing_tags and construction_legal:
        simulation_readiness = "Partial"
    else:
        simulation_readiness = "Blocked"
    return {
        "deck_name": decklist.name,
        "total_cards": total,
        "unique_cards": len(decklist.cards),
        "fully_supported_count": fully_supported_count,
        "partially_supported_count": partially_supported_count,
        "unsupported_count": unsupported_count,
        "unknown_data_count": unknown_data_count,
        "official_data_complete_count": official_data_complete_count,
        "missing_official_data_count": missing_official_data_count,
        "twinpact_count": twinpact_count,
        "twinpact_blocked_count": twinpact_blocked_count,
        "missing_fields_summary": dict(sorted(missing_fields_summary.items())),
        "unsupported_cards": unsupported_cards,
        "unknown_cards": unknown_cards,
        "unsupported_tags_summary": dict(sorted(unsupported_tags.items())),
        "ability_tags_summary": dict(sorted(ability_tags.items())),
        "implemented_tags_summary": dict(sorted(implemented_tags.items())),
        "high_priority_missing_tags": high_priority_missing_tags,
        "construction_legal": construction_legal,
        "ruleset_violations": ruleset_violations,
        "same_name_exceptions_used": same_name_exceptions_used,
        "runtime_convertible_count": runtime_convertible_count,
        "runtime_blocked_count": runtime_blocked_count,
        "blocked_reasons": dict(sorted(blocked_reasons.items())),
        "simulation_readiness": simulation_readiness,
        "reliability": reliability,
    }


def _same_name_exceptions_used(decklist: DeckList, ruleset: Ruleset | None) -> list[str]:
    if ruleset is None:
        return []
    exceptions = set(ruleset.same_name_exception_card_ids)
    return [
        entry.card_id
        for entry in decklist.cards
        if entry.count > ruleset.max_copies_per_card and entry.card_id in exceptions
    ]
