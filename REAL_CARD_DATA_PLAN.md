# Real Card Data Plan

実カードデータ対応は、全カード能力の完全再現から始めません。まずカードデータを読み込めるようにし、未対応能力をタグ化し、対象デッキ・対象メタに含まれるカードから優先的に能力を実装します。

## 取り込み時期

次の大きな工程は、実カードデータの最小スキーマ導入です。ルール監査が終わった現在、次に入れるべきは「カードを読み込めるが、能力は未対応なら警告する」段階です。

## 持つ情報

- card id
- name
- cost
- civilizations
- card types
- power
- race
- abilities raw text
- ability tags
- shield trigger
- blocker
- breaker count
- speed attacker
- g strike
- twinpact fields
- regulation legality
- hall of fame / premium hall of fame status
- source set

## 未対応能力の扱い

- 能力テキストを保存する。
- パーサーが能力タグを付与する。
- 未対応タグがあるカードは `unsupported` または `partial` として扱う。
- 対戦実行前にデッキ互換性レポートを出す。
- 未対応能力は無視して対戦するか、評価対象から除外するかを設定で選ぶ。

## 対象デッキ単位の方針

全カードを一気に再現せず、まず評価したいデッキを決めます。そのデッキと主要メタに含まれるカードから能力を実装します。

優先順:

1. 対象デッキの勝敗に直結する能力
2. 主要メタカードの妨害能力
3. 汎用受け札
4. 汎用初動
5. 低頻度カード

## レギュレーション・殿堂管理

- レギュレーションをデータとして分離する。
- カードごとに使用可能フォーマットを持つ。
- 殿堂・プレミアム殿堂・コンビ殿堂を別テーブルで管理する。
- 評価時にデッキリストを検証し、違反をエラーまたは警告にする。

## カード個別裁定

- 能力タグだけで表現できないカードは個別ハンドラを持つ。
- 個別ハンドラには対象カード、対応範囲、未対応ケース、テストケースを記録する。
- 裁定メモはコードコメントではなくデータ/Markdownに残す。

## デッキ互換性レポート例

```text
Deck compatibility:
- fully supported: 28/40
- partially supported: 8/40
- unsupported: 4/40
- reliability: Medium
```

互換性の目安:

- High: 主要な勝ち筋と防御札がほぼ再現される。
- Medium: 一部能力を簡略化しているが、速度や大まかな相性は見られる。
- Low: 未対応能力が多く、評価結果を信用しにくい。

## 4-Aで追加した入口

サンプルデータは `data/cards/sample_cards.json`、`data/decks/sample_deck.json`、`data/rulesets/sample_ruleset.json` に置きます。カード能力は `ability_tags` で人間が明示し、現在のランタイムで処理できるものを `implemented_tags`、未対応のものを `unsupported_tags` に分けます。

`unsupported_tags` があるカードも `strict=False` では読み込めますが、互換性レポートの信頼度を下げます。`strict=True` では例外にして、未対応能力を含むデッキを評価から除外できます。

Rulesetはまず `banned_card_ids` と `restricted_card_ids` の簡易チェックから始めます。実運用では殿堂日付、フォーマット、カードプール、同名カード扱いを追加します。

## Reference Deck Intake

4-Bで提出参考デッキを取り込みました。

- `data/cards/reference_cards.json`
- `data/decks/reference_deck_01.json`
- `data/decks/reference_deck_02.json`
- `data/rulesets/reference_ruleset.json`
- `REFERENCE_DECK_COMPATIBILITY.md`

公式データ未確認の項目は `null` または `UNKNOWN` とし、`notes` に `needs_official_data` を記録します。不確かなコスト、文明、パワー、カードタイプを推定値として入力しません。

《特攻の忠剣ハチ公》はユーザー指示により、4枚超過可能カードの確定仕様として `SAME_NAME_MORE_THAN_4_ALLOWED` を付与し、reference ruleset の `same_name_exception_card_ids` に記録します。

