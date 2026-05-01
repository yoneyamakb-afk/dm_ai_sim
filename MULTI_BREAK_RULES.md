# Multi-Break Rules Plan

フェーズ4-K時点の複数ブレイク方針です。`DOUBLE_BREAKER` は `Card.breaker_count=2` として通常のシールド攻撃解決へ接続済みです。

## Single Break

単一ブレイクでは、攻撃側クリーチャーがシールドを1枚ブレイクします。

現在の実装では、`env.py` の攻撃解決から `shield_breaks.break_shields(..., count=attacker.card.breaker_count)` を呼びます。内部では対象シールドをシールドゾーンから取り除き、通常カード、S・トリガー、G・ストライク、ツインパクト下側S・トリガーを同じ経路で処理します。

## Multi Break

W・ブレイカー等で複数のシールドをブレイクする場合、公式ルールに近づけるため、以下を基本方針にします。

1. 複数枚のシールドを選ぶ。
2. 選ばれたシールドを同時にシールドゾーンから取り除く。
3. 取り除いたカード群をbreak contextとして保持する。
4. S・トリガー / G・ストライク / 通常手札移動を処理する。
5. S・トリガーの使用順は将来的には防御側が選ぶ。
6. 初期版では自動順で処理する。

フェーズ4-J4では `collect_shields_to_break` と `resolve_broken_shields` を追加し、`break_shields(count=2)` を直接呼んだ場合に、対象2枚を先にシールドゾーンから取り除いてから順番に解決する形へ調整しました。フェーズ4-Kでは通常攻撃の `ATTACK_SHIELD` からもこの経路を使います。

## Trigger Order

複数枚が同時に手札へ加わった場合、その中のS・トリガーは使う順番を選べる扱いです。現時点では選択Actionを追加しません。

初期版の自動順:

- シールドゾーンの上側から選ばれた順に `break_index` を振る。
- `trigger_resolution_order` も同じ順番で振る。
- ログには `batch_id`、`break_index`、`simultaneous_count`、`trigger_resolution_order` を残す。

## G-Strike

G・ストライクも、同時にブレイクされたカード群の中から処理されるものとして扱います。

現時点では、カードがG・ストライクを持ち、S・トリガーとして処理されない場合、自動でG・ストライクを使用します。その後、そのカードは手札へ加わります。対象選択は `GStrikeHandler` と `attack_permissions.get_gstrike_targets` に従います。

## Destroy Attacker

複数ブレイク中に `DESTROY_ATTACKER` が出て攻撃クリーチャーが破壊されても、すでに同時に選ばれたシールドはブレイク済みとして扱います。

フェーズ4-J3の暫定helperでは後続ブレイクを止めていましたが、4-J4で方針を変更しました。`break_shields(count=2)` で先に選ばれた2枚は、1枚目が攻撃クリーチャーを破壊しても2枚目まで解決します。

## Current Limits

- 通常攻撃の本番経路は `breaker_count` を使用します。
- `DOUBLE_BREAKER` は `breaker_count=2` として実処理済みです。
- 複数S・トリガーの使用順は防御側が選べず、自動順です。
- 複数ブレイク時に「一度まとめて手札へ加える」完全表現ではなく、break contextに置いてから順番にゾーン移動しています。
- `TRIPLE_BREAKER` はデータ推論として `breaker_count=3` になりますが、Reference Deck 02の実証対象ではありません。
