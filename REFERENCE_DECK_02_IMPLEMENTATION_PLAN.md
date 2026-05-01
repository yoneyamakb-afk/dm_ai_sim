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

Implemented in phase 4-F:

- `TWINPACT` has a minimal runtime representation.
- Runtime `Card` can hold `top_side` and `bottom_side` while remaining one physical card in deck, hand, mana, shield, and graveyard.
- Top-side `CREATURE` summon is supported.
- Bottom-side `SPELL` cast is supported.
- Bottom-side S-trigger auto-resolution is supported when side data has `shield_trigger` and `trigger_effect`.
- Action IDs remain unchanged; legal actions carry `side="top"` or `side="bottom"` internally for twinpact use.
- `data/decks/twinpact_runtime_test_deck.json` exists only for twinpact behavior verification.

Implemented in phase 4-G:

- `G_STRIKE` has a simplified runtime implementation.
- G・ストライク cards revealed from shields are automatically used, then added to hand.
- The selected opposing creature gets `cannot_attack_this_turn=True`; the flag is cleared when turns advance.
- Twinpact cards can expose G・ストライク through the whole card, top side, or bottom side.
- 《綺羅王女プリン / ハンター☆エイリアン仲良しビーム》 is treated as the Reference Deck 02 G・ストライク target card for this phase.
- Gachinko Judge now records twinpact reveal cost source. For Prin, the judge cost source is `bottom_spell_cost`, matching the official Q&A ruling that the creature side can be put out even when the spell-side cost is referenced.
- `data/decks/gstrike_runtime_test_deck.json` exists only for G・ストライク behavior verification.

Implemented in phase 4-H:

- `REVOLUTION_CHANGE` has a minimal runtime implementation.
- In the attack phase, a hand card with `REVOLUTION_CHANGE` can return an attack-capable own creature to hand and enter the battle zone for no mana payment.
- The implementation is a special summon action, not a full attack replacement model.
- A simple one-revolution-change-per-turn guard is used to avoid repeated loops.
- Action space increased from 384 to 512. IDs 384-463 are `REVOLUTION_CHANGE(hand_index 0-9, attacker_index 0-7)`.
- Red Girazone has `REVOLUTION_CHANGE`, `SPEED_ATTACKER`, and `DOUBLE_BREAKER` data implemented; `META_EFFECT` remains unsupported.
- `data/decks/revolution_change_runtime_test_deck.json` exists only for revolution change behavior verification.

Implemented in phase 4-I:

- `INVASION` has a minimal runtime implementation for 《熱き侵略 レッドゾーンZ》.
- Runtime `Creature` can hold `evolution_sources`.
- In the attack phase, a hand card with `INVASION` can enter on top of an attack-capable own creature for no mana payment.
- The source creature and existing evolution sources are kept under the new creature for zone consistency.
- Evolved creatures are attack-ready in this simplified model.
- When an evolved creature is destroyed or returned to hand by current simplified effects, the top card and all sources move together.
- Action space increased from 512 to 640. IDs 512-591 are `INVASION(hand_index 0-9, attacker_index 0-7)`.
- `DOUBLE_BREAKER` is represented as `breaker_count=2`; full shield breaking is implemented in phase 4-K.
- `data/decks/invasion_runtime_test_deck.json` exists only for invasion behavior verification.

Implemented in phase 4-K:

- `ATTACK_SHIELD` now uses the attacking creature's `breaker_count`.
- `DOUBLE_BREAKER` cards break up to two shields through the shared `shield_breaks` path.
- Multiple shields are removed from the shield zone before S-trigger/G-Strike/hand movement resolution.
- `DESTROY_ATTACKER` does not stop other shields already selected in the same break batch.
- `data/decks/double_breaker_runtime_test_deck.json` exists only for double breaker behavior verification.
- `evaluate_double_breaker` and `analyze_double_breaker_logs` summarize double-break attacks and multi-break batches.

Implemented in phase 4-L:

- `COST_REDUCTION` has a minimal runtime implementation for 《フェアリー・ギフト》.
- Casting Fairy Gift creates a temporary next-CREATURE summon cost reduction of 3.
- The reduction applies only to normal `SUMMON`, including twinpact top-side CREATURE summon.
- It does not apply to SPELL casts, REVOLUTION_CHANGE, INVASION, S-trigger summons, or Hachiko's Gachinko same-name summon.
- Unused reduction expires at turn end.
- `data/decks/cost_reduction_runtime_test_deck.json` exists only for cost-reduction behavior verification.
- `evaluate_cost_reduction` and `analyze_cost_reduction_logs` summarize casts, usage, enabled summons, and expiry.

