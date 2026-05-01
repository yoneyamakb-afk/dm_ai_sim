# Rule Engine Architecture

この文書はフェーズ4-J時点の最小アーキテクチャ方針です。今回は大規模リファクタではありません。既存挙動を壊さず、まずは薄い抽象化から始めます。

## Core Rules Engine

Core Rules Engineは、カード個別能力に依存しにくい基本進行を担当します。

- ターン進行
- フェーズ管理
- ゾーン管理
- マナ支払い
- 召喚と呪文詠唱の基本処理
- 攻撃宣言、ブロック、バトル、シールド処理
- 状態不変条件
- 基本legal actions生成
- action mask生成

`env.py` と `rules.py` は当面この領域を担当します。ただし、個別カード名や能力タグごとの処理をここへ増やし続ける方針は取りません。

## Ability System

Ability Systemは、能力タグや個別カード能力によって基本ルールを変更する処理を担当します。

- 攻撃可否の変更
- カード能力による追加Action生成
- イベント発生時の誘発処理
- シールドブレイク時の能力処理
- 常在効果、禁止効果、置換効果の将来受け皿

フェーズ4-Jでは `dm_ai_sim.events` と `dm_ai_sim.ability_handlers` を追加しました。全能力を移したわけではなく、`SPEED_ATTACKER` と `G_STRIKE` の一部だけをhandler経由にしています。

## Attack Permission Utility

フェーズ4-J2で `dm_ai_sim.attack_permissions` を追加しました。攻撃できるかどうかは、原則この共通ユーティリティを使って判定します。

- `can_creature_attack(env, player_id, creature_index)`
- `get_attackable_creatures(env, player_id)`
- `can_be_gstrike_target(env, attacker_player, creature_index)`
- `get_gstrike_targets(env, attacker_player)`

この判定は、ATTACKフェーズ、pending attackなし、ゲーム未終了、タップ状態、召喚酔い、`SPEED_ATTACKER`、`INVASION` / `ATTACKING_CREATURE_EVOLUTION`、`cannot_attack_this_turn`、AbilityHandlerの攻撃可否修正をまとめて確認します。

`AbilityHandler.modifies_attack_permission()` が `False` を返した場合は攻撃不可を優先します。将来の `LOCK`、`META_EFFECT`、攻撃制限能力はここに接続します。個別能力側で独自の攻撃可否判定を増やさず、必要な場合はこのユーティリティにhookを追加します。

## Shield Break Utility

フェーズ4-J3で `dm_ai_sim.shield_breaks` を追加しました。シールドブレイク、S・トリガー、G・ストライク、通常カードの手札移動は、原則この共通ユーティリティを使って処理します。

- `break_one_shield(env, attacker_player, defender_player, shield_index, attacker_instance, info)`
- `break_shields(env, attacker_player, defender_player, count, attacker_instance, info)`
- `collect_shields_to_break(env, defender_player, count)`
- `resolve_broken_shields(env, attacker_player, defender_player, contexts, attacker_instance, info)`
- `ShieldBreakResult`

フェーズ4-J4で、複数ブレイクは公式ルールに近づけるため「先に対象シールドをまとめてシールドゾーンから取り除き、その後S・トリガー/G・ストライクを自動順で処理する」方針に寄せました。フェーズ4-Kでは、通常の `ATTACK_SHIELD` が攻撃クリーチャーの `breaker_count` を参照して `break_shields` を呼ぶようになりました。`DOUBLE_BREAKER` は `breaker_count=2` として本番経路で有効です。詳細は [MULTI_BREAK_RULES.md](MULTI_BREAK_RULES.md) を参照してください。

複数ブレイクの暫定方針:

- シールドが足りない場合は存在する分だけ処理する。
- 各シールドを順番に処理し、各カードごとにS・トリガー/G・ストライクを解決する。
- `DESTROY_ATTACKER` で攻撃クリーチャーが破壊された場合でも、同時に選ばれたシールドはブレイク済みとして最後まで解決する。
- 複数S・トリガーの防御側任意順選択は未実装で、現在は自動順で処理する。

