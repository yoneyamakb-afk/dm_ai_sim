# Ability Handler Migration

フェーズ4-J時点の移行表です。今回は土台作りが目的であり、全能力の移行は行っていません。

| Ability | Current location | Handler exists | Handler used | Migration status | Notes |
|---|---|---:|---:|---|---|
| SPEED_ATTACKER | `attack_permissions`, `rules.can_attack` | yes | yes | migrated | 攻撃可能判定は共通ユーティリティ経由で `SpeedAttackerHandler` を参照。 |
| G_STRIKE | `shield_breaks`, `GStrikeHandler` | yes | yes | partial | シールドからの発動は `shield_breaks` 経由。対象選択と適用は `GStrikeHandler`、対象候補は `attack_permissions.get_gstrike_targets` を使う。 |
| HACHIKO_GACHINKO | `env._resolve_after_attack_triggers`, `env._resolve_gachinko_judge` | no | no | pending | `ATTACK_RESOLVED` / `GACHINKO_JUDGE_RESOLVED` イベント化候補。 |
| TWINPACT | `Card`, `CardSide`, `env`, `rules`, `card_database` | no | no | pending | カード表現はCore寄り。side別能力はhandler連携候補。 |
| REVOLUTION_CHANGE | `rules.legal_actions`, `env._resolve_revolution_change` | no | no | pending | 追加Action生成と解決をhandlerへ移す候補。 |
| INVASION | `rules.legal_actions`, `env._resolve_invasion` | no | no | pending | 追加Action生成、進化条件、置換タイミングをhandlerへ移す候補。 |
| DOUBLE_BREAKER | `Card.breaker_count`, `Env._resolve_unblocked_attack`, `shield_breaks.break_shields` | no | no | implemented_core_rule | 攻撃解決が `breaker_count` 枚を同時ブレイクする。handler化は将来の汎用能力移行候補。 |
| COST_REDUCTION | `PlayerState.pending_cost_reductions`, `mana.effective_summon_cost`, `env._cast_spell` | no | no | minimal_core_rule | 《フェアリー・ギフト》の次CREATURE召喚3軽減のみ対応。SPELL、REVOLUTION_CHANGE、INVASION、S・トリガー、ガチンコ展開には適用しない。 |
| LOCK | card data only | no | no | not_started | action generation / permission checkを制限するhandler候補。 |
| META_EFFECT | card data only | no | no | not_started | 常在効果、禁止効果、置換効果のhandler候補。 |
| GACHINKO_JUDGE | `env._resolve_gachinko_judge` | no | no | pending | ハチ公固有処理から汎用イベントへ分離予定。 |
| SAME_NAME_MORE_THAN_4_ALLOWED | `ruleset`, deck validation | no | no | intentionally_core_rule | 構築ルールなのでAbilityHandlerではなくRuleset側に残す。 |

## Attack Permission Policy

攻撃可否判定は `dm_ai_sim.attack_permissions` を共通入口にします。

- `rules.can_attack` と `legal_actions` は共通ユーティリティを使います。
- `GStrikeHandler` は共通ユーティリティで「このターンまだ攻撃可能なクリーチャー」を対象候補にします。
- `HeuristicAgent` は共通ユーティリティで生成されたlegal actionsを前提にしつつ、観測上明らかに攻撃不可の候補を選ばない防御的フィルタを持ちます。
- 今後の `LOCK`、`META_EFFECT`、攻撃制限能力は `AbilityHandler.modifies_attack_permission()` から `False` を返す形で接続します。
- 個別能力handlerが独自に召喚酔い、タップ、攻撃不可状態を再判定することは避けます。

## Shield Break Policy

シールドブレイク処理は `dm_ai_sim.shield_breaks` を共通入口にします。

- `env.py` のシールド攻撃解決は `break_shields(..., count=attacker.card.breaker_count)` を呼びます。
- 通常カードの手札移動、S・トリガー、G・ストライク、ツインパクト下側S・トリガーは同じ経路で処理します。
- ログ互換のため、既存の `info["shield_broken"]`、`info["broken_shield_card"]`、`info["trigger_activated"]`、`info["g_strike_activated"]` などは維持します。
- `ShieldBreakResult` と `info["shield_break_results"]` は、複数ブレイクログに使います。`batch_id`、`break_index`、`simultaneous_count`、`trigger_resolution_order` を保持します。
- 複数ブレイクでは、対象シールドを先にまとめてシールドゾーンから取り除き、その後自動順でS・トリガー/G・ストライクを解決します。
- `DOUBLE_BREAKER` は実処理済みです。複数S・トリガーの任意順選択は未実装で、自動順です。