## Card-by-Card Status

| Card | Count | Official data status | Runtime feasibility | Unsupported tags | Priority |
|---|---:|---|---|---|---|
| 特攻の忠剣ハチ公 | 9 | Cost, civilization, type, power, race, and text summary entered. | Runtime-convertible. Simplified attack-end Gachinko same-name summon implemented. | none | Done for stage 1 |
| 轟く革命 レッドギラゾーン | 3 | Static fields entered from official data. | Minimal revolution change, speed attacker, and double breaker work. Still blocked by meta behavior. | `META_EFFECT` | High |
| 熱き侵略 レッドゾーンZ | 1 | Static fields entered from official data; power corrected to 11000. | Minimal invasion/evolution and double breaker work. Shield burn/meta behavior remains blocked. | `META_EFFECT` | High |
| 配球の超人 / 記録的剛球 | 4 | Twinpact side data entered. | Runtime-convertible. Top summon and bottom `MANA_BOOST` cast can run. | none | Done for minimal twinpact |
| D2V3 終断のレッドトロン / フォビドゥン・ハンド | 4 | Twinpact side data entered. | Runtime-convertible. Bottom destroy/S-trigger path can run. | none | Done for minimal twinpact |
| Q.Q.QX. / 終葬 5.S.D. | 4 | Twinpact side data entered for core static fields and special-win/lock summary. | Twinpact runtime structure works, but lock/alternate-win behavior remains blocked. | `LOCK`, `ALTERNATE_WIN_CONDITION` | High |
| 綺羅王女プリン / ハンター☆エイリアン仲良しビーム | 4 | Twinpact side data entered. | Runtime-convertible. Simplified G・ストライク and Prin Gachinko ruling log support are implemented. | none | Done for stage 3 |
| フェアリー・ギフト | 1 | Static fields entered from official data. | Runtime-convertible. Minimal next-CREATURE summon cost reduction works. | none | Done for minimal cost reduction |
| 悪魔世界の閃光 | 2 | Still needs official confirmation. | Blocked by unknown official fields. | `DESTROY` | Medium |
| 逆転の剣スカイソード | 4 | Civilization, type, and text summary entered from official search; cost, power, and races remain pending. | Blocked by unknown static fields and card-specific ability. | `MANA_BOOST`, `GAIN_SHIELD` | Medium |
| 青銅のバンビシカット / 「我が力、しかと見よ！」 | 4 | Twinpact side data entered. | Twinpact runtime structure works, but card-specific mana cheating remains blocked. | `MANA_BOOST` | Medium |

## Twinpact Cards

- `DM_REF_017` 配球の超人 / 記録的剛球
- `DM_REF_018` D2V3 終断のレッドトロン / フォビドゥン・ハンド
- `DM_REF_019` Q.Q.QX. / 終葬 5.S.D.
- `DM_REF_020` 綺羅王女プリン / ハンター☆エイリアン仲良しビーム
- `DM_REF_024` 青銅のバンビシカット / 「我が力、しかと見よ！」

All twinpact cards now load into `CardData` and runtime `Card` with `is_twinpact`, `top_side`, and `bottom_side`. They remain one physical card, and only the used side becomes the summon/spell face for payment and resolution.

## Non-Twinpact Cards Likely First to Run

- `DM_REF_021` フェアリー・ギフト: static data is complete and minimal `COST_REDUCTION` is implemented.
- `DM_REF_023` 逆転の剣スカイソード: partial static data is available, but cost, power, races, and card-specific handling need confirmation.
- `DM_REF_014` 特攻の忠剣ハチ公: central to the deck and now usable for focused runtime tests.

## Ability Implementation Priority

High:

- `SAME_NAME_MORE_THAN_4_ALLOWED`
- `REVOLUTION_CHANGE`
- `G_STRIKE`
- `SHIELD_TRIGGER`
- `LOCK`
- `META_EFFECT`
- `ALTERNATE_WIN_CONDITION`

Medium:

- `DESTROY`
- `MANA_BOOST`
- `GAIN_SHIELD`
- `SEARCH`
- Additional card-specific mana boost/gain shield effects

Low:

- Exact card-specific reproduction for shield burn and lower-priority card text should wait until the base mechanics above exist.

Next structural targets are `LOCK`, `META_EFFECT`, and `ALTERNATE_WIN_CONDITION`. More detailed Revolution Change/Invasion timing, exact command-condition filtering, and defender-selected multi-trigger order remain future work.
