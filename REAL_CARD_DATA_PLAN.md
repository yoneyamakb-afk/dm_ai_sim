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
