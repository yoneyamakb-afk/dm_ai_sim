# Reference Deck 02 Data Audit

This audit records the phase 4-D official data pass for Reference Deck 02. Unconfirmed fields are intentionally left as `UNKNOWN`, `null`, or empty text, with `needs_official_data` retained in notes.

## Completed Fields

- 《特攻の忠剣ハチ公》: cost, civilization, card type, power, races, short text summary, and additional ability tags were recorded.
- 《轟く革命 レッドギラゾーン》: cost, civilizations, card type, power, races, short text summary, and combat/revolution tags were recorded.
- 《熱き侵略 レッドゾーンZ》: cost, civilization, card type, power, races, short text summary, and evolution/invasion tags were recorded.
- 《Q.Q.QX. / 終葬 5.S.D.》: twinpact side structure was populated with side names, costs, civilizations, side types, power where applicable, races, and short text summaries.
- 《フェアリー・ギフト》: cost, civilization, card type, and short cost-reduction summary were recorded.
- 《逆転の剣スカイソード》: civilization, card type, and short ability summary were recorded. Cost, power, and races remain pending.

## Still Unknown

- 《配球の超人 / 記録的剛球》: twinpact side names and side types are structured, but cost, civilizations, power, races, and text remain unconfirmed.
- 《D2V3 終断のレッドトロン / フォビドゥン・ハンド》: twinpact side names and side types are structured, but most static fields remain unconfirmed.
- 《綺羅王女プリン / ハンター☆エイリアン仲良しビーム》: twinpact side names and side types are structured, but most static fields remain unconfirmed.
- 《悪魔世界の閃光》: all official static fields remain unconfirmed.
- 《青銅のバンビシカット / 「我が力、しかと見よ！」》: twinpact side names and side types are structured, but most static fields remain unconfirmed.

## Unknowns Left on Purpose

- Exact official rules text is not copied verbatim into the data file. The `text` field currently holds a short implementation-facing summary where official data was confirmed.
- Any field not confirmed from official card data remains `UNKNOWN`, `null`, or empty.
- Twinpact cards are not approximated as a single `CREATURE` or `SPELL`.

## Twinpact Cards Organized

ツインパクトとして整理したカード:

- `DM_REF_017` 配球の超人 / 記録的剛球
- `DM_REF_018` D2V3 終断のレッドトロン / フォビドゥン・ハンド
- `DM_REF_019` Q.Q.QX. / 終葬 5.S.D.
- `DM_REF_020` 綺羅王女プリン / ハンター☆エイリアン仲良しビーム
- `DM_REF_024` 青銅のバンビシカット / 「我が力、しかと見よ！」

## Next Human Confirmation Needed

- Confirm exact static fields for the four twinpact cards that still carry `needs_official_data`.
- Confirm 《悪魔世界の閃光》 cost, civilization, card type, and exact destroy behavior.
- Confirm whether any future cards need non-integer printed power notation before extending the runtime schema.
- Decide whether `text` should remain an implementation summary or whether a separate official text storage policy is needed.
