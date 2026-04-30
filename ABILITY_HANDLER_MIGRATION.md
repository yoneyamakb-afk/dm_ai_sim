# Ability Handler Migration

フェーズ4-J時点の移行表です。今回は土台作りが目的であり、全能力の移行は行っていません。

| Ability | Current location | Handler exists | Handler used | Migration status | Notes |
|---|---|---:|---:|---|---|
| SPEED_ATTACKER | `rules.can_attack`, `env._creature_can_attack_now` | yes | yes | migrated | 攻撃可能判定は `SpeedAttackerHandler` を参照。 |
| G_STRIKE | `env._resolve_shield_trigger`, `env._resolve_g_strike` | yes | yes | partial | 対象選択と適用を `GStrikeHandler` へ移行。シールド処理の入口はCore側に残す。 |
| HACHIKO_GACHINKO | `env._resolve_after_attack_triggers`, `env._resolve_gachinko_judge` | no | no | pending | `ATTACK_RESOLVED` / `GACHINKO_JUDGE_RESOLVED` イベント化候補。 |
| TWINPACT | `Card`, `CardSide`, `env`, `rules`, `card_database` | no | no | pending | カード表現はCore寄り。side別能力はhandler連携候補。 |
| REVOLUTION_CHANGE | `rules.legal_actions`, `env._resolve_revolution_change` | no | no | pending | 追加Action生成と解決をhandlerへ移す候補。 |
| INVASION | `rules.legal_actions`, `env._resolve_invasion` | no | no | pending | 追加Action生成、進化条件、置換タイミングをhandlerへ移す候補。 |
| DOUBLE_BREAKER | `Card.breaker_count` data only | no | no | handler_created_pending | 複数ブレイク処理は未実装。`SHIELD_BROKEN` イベントとhandlerで実装予定。 |
| COST_REDUCTION | card data only | no | no | not_started | 支払い計算hookとしてhandler化予定。 |
| LOCK | card data only | no | no | not_started | action generation / permission checkを制限するhandler候補。 |
| META_EFFECT | card data only | no | no | not_started | 常在効果、禁止効果、置換効果のhandler候補。 |
| GACHINKO_JUDGE | `env._resolve_gachinko_judge` | no | no | pending | ハチ公固有処理から汎用イベントへ分離予定。 |
| SAME_NAME_MORE_THAN_4_ALLOWED | `ruleset`, deck validation | no | no | intentionally_core_rule | 構築ルールなのでAbilityHandlerではなくRuleset側に残す。 |
