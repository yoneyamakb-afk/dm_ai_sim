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

## Event-Driven Direction

`EventType` と `Event` は、今後の能力処理が「何が起きたか」に反応できるようにする受け皿です。現時点では全イベントを実際に発火しません。まず型を固定し、今後の実装で必要な箇所から段階的に発火します。

想定例:

- `ATTACK_PERMISSION_CHECK`: 攻撃可能判定
- `ACTION_GENERATION`: 能力による追加Action生成
- `SHIELD_BROKEN`: G・ストライク、S・トリガー、将来の複数ブレイク処理
- `GACHINKO_JUDGE_RESOLVED`: ハチ公やプリン裁定ログ
- `CARD_MOVED`: 進化元を含むゾーン移動、置換効果

## Adding New Abilities

新しい能力を追加する時は、原則として以下の順で進めます。

1. `ability_tags` / `implemented_tags` / `unsupported_tags` を整理する。
2. 能力が基本ルールそのものか、カード能力による修正かを判断する。
3. カード能力なら `AbilityHandler` を作る。
4. 必要なイベントまたはhookだけをCore Rules Engineから呼ぶ。
5. Reference Deck単位の確認デッキ、評価CLI、ログ解析、テストを追加する。

今後の `DOUBLE_BREAKER`、`COST_REDUCTION`、`LOCK`、`META_EFFECT` は、原則AbilityHandlerに追加します。Core Rules Engineへ直接カード能力処理を増やすのは、ゾーン移動や攻撃解決など本当に基本ルールへ属する場合だけにします。

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
- `DOUBLE_BREAKER`: 次に入れるならhandler + `SHIELD_BROKEN` 系イベントで扱う。
- `COST_REDUCTION`: 支払い計算hookとしてhandler化する。
- `LOCK` / `META_EFFECT`: action generationやpermission checkへの禁止効果としてhandler化する。

この移行は一度に行いません。各フェーズで対象能力を限定し、診断CLIと既存評価CLIが壊れていないことを確認しながら進めます。