通常ブレイク、S・トリガー、G・ストライク、ログ用infoは同じ経路に寄せます。個別能力が独自にシールドをpopしたり、手札/墓地へ直接振り分けたりすることは避けます。

## Event-Driven Direction

`EventType` と `Event` は、今後の能力処理が「何が起きたか」に反応できるようにする受け皿です。現時点では全イベントを実際に発火しません。まず型を固定し、今後の実装で必要な箇所から段階的に発火します。

想定例:

- `ATTACK_PERMISSION_CHECK`: 攻撃可能判定
- `ACTION_GENERATION`: 能力による追加Action生成
- `SHIELD_BROKEN`: `shield_breaks` から将来的に発火する候補。G・ストライク、S・トリガー、複数ブレイク処理と連携する。
- `GACHINKO_JUDGE_RESOLVED`: ハチ公やプリン裁定ログ
- `CARD_MOVED`: 進化元を含むゾーン移動、置換効果

## Adding New Abilities

新しい能力を追加する時は、原則として以下の順で進めます。

1. `ability_tags` / `implemented_tags` / `unsupported_tags` を整理する。
2. 能力が基本ルールそのものか、カード能力による修正かを判断する。
3. カード能力なら `AbilityHandler` を作る。
4. 必要なイベントまたはhookだけをCore Rules Engineから呼ぶ。
5. Reference Deck単位の確認デッキ、評価CLI、ログ解析、テストを追加する。

今後の `LOCK`、`META_EFFECT` は、原則AbilityHandlerに追加します。`DOUBLE_BREAKER` は攻撃解決の基本ルール寄りの `breaker_count` として先に接続しました。`COST_REDUCTION` は《フェアリー・ギフト》向けに通常SUMMONの支払いhookへ最小接続していますが、より汎用の軽減/増加/置換効果へ広げる場合はhandler化を検討します。

## Why Not CLIPS Or A DSL Yet

現時点ではCLIPSや本格DSLは導入しません。

- まだ対象カードがReference Deck 02中心で、必要なhookの形が固まり切っていない。
- Python handlerで十分にテスト可能な粒度が作れる。
- DSLを早く入れると、未確定のルール構造まで固定してしまう。
- まず既存テストを壊さない小さな移行経路を作る方が安全。

将来的には、安定したhandler APIをもとに `RuleSpec` JSONや小さなDSLへ寄せる余地を残します。DSL化する場合でも、最初はAbilityHandlerの入力データを外部化する形から始めます。

## Reference Deck 02 Migration

Reference Deck 02向け能力は、段階的にAbilityHandlerへ移します。

- `SPEED_ATTACKER`: 攻撃可否hookへ移行開始。
- `G_STRIKE`: 対象選択と適用をhandlerへ移行開始。
- `HACHIKO_GACHINKO`: 当面は既存env.py処理を維持し、イベント化候補。
- `TWINPACT`: カード表現とside選択がCore寄りなので、まず現状維持。
- `REVOLUTION_CHANGE` / `INVASION`: 追加Action生成と解決のhandler化候補。
- `DOUBLE_BREAKER`: `breaker_count` + `shield_breaks.break_shields(count=breaker_count)` で実処理済み。今後は `SHIELD_BROKEN` 系イベント発火へ寄せる。
- `COST_REDUCTION`: 《フェアリー・ギフト》の次CREATURE召喚軽減のみ実装済み。SPELL、REVOLUTION_CHANGE、INVASION、S・トリガー、ガチンコ展開には適用しない。
- `LOCK` / `META_EFFECT`: action generationや `attack_permissions` への禁止効果としてhandler化する。

この移行は一度に行いません。各フェーズで対象能力を限定し、診断CLIと既存評価CLIが壊れていないことを確認しながら進めます。
