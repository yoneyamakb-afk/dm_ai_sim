from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from dm_ai_sim.deck_loader import DeckList


@dataclass(frozen=True, slots=True)
class Ruleset:
    ruleset_id: str
    name: str
    comprehensive_rules_version: str
    banlist_effective_date: str
    allowed_card_ids: tuple[str, ...]
    banned_card_ids: tuple[str, ...]
    restricted_card_ids: tuple[str, ...]
    max_copies_per_card: int = 4
    same_name_exception_card_ids: tuple[str, ...] = ()
    hall_of_fame_card_ids: tuple[str, ...] = ()
    premium_hall_of_fame_card_ids: tuple[str, ...] = ()
    regulation_date: str = ""
    notes: str = ""


def load_ruleset(path: str | Path) -> Ruleset:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return Ruleset(
        ruleset_id=str(raw["ruleset_id"]),
        name=str(raw["name"]),
        comprehensive_rules_version=str(raw.get("comprehensive_rules_version", "")),
        banlist_effective_date=str(raw.get("banlist_effective_date", "")),
        allowed_card_ids=tuple(str(value) for value in raw.get("allowed_card_ids", ())),
        banned_card_ids=tuple(str(value) for value in raw.get("banned_card_ids", ())),
        restricted_card_ids=tuple(str(value) for value in raw.get("restricted_card_ids", ())),
        max_copies_per_card=int(raw.get("max_copies_per_card", 4)),
        same_name_exception_card_ids=tuple(str(value) for value in raw.get("same_name_exception_card_ids", ())),
        hall_of_fame_card_ids=tuple(str(value) for value in raw.get("hall_of_fame_card_ids", ())),
        premium_hall_of_fame_card_ids=tuple(str(value) for value in raw.get("premium_hall_of_fame_card_ids", ())),
        regulation_date=str(raw.get("regulation_date", raw.get("banlist_effective_date", ""))),
        notes=str(raw.get("notes", "")),
    )


def validate_deck_against_ruleset(decklist: DeckList, ruleset: Ruleset) -> dict[str, list[str]]:
    banned = set(ruleset.banned_card_ids)
    restricted = set(ruleset.restricted_card_ids)
    allowed = set(ruleset.allowed_card_ids)
    exceptions = set(ruleset.same_name_exception_card_ids)
    violations: dict[str, list[str]] = {"banned": [], "restricted": [], "not_allowed": [], "too_many_copies": []}
    for entry in decklist.cards:
        if entry.card_id in banned:
            violations["banned"].append(entry.card_id)
        if entry.card_id in restricted and entry.count > 1:
            violations["restricted"].append(entry.card_id)
        if allowed and entry.card_id not in allowed:
            violations["not_allowed"].append(entry.card_id)
        if entry.count > ruleset.max_copies_per_card and entry.card_id not in exceptions:
            violations["too_many_copies"].append(entry.card_id)
    return violations