Reference Deck 02を優先対象にします。まずハチ公デッキに含まれるカードの公式データを補完し、次に `TWINPACT`、`REVOLUTION_CHANGE`、`INVASION`、`SPEED_ATTACKER`、`G_STRIKE`、`COST_REDUCTION`、`LOCK` / `META_EFFECT` を対象デッキ優先で実装します。全カード対応ではなく、対象デッキと対象メタに含まれるカードから進めます。

## Reference Deck 02 Stage 1 Ability Work

4-EでReference Deck 02優先対応の第1段階として、《特攻の忠剣ハチ公》本体能力を簡易実装しました。

- `SAME_NAME_MORE_THAN_4_ALLOWED` は構築ルールで対応済み。
- `SPEED_ATTACKER` は攻撃可能判定で召喚酔いを無視できる能力として対応済み。
- `GACHINKO_JUDGE`、`SEARCH_SAME_NAME`、`PUT_FROM_DECK_TO_BATTLE_ZONE` はハチ公の攻撃終了時能力として簡易対応済み。
- 公式の「出してもよい」は現時点では自動展開です。将来は任意選択Actionへ切り出す余地があります。
- `data/decks/hachiko_runtime_test_deck.json` は能力確認用であり、大会評価用デッキではありません。

次候補は `TWINPACT` と `G_STRIKE`、または `REVOLUTION_CHANGE` / `INVASION` です。

## Reference Deck 02 Stage 2 Twinpact Work

4-Fで対象デッキ優先の `TWINPACT` 最小実装を追加しました。

- ツインパクトカードはランタイムでも1枚のカードとして保持します。
- `top_side` が `CREATURE` なら上側召喚できます。
- `bottom_side` が `SPELL` なら下側詠唱できます。
- マナ、シールド、墓地では元カード1枚として移動します。
- 下側にS・トリガー情報がある場合、初期版では自動発動します。
- action ID空間は維持し、`Action.side` で `"top"` / `"bottom"` を保持します。

詳細な裁定、両面にまたがる常在能力、複雑な置換効果、任意選択は今後の課題です。次候補は `G_STRIKE`、`REVOLUTION_CHANGE`、`INVASION` です。

## Reference Deck 02 Stage 3 G-Strike Work

4-Gで対象デッキ優先の `G_STRIKE` 簡易実装を追加しました。

- G・ストライクはシールドから手札に加わる時に自動使用します。
- 対象は攻撃可能、SPEED_ATTACKER/ハチ公、高パワーの順で自動選択します。
- 対象クリーチャーには `cannot_attack_this_turn` を付与し、ターン進行時に解除します。
- G・ストライク使用後、そのカードは手札へ加わります。
- ツインパクトの場合、カード全体、上側、下側の `G_STRIKE` タグを確認します。
- 《綺羅王女プリン / ハンター☆エイリアン仲良しビーム》がガチンコ・ジャッジで表向きになった場合、公式Q&A（https://dm.takaratomy.co.jp/rule/qa/38694/）由来の特別裁定として `bottom_spell_cost` をjudge cost sourceに記録します。

今後は `REVOLUTION_CHANGE`、`INVASION`、`COST_REDUCTION` を順に検討します。

## Reference Deck 02 Stage 4 Revolution Change Work

4-Hで《轟く革命 レッドギラゾーン》向けに `REVOLUTION_CHANGE` 最小実装を追加しました。

- `REVOLUTION_CHANGE` はATTACKフェーズ中の特殊召喚Actionとして扱います。
- 手札の革命チェンジ持ちクリーチャーを出し、攻撃可能な自軍クリーチャーを手札へ戻します。
- 初期版ではコスト支払い・文明支払いは不要です。
- 実ルールの攻撃時置換処理や「火または自然のコマンド」などの条件は今後詳細化します。
- 1ターン1回の簡易制限で、革命チェンジを無限に繰り返さないようにしています。
- action spaceは512に拡張し、384-463を `REVOLUTION_CHANGE` 用に使います。

次候補は `INVASION` または `COST_REDUCTION` です。

## Reference Deck 02 Stage 5 Invasion Work

