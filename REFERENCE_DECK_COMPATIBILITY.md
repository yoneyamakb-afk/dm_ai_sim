# Reference Deck Compatibility

この文書は、提出された `ViewDeckSheet(1).pdf` と `ViewDeckSheet(2).pdf` をもとに作成した参考デッキの互換性レポートです。今回はカード能力の完全実装ではなく、カード一覧、未対応能力、不明情報、4枚超過例外候補を可視化することを目的とします。

## Reference Deck 01

Source: `ViewDeckSheet(1).pdf`

Cards:

- 轟䡛合体 ゴルギーオージャー x4
- ～西方より来る激流の竜騎公～ x4
- ソウルサンライト コハク x4
- 一音の妖精 x4
- ジャスミンの地版 x4
- 観覧！ホールインランド・ヘラクレス x4
- 大集合！アカネ&アサギ&コハク x4
- 巨魔天 アオフェシー x3
- 華謡の精霊カンツォーネ x4
- ベイB セガーレ x2
- 水上第九院 シャコガイル x1
- 飛翔龍 5000VT x1
- 吟弾の妖精 x1

Total: 40

Current status:

- 公式データ未確認カード: 40/40
- unsupported / unknown: High
- reliability: Low

Major unsupported or unconfirmed tags:

- `ALTERNATE_WIN_CONDITION`
- `DRAW`
- `MANA_BOOST`
- `SEARCH`
- `META_EFFECT`
- `LOCK`
- `COST_REDUCTION`
- `BLOCKER` is partially represented, but official card data still needs confirmation.

## Reference Deck 02

Source: `ViewDeckSheet(2).pdf`

Cards:

- 特攻の忠剣ハチ公 x9
- 轟く革命 レッドギラゾーン x3
- 熱き侵略 レッドゾーンZ x1
- 配球の超人 / 記録的剛球 x4
- D2V3 終断のレッドトロン / フォビドゥン・ハンド x4
- Q.Q.QX. / 終葬 5.S.D. x4
- 綺羅王女プリン / ハンター☆エイリアン仲良しビーム x4
- フェアリー・ギフト x1
- 悪魔世界の閃光 x2
- 逆転の剣スカイソード x4
- 青銅のバンビシカット / 「我が力、しかと見よ！」 x4

Total: 40

Current status:

- ハチ公本体のruntime変換: 可能
- runtime_convertible_count: 9
- runtime_blocked_count: 31
- 4枚超過カード: 《特攻の忠剣ハチ公》 x9
- 《特攻の忠剣ハチ公》は4枚超過可能な確定仕様として扱う
- same-name exception: `DM_REF_014`
- 構築上は `reference_ruleset.json` の `same_name_exception_card_ids` により合法
- ハチ公の `SPEED_ATTACKER` と攻撃終了時の簡易ガチンコ・ジャッジ同名展開は実装済み
- Reference Deck 02全体はまだBlocked
- reliability: Low

Major unsupported or unconfirmed tags:

- `REVOLUTION_CHANGE`
- `INVASION`
- `TWINPACT`
- `G_STRIKE`
- `COST_REDUCTION`
- `DESTROY`
- `MANA_BOOST`
- `GAIN_SHIELD`
- `LOCK`
- `ALTERNATE_WIN_CONDITION`
- `SHIELD_TRIGGER`

## Priority Work Before Accurate Simulation

High:

- 公式カードデータの確認と入力
- `TWINPACT`
- `REVOLUTION_CHANGE`
- `INVASION`
- `SPEED_ATTACKER`
- `G_STRIKE`
- `ALTERNATE_WIN_CONDITION`
- `SAME_NAME_MORE_THAN_4_ALLOWED` ruleset handling
- `COST_REDUCTION`
- `META_EFFECT` / `LOCK`

Medium:

- `SEARCH`
- `DRAW`
- `MANA_BOOST`
- `GAIN_SHIELD`
- `DESTROY`
- `SHIELD_TRIGGER`

## Which Deck Is Easier First?

Reference Deck 01 is likely the more practical first target if the goal is incremental support, because it appears to have fewer structural mechanics like twinpact, invasion, and revolution change. However, it still depends on special win condition and meta effects.

Reference Deck 02 requires earlier support for deck construction exceptions, twinpact, revolution change, invasion, and G・ストライク. It is a better stress test for real-card infrastructure, but a harder first accurate simulator target.

## Reference Deck 02 Simulation Readiness

Current readiness: Blocked.

《特攻の忠剣ハチ公》9枚投入は4枚超過違反ではなく、カード能力による合法構築として扱います。ハチ公本体はruntime変換可能で、`SPEED_ATTACKER`、簡易 `GACHINKO_JUDGE`、`SEARCH_SAME_NAME`、`PUT_FROM_DECK_TO_BATTLE_ZONE` による同名展開が動きます。

Blocked reasons:

- Twinpact cards are 20 cards, and the runtime does not yet model upper/lower card faces.
- Revolution change, invasion, G・ストライク, cost reduction, lock/meta effects, and alternate win conditions are not implemented.
- Some cards still have unknown official data fields.
- Placeholder conversion is intentionally blocked by default, because silently guessing card type, cost, civilization, or power would produce misleading results.

Shortest route:

1. Complete official data for Reference Deck 02.
2. Implement or approximate twinpact structure.
3. Keep Hachiko's same-name exception as a ruleset feature.
4. Implement `TWINPACT` and `G_STRIKE`.
5. Implement Red Girazone / Red Zone Z movement mechanics: revolution change and invasion.
6. Add card-specific handlers for Q.Q.QX. and key meta/lock effects.
