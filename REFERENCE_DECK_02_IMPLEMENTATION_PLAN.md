# Reference Deck 02 Implementation Plan

Reference Deck 02 is the priority target for the next real-card simulation work. The goal is not full reproduction yet; it is to identify which cards can enter the current runtime, which cards are blocked by missing official data, and which ability tags must be implemented first.

Current conclusion: the deck is construction-legal under `reference_ruleset.json` because 《特攻の忠剣ハチ公》 is a confirmed same-name count exception. It is not yet simulation-ready because all 40 cards still have unknown official data and many high-priority unsupported tags.

## Engine Support Baseline

Currently supported by the runtime:

- `CREATURE`
- `SPELL`
- `BLOCKER`
- `SHIELD_TRIGGER` in simplified S-trigger form
- `DRAW_1`
- `DESTROY_TARGET`
- `DESTROY_ATTACKER`
- `GAIN_SHIELD`
- `MANA_BOOST`
- Civilization payment
- Multicolor mana tap-in
- Optional blocking
- Normal spell casting

Not yet supported or requiring card-specific implementation:

- `SPEED_ATTACKER`
- `DOUBLE_BREAKER` / multiple breaks
- `REVOLUTION_CHANGE`
- `INVASION`
- `G_STRIKE`
- `TWINPACT`
- `COST_REDUCTION`
- `LOCK`
- `SEARCH`
- `META_EFFECT`
- Individual card text

## Card Status

| Card | Count | Current data | Unknown fields | ability_tags | implemented_tags | unsupported_tags | Runtime status | Priority |
|---|---:|---|---|---|---|---|---|---|
| 特攻の忠剣ハチ公 | 9 | name, count, same-name exception | cost, civilizations, card_type, power | `SAME_NAME_MORE_THAN_4_ALLOWED` | `SAME_NAME_MORE_THAN_4_ALLOWED` | none | Blocked by unknown data | High |
| 轟く革命 レッドギラゾーン | 3 | name, count, tags | cost, civilizations, card_type, power | `REVOLUTION_CHANGE`, `SPEED_ATTACKER` | none | `REVOLUTION_CHANGE`, `SPEED_ATTACKER` | Blocked | High |
| 熱き侵略 レッドゾーンZ | 1 | name, count, tags | cost, civilizations, card_type, power | `INVASION` | none | `INVASION` | Blocked | High |
| 配球の超人 / 記録的剛球 | 4 | name, count, twinpact tag | cost, civilizations, card_type, power | `TWINPACT` | none | `TWINPACT` | Blocked | High |
| D2V3 終断のレッドトロン / フォビドゥン・ハンド | 4 | name, count, tags | cost, civilizations, card_type, power | `TWINPACT`, `DESTROY`, `SHIELD_TRIGGER` | none | `TWINPACT`, `DESTROY`, `SHIELD_TRIGGER` | Blocked | High |
| Q.Q.QX. / 終葬 5.S.D. | 4 | name, count, tags | cost, civilizations, card_type, power | `TWINPACT`, `LOCK`, `ALTERNATE_WIN_CONDITION` | none | `TWINPACT`, `LOCK`, `ALTERNATE_WIN_CONDITION` | Blocked | High |
| 綺羅王女プリン / ハンター☆エイリアン仲良しビーム | 4 | name, count, tags | cost, civilizations, card_type, power | `TWINPACT`, `G_STRIKE` | none | `TWINPACT`, `G_STRIKE` | Blocked | High |
| フェアリー・ギフト | 1 | name, count, tag | cost, civilizations, card_type | `COST_REDUCTION` | none | `COST_REDUCTION` | Blocked | High |
| 悪魔世界の閃光 | 2 | name, count, tag | cost, civilizations, card_type | `DESTROY` | none | `DESTROY` | Blocked | Medium |
| 逆転の剣スカイソード | 4 | name, count, tags | cost, civilizations, card_type, power | `MANA_BOOST`, `GAIN_SHIELD` | none | `MANA_BOOST`, `GAIN_SHIELD` | Blocked | Medium |
| 青銅のバンビシカット / 「我が力、しかと見よ！」 | 4 | name, count, tags | cost, civilizations, card_type, power | `TWINPACT`, `MANA_BOOST` | none | `TWINPACT`, `MANA_BOOST` | Blocked | High |

## Provisional Runtime Policy

Do not silently convert unknown cards into fake `COLORLESS` creatures or zero-cost placeholders. `deck_to_runtime_cards(..., allow_placeholder=False)` blocks these cards with explicit reasons such as `missing_cost`, `missing_civilizations`, `missing_card_type`, `unknown_power`, and `unsupported_tags`.

This is intentional. Incorrect card data is more dangerous than no data for competitive evaluation.

## Shortest Route To First Playable Approximation

1. Fill official data for the 11 unique cards: cost, civilizations, card type, power, races, trigger flags.
2. Add twinpact data structure or a controlled approximation for twinpact cards.
3. Keep Hachiko deck construction exception as a permanent ruleset feature.
4. Implement high-impact mechanics in this order: `TWINPACT`, `REVOLUTION_CHANGE`, `INVASION`, `SPEED_ATTACKER`, `G_STRIKE`, `COST_REDUCTION`, `LOCK` / `META_EFFECT`.
5. Add card-specific handlers for Q.Q.QX., Red Girazone, Red Zone Z, Hachiko, and Fairy Gift.