4-Iで《熱き侵略 レッドゾーンZ》向けに `INVASION` / `EVOLUTION` 最小実装を追加しました。

- `INVASION` はATTACKフェーズ中の特殊Actionとして扱います。
- 手札の侵略持ちクリーチャーを、攻撃可能な自軍クリーチャーの上に重ねます。
- 元クリーチャーと既存の進化元は `evolution_sources` に保持します。
- 初期版ではコスト支払い・文明支払いは不要です。
- 実ルールの「火のコマンドが攻撃する時」条件はカードデータの `invasion_condition` に残し、ランタイム条件は今後詳細化します。
- 進化クリーチャーが破壊/バウンスされる場合、現時点では上カードと進化元をまとめて移動します。
- `DOUBLE_BREAKER` は `breaker_count=2` として保持され、通常のシールド攻撃で2枚ブレイクします。
- action spaceは640に拡張し、512-591を `INVASION` 用に使います。

次候補は `COST_REDUCTION`、`LOCK`、`META_EFFECT` のいずれかです。

## Ability Handler Direction

4-Jで実カード能力を段階的に接続するためのAbilityHandler/Event土台を追加しました。

- 実カード能力は `ability_tags` から `AbilityRegistry` を通じて `AbilityHandler` へ接続します。
- 未対応タグは引き続きcompatibility診断で検出し、Reference Deck単位で優先順位を決めます。
- 対象デッキ優先でhandlerを増やし、全カード能力の一括再現は狙いません。
- `SPEED_ATTACKER` は攻撃可能判定handlerへ移行済みです。
- `G_STRIKE` は対象選択と適用をhandlerへ部分移行済みです。
- `DOUBLE_BREAKER` は攻撃解決の `breaker_count` として接続済みです。`COST_REDUCTION` は《フェアリー・ギフト》向けの通常SUMMON軽減として最小実装済みです。`LOCK`、`META_EFFECT` は原則handlerとして追加します。
- 将来的に `RuleSpec` JSONやDSLへ移行する場合も、まずはAbilityHandlerの入力データを外部化する形から進めます。

現時点ではCLIPSや本格DSLは導入しません。まずPython内の小さなhandler APIで、必要なイベント、hook、テスト境界を固めます。

## Reference Deck 02 Stage 8 Double Breaker Work

4-Kで《轟く革命 レッドギラゾーン》と《熱き侵略 レッドゾーンZ》向けに `DOUBLE_BREAKER` の実ブレイク処理を追加しました。

- `Card` は `DOUBLE_BREAKER` タグから `breaker_count=2` を推論します。
- 通常の `ATTACK_SHIELD` は攻撃クリーチャーの `breaker_count` を参照します。
- 複数ブレイクでは対象シールドを先にまとめて取り除き、その後S・トリガー/G・ストライク/通常手札移動を自動順で解決します。
- `data/decks/double_breaker_runtime_test_deck.json`、`evaluate_double_breaker`、`analyze_double_breaker_logs` を追加しました。
- `LOCK`、`META_EFFECT` は今回未実装です。

## Reference Deck 02 Stage 9 Cost Reduction Work

4-Lで《フェアリー・ギフト》向けに `COST_REDUCTION` の最小実装を追加しました。

- `CardData` 上で《フェアリー・ギフト》は `COST_REDUCTION` / `NEXT_CREATURE_COST_REDUCTION` を実装済みとして扱います。
- 唱えた後、使用者に次CREATURE通常召喚のコストを3下げる一時効果を作ります。
- 軽減は通常の `SUMMON` とツインパクト上側CREATURE召喚にだけ適用します。
- SPELL、REVOLUTION_CHANGE、INVASION、S・トリガー、ハチ公のガチンコ展開には適用しません。
- 未使用の軽減はターン終了時に失効します。
- `data/decks/cost_reduction_runtime_test_deck.json`、`evaluate_cost_reduction`、`analyze_cost_reduction_logs` を追加しました。
- 次候補は `LOCK`、`META_EFFECT`、`ALTERNATE_WIN_CONDITION` です。
