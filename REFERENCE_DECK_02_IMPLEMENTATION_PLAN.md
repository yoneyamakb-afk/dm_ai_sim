# Reference Deck 02 Implementation Plan

Reference Deck 02 is the Hachiko priority deck. The current phase builds the official data foundation first; it does not implement new card abilities yet.

Construction remains legal because `DM_REF_014` is listed in `data/rulesets/reference_ruleset.json` as a same-name count exception. The 9 copies of 《特攻の忠剣ハチ公》 must continue to be reported as allowed by `SAME_NAME_MORE_THAN_4_ALLOWED`.

## Current Runtime Position

The deck is still not simulation-ready. Hachiko itself is now runtime-convertible and has a first-stage simplified ability implementation, but high-impact ability tags remain unsupported, and twinpact cards are intentionally blocked until the engine can choose between top and bottom sides.

Implemented in phase 4-E:

- `SAME_NAME_MORE_THAN_4_ALLOWED` remains supported as a construction rule.
- `SPEED_ATTACKER` is supported in the attack eligibility check.
- `GACHINKO_JUDGE`, `SEARCH_SAME_NAME`, and `PUT_FROM_DECK_TO_BATTLE_ZONE` are implemented for 《特攻の忠剣ハチ公》 as a simplified automatic attack-end trigger.
- `data/decks/hachiko_runtime_test_deck.json` exists only for ability verification, not tournament evaluation.

## Card-by-Card Status

| Card | Count | Official data status | Runtime feasibility | Unsupported tags | Priority |
|---|---:|---|---|---|---|
| 特攻の忠剣ハチ公 | 9 | Cost, civilization, type, power, race, and text summary entered. | Runtime-convertible. Simplified attack-end Gachinko same-name summon implemented. | none | Done for stage 1 |
| 轟く革命 レッドギラゾーン | 3 | Static fields entered from official data. | Blocked by revolution change and combat keywords. | `REVOLUTION_CHANGE`, `SPEED_ATTACKER`, `DOUBLE_BREAKER`, `META_EFFECT` | High |
| 熱き侵略 レッドゾーンZ | 1 | Static fields entered from official data. | Blocked by evolution/invasion and shield-processing behavior. | `EVOLUTION`, `INVASION`, `DOUBLE_BREAKER`, `META_EFFECT` | High |
| 配球の超人 / 記録的剛球 | 4 | Twinpact shell added. Side names and side types are recorded; unresolved fields remain unknown. | Blocked by `TWINPACT` and missing side fields. | `TWINPACT` | High |
| D2V3 終断のレッドトロン / フォビドゥン・ハンド | 4 | Twinpact shell added. Bottom-side trigger/destroy tags retained. | Blocked by `TWINPACT` and missing side fields. | `TWINPACT`, `DESTROY`, `SHIELD_TRIGGER` | High |
| Q.Q.QX. / 終葬 5.S.D. | 4 | Twinpact side data entered for core static fields and special-win/lock summary. | Blocked by `TWINPACT` and alternate-win/lock implementation. | `TWINPACT`, `LOCK`, `ALTERNATE_WIN_CONDITION` | High |
| 綺羅王女プリン / ハンター☆エイリアン仲良しビーム | 4 | Twinpact shell added. Side names and side types are recorded; unresolved fields remain unknown. | Blocked by `TWINPACT`, `G_STRIKE`, and missing side fields. | `TWINPACT`, `G_STRIKE` | High |
| フェアリー・ギフト | 1 | Static fields entered from official data. | Runtime card can be created directly, but deck conversion blocks by unsupported cost reduction. | `COST_REDUCTION` | High |
| 悪魔世界の閃光 | 2 | Still needs official confirmation. | Blocked by unknown official fields. | `DESTROY` | Medium |
| 逆転の剣スカイソード | 4 | Civilization, type, and text summary entered from official search; cost, power, and races remain pending. | Blocked by unknown static fields and card-specific ability. | `MANA_BOOST`, `GAIN_SHIELD` | Medium |
| 青銅のバンビシカット / 「我が力、しかと見よ！」 | 4 | Twinpact shell added. Side names and side types are recorded; unresolved fields remain unknown. | Blocked by `TWINPACT` and missing side fields. | `TWINPACT`, `MANA_BOOST` | High |

## Twinpact Cards

- `DM_REF_017` 配球の超人 / 記録的剛球
- `DM_REF_018` D2V3 終断のレッドトロン / フォビドゥン・ハンド
- `DM_REF_019` Q.Q.QX. / 終葬 5.S.D.
- `DM_REF_020` 綺羅王女プリン / ハンター☆エイリアン仲良しビーム
- `DM_REF_024` 青銅のバンビシカット / 「我が力、しかと見よ！」

All twinpact cards now load into `CardData` with `is_twinpact`, `top_side`, and `bottom_side`. They deliberately do not convert into one simple runtime card.

## Non-Twinpact Cards Likely First to Run

- `DM_REF_021` フェアリー・ギフト: static data is complete, but `COST_REDUCTION` needs an implementation.
- `DM_REF_023` 逆転の剣スカイソード: partial static data is available, but cost, power, races, and card-specific handling need confirmation.
- `DM_REF_014` 特攻の忠剣ハチ公: central to the deck and now usable for focused runtime tests.

## Ability Implementation Priority

High:

- `SAME_NAME_MORE_THAN_4_ALLOWED`
- `TWINPACT`
- `REVOLUTION_CHANGE`
- `INVASION`
- `G_STRIKE`
- `SHIELD_TRIGGER`
- `COST_REDUCTION`

Medium:

- `DESTROY`
- `MANA_BOOST`
- `GAIN_SHIELD`
- `SEARCH`
- `LOCK`
- `META_EFFECT`

Low:

- Exact card-specific reproduction for alternate win conditions and shield burn should wait until the base mechanics above exist.

Next structural targets are `TWINPACT`, `G_STRIKE`, `REVOLUTION_CHANGE`, and `INVASION`.
