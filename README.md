# dm_ai_sim

デュエル・マスターズ風の最小カードゲーム環境です。将来的に強化学習AIを接続するため、Gymnasium風の `reset()` / `step(action)` / `legal_actions()` / `get_observation()` API を持つ `Env` を中心にしています。

## インストール方法

```bash
pip install -e .
```

開発用にテストも入れる場合:

```bash
pip install -e ".[dev]"
```

## テスト実行方法

```bash
pytest
```

## サンプル対戦の実行方法

```bash
python -m dm_ai_sim.examples.play_random_vs_random
python -m dm_ai_sim.examples.play_heuristic_vs_random
```

## 大量対戦テストの実行方法

```bash
python -m dm_ai_sim.examples.run_many_random_games
python -m dm_ai_sim.examples.run_many_heuristic_vs_random
python -m dm_ai_sim.examples.play_with_action_id
```

`run_many_random_games` は RandomAgent 同士で1000試合を実行し、総試合数、各プレイヤー勝利数、平均ターン数、最大ターン数、エラー件数を表示します。

`run_many_heuristic_vs_random` は HeuristicAgent と RandomAgent で1000試合を実行し、勝率、平均ターン数、最大ターン数を表示します。

## 固定長 action space

人間向け・ルール実装向けの `Action` dataclass API は維持しつつ、強化学習ライブラリ向けに固定長の整数 `action_id` を追加しています。

```python
from dm_ai_sim import Env

env = Env()
obs = env.reset()
action_ids = env.legal_action_ids()
obs, reward, done, info = env.step_action_id(action_ids[0])
```

`action_id` の割り当ては以下です。現在の仕様では最大40枚手札、最大40体クリーチャーを上限として扱います。`ACTION_SPACE_SIZE` は通常呪文用の領域を含めて384です。

| action_id | 対応アクション |
| --- | --- |
| `0` - `39` | `CHARGE_MANA(card_index)` |
| `40` - `79` | `SUMMON(card_index)` |
| `80` - `119` | `ATTACK_SHIELD(attacker_index)` |
| `120` - `159` | `ATTACK_PLAYER(attacker_index)` |
| `160` | `END_MAIN` |
| `161` | `END_ATTACK` |
| `162` - `241` | `ATTACK_CREATURE(attacker_index, target_index)`。攻撃側0-9、対象0-7 |
| `242` - `249` | `BLOCK(blocker_index)`。防御側blocker 0-7 |
| `250` | `DECLINE_BLOCK` |
| `251` - `255` | 予約領域 |
| `256` - `295` | `CAST_SPELL(hand_index)`。対象不要呪文 |
| `296` - `375` | `CAST_SPELL(hand_index, target_index)`。手札0-9、対象0-7 |
| `376` - `383` | 将来拡張用の予約領域 |

`dm_ai_sim.action_encoder` には以下があります。

- `encode_action(action)` は `Action` または dict を `action_id` に変換します。
- `decode_action(action_id)` は `action_id` を `Action` に戻します。
- `legal_action_mask(env)` は現在選択可能な `action_id` を1、それ以外を0にした長さ384のリストを返します。

`EnvConfig(include_action_mask=True)` を使うと、観測に `action_mask` が追加されます。PPOなどへ接続する場合は、方策の出力次元を `ACTION_SPACE_SIZE` にし、`action_mask` で非合法手を選ばないようにします。通常呪文追加により `ACTION_SPACE_SIZE` は384へ拡張されています。256出力で学習した旧モデルは推論に失敗する場合があるため、評価スクリプト側で安全にスキップします。

## 実装済みルール

- 2人対戦
- 各プレイヤー40枚デッキ
- 初期手札5枚
- シールド5枚
- 先攻1ターン目ドローの設定切替
- 最大ターン数 `max_turns` による引き分け終了
- クリーチャーのみ
- 山札、手札、マナ、バトルゾーン、墓地、シールド管理
- 1ターン1回のマナチャージ
- 未タップマナによる召喚コスト支払い
- 召喚酔い
- シールド攻撃
- シールドブレイク時の手札追加
- S・トリガーの自動発動
- シールド0枚時のプレイヤー攻撃による勝利
- クリーチャー同士のバトル
- 任意選択式のブロック宣言

## 未実装ルール

- 呪文
- 呪文全般の手札からの使用
- 複雑な能力
- 文明支払い
- 本格的な不完全情報観測

## 今後の拡張方針

- アクションは `Action` と `ActionType` に集約し、合法手生成を `rules.py` に寄せています。DouZero などのカードゲーム強化学習研究で重要になる「状態ごとに大きく変わる合法手集合」を扱いやすくするためです。
- 観測は `get_observation(player_id=...)` に閉じ込めています。将来、相手手札を枚数だけにする、公開情報だけを返す、履歴や信念状態を追加する、といった不完全情報向けの変更をここで吸収できます。
- 報酬は終局報酬を基本にし、中間報酬は `intermediate_rewards` 設定から拡張できる形にしています。自己対戦やDeep Monte-Carlo系の学習にも接続しやすい構造です。
- ルール解決は `Env` から分離し、S・トリガー、文明支払い、追加バトル能力を段階的に追加できるようにします。

## 現在の安定性確認結果

- `pytest` で初期化、マナチャージ、召喚、攻撃、勝利条件、不正アクション、最大ターン終了、カード総数保存を確認しています。
- RandomAgent 同士の100試合テストでは、各ステップで `legal_actions()` が空でないことと `assert_invariants()` が通ることを確認しています。
- 1000試合スクリプトでは、長時間・大量対戦時の例外発生数、勝利数、平均ターン数、最大ターン数を確認できます。

## 強化学習接続前に確認すべき項目

- 観測を完全情報にするか、不完全情報にするか。
- 行動を `Action` オブジェクトのまま扱うか、整数IDへエンコードするか。
- `done=True` かつ `winner=None` の引き分けを学習側でどう扱うか。
- 中間報酬 `intermediate_rewards` を使う場合、報酬設計が方策を歪めていないか。
- 自己対戦時の先攻・後攻の偏り、seed管理、評価用固定デッキの扱い。

## PPO学習

Stable-Baselines3、sb3-contrib、Gymnasium に対応した `DuelMastersGymEnv` を追加しています。PPOはPlayer 0を操作し、Player 1はRandomAgentまたはHeuristicAgentが自動で操作します。

```bash
python -m dm_ai_sim.train_ppo
```

モデルは以下に保存されます。

```text
saved_models/ppo_basic.zip
```

評価は以下です。

```bash
python -m dm_ai_sim.evaluate_ppo
python -m dm_ai_sim.compare_agents
```

`train_ppo.py` は `sb3-contrib` の `MaskablePPO` を使います。通常PPOだけでも環境は動きますが、このゲームは合法手が状態ごとに大きく変わるため、初期学習からaction maskを使う方が安定します。

現在の `DuelMastersGymEnv` は固定長の `Box(shape=(24,))` 観測を返します。内容は手札枚数、山札枚数、シールド枚数、マナ枚数、バトルゾーン枚数、ターン数、合法手数などの簡易特徴量です。まずは「学習が成立する」ことを優先しており、強い特徴設計ではありません。

`info["action_mask"]` と `DuelMastersGymEnv.action_masks()` が利用できます。MaskablePPO以外の通常PPOで使う場合、不正actionには小さなペナルティを与える設計になっています。

推奨学習step数:

- 動作確認: `1,000` - `10,000`
- 簡易評価: `10,000` - `50,000`
- 改善確認: `100,000` 以上

今後の改善案:

- `MaskablePPO` の正式採用
- 自己対戦学習
- 相手をRandomAgentからHeuristicAgentへ段階的に強化
- カード単位の特徴量追加
- 先攻・後攻を入れ替えた評価

## Self-Play 学習

Self-Playでは `DuelMastersSelfPlayEnv` を使い、Player 0を学習対象、Player 1を固定opponentとして扱います。opponentはRandomAgent、HeuristicAgent、または `saved_models/opponents/` に保存された過去snapshotからランダムに選ばれます。

```bash
python -m dm_ai_sim.train_selfplay
```

デフォルトは動作確認しやすい `10,000` stepです。長めに学習する場合はPowerShellで環境変数を指定します。

```powershell
$env:DM_SELFPLAY_TIMESTEPS="100000"
$env:DM_SELFPLAY_SNAPSHOT_INTERVAL="10000"
python -m dm_ai_sim.train_selfplay
```

保存先:

```text
saved_models/selfplay_ppo.zip
saved_models/opponents/ppo_snapshot_*.zip
```

評価:

```bash
python -m dm_ai_sim.evaluate_selfplay
```

SelfPlayPPO vs RandomAgent、HeuristicAgent、通常PPOを100試合ずつ比較し、勝率、平均ターン数、簡易Eloを表示します。

Eloは相対的な強さの目安です。初期値1000から、勝てば上がり、負ければ下がります。試合数が少ない段階では揺れが大きいので、学習推移を見るための簡易指標として使ってください。

今後の研究拡張:

- opponent poolのサイズ制御と重み付きサンプリング
- 最新モデルとのミラー対戦
- 先攻・後攻を入れ替えたSelf-Play
- checkpointごとのElo推移グラフ化
- league trainingやpopulation based training

## Creature Battle

`ATTACK_CREATURE` を追加し、攻撃可能なクリーチャーは相手クリーチャーを攻撃できるようになりました。

基本ルール:

- 攻撃側クリーチャーをタップします。
- 攻撃側powerと防御側powerを比較します。
- `attacker.power >= defender.power` なら防御側を破壊します。
- `defender.power >= attacker.power` なら攻撃側を破壊します。
- 両方成立する同powerの場合は相打ちです。
- 破壊されたカードは `battle_zone` から `graveyard` へ移動します。

未実装:

- スレイヤー
- バトル時能力
- パワー低下
- タップキル特殊裁定

HeuristicAgentは、攻撃側が生き残り相手だけを破壊できる有利交換を最優先するようになりました。その後はシールド攻撃、最大コスト召喚、マナチャージの順で行動します。

PPO/SelfPlay用の観測には、盤面判断の最低限の材料として、自分・相手それぞれの最大powerと総powerを追加しています。既存モデル互換のため観測shapeは `(24,)` のまま維持しています。

## Blocker

`Card` に `blocker: bool = False` を追加しました。標準のサンプルデッキには約25%のブロッカーが混ざります。

現在は任意ブロックをActionとして扱います。シールド攻撃またはプレイヤー攻撃が宣言されたとき、防御側にアンタップ状態のblockerがいれば即時解決せず、`pending_attack` を作成して `current_player` を防御側へ切り替えます。

`pending_attack` 中の合法手は以下だけです。

- `BLOCK(blocker_index)`: 指定した自分のアンタップblockerでブロックします。
- `DECLINE_BLOCK`: ブロックせずに攻撃を通します。

`BLOCK` ではblockerをタップし、攻撃クリーチャーとblockerが通常のCreature Battleを行います。シールドブレイクやプレイヤー勝利は発生せず、解決後は `pending_attack` をクリアして攻撃側のAttack phaseへ戻ります。

`DECLINE_BLOCK` では `pending_attack.target_type` に従ってシールドブレイクまたはプレイヤー攻撃を解決します。`ATTACK_CREATURE` は初期実装ではブロック対象にせず、そのままクリーチャーバトルとして解決します。

`step()` の `info` には以下が入ります。

```python
{
    "blocked": True,
    "blocker_index": 0,
    "blocker_name": "Blocker Creature 1000",
    "blocker_power": 2000,
    "attacker_power": 3000,
}
```

ブロックしなかった場合は `info["declined_block"] == True` です。ブロック候補がない攻撃は従来どおり即時解決されます。

HeuristicAgentは、相手にアンタップblockerがいる場合に無駄なシールド/プレイヤー攻撃を減らし、先にblockerを処理できる `ATTACK_CREATURE` を選びやすくしています。防御側では、生存して攻撃クリーチャーを倒せる場合、相打ちで高価値攻撃を止められる場合、プレイヤー攻撃で負ける場合、シールドが少ない場合にブロック寄りになります。

PPO/SelfPlay用の観測には、既存モデル互換のためshape `(24,)` を維持しつつ、`pending_attack` の有無、自分が防御側か、攻撃側power、ブロック可能数、ブロック可能最大power、攻撃対象がPLAYERかを一部特徴量へ差し込んでいます。旧モデルは読み込める場合がありますが、任意ブロック判断を学習していないため性能低下することがあります。`evaluate_blocker.py` はモデル読み込みやshapeが合わない組み合わせを安全にスキップします。

Reward shapingでは「ブロックされたこと」自体を大きく罰しません。ブロック誘導、相打ち狙い、後続攻撃を通すための攻撃が正しい戦術になりうるためです。採用する報酬は、相手blocker破壊、有利交換、相打ち、不利交換、シールドブレイクなどの結果に基づきます。

ブロック判断のログ分析:

```powershell
python -m dm_ai_sim.analyze_blocking_logs
```

`SelfPlayBlockerFineTunedAgent` と `HeuristicAgent` を20試合対戦させ、`logs/blocking_analysis.jsonl` にturn、current_player、phase、action、pending_attack有無、blocked/declined、attacker/blocker power、shield counts、winner、敗戦タグを保存します。`logs/` は `.gitignore` 対象です。

## Blocker込み再学習

Blocker導入前の `ppo_basic.zip` や `selfplay_ppo.zip` は、ブロッカーを処理する判断を学習していません。そのため、Blocker導入後は無駄なシールド攻撃やリーサル失敗が増え、勝率が落ちることがあります。

Blocker込みモデルは旧モデルと分けて保存します。

```text
saved_models/ppo_blocker.zip
saved_models/selfplay_blocker.zip
saved_models/opponents_blocker/ppo_snapshot_*.zip
```

Blocker込みPPO再学習:

```powershell
python -m dm_ai_sim.train_ppo_blocker
```

学習step数を変える場合:

```powershell
$env:DM_PPO_BLOCKER_TIMESTEPS="100000"
python -m dm_ai_sim.train_ppo_blocker
```

Blocker込みSelf-Play再学習:

```powershell
python -m dm_ai_sim.train_selfplay_blocker
```

学習step数を変える場合:

```powershell
$env:DM_SELFPLAY_BLOCKER_TIMESTEPS="100000"
python -m dm_ai_sim.train_selfplay_blocker
```

`train_selfplay_blocker.py` は `ppo_blocker.zip` が存在する場合、初期opponent poolへ `ppo_snapshot_0.zip` として追加します。RandomAgent、HeuristicAgent、過去snapshotも相手候補になります。

Blocker込み評価:

```powershell
python -m dm_ai_sim.evaluate_blocker
```

`evaluate_blocker.py` は以下を比較します。存在しないモデルは自動でスキップします。

- RandomAgent
- HeuristicAgent
- PPOAgent
- SelfPlayPPOAgent
- PPOBlockerAgent
- SelfPlayBlockerAgent
- SelfPlayBlockerFineTunedAgent

## Heuristic対策 Fine-tune

Blocker込みSelfPlayモデルがHeuristicAgentに直接勝ち越せない場合、HeuristicAgentの出現比率を高めた追加学習を行います。これはSelfPlay全体のEloを上げるというより、「特定の強いルールベース相手に勝つ」ためのfine-tuneです。

実行:

```powershell
python -m dm_ai_sim.train_selfplay_blocker_finetune
```

学習step数を変える場合:

```powershell
$env:DM_SELFPLAY_BLOCKER_FINETUNE_TIMESTEPS="100000"
python -m dm_ai_sim.train_selfplay_blocker_finetune
```

保存先:

```text
saved_models/selfplay_blocker_finetuned.zip
saved_models/opponents_blocker_finetuned/ppo_snapshot_*.zip
```

Fine-tune時のopponent比率:

- HeuristicAgent: 60%
- PPOBlockerAgent: 20%
- RandomAgent: 10%
- 過去snapshot: 10%

Fine-tune時のみreward shapingをONにしています。通常ルールそのものは変えません。

- 相手blockerを破壊: `+0.05`
- 自分の攻撃がblockerに止められた: `0.00`
- ブロックされずにシールドを割った: `+0.03`
- 有利交換で相手クリーチャーを破壊: `+0.04`
- ブロック戦闘で相打ち: `+0.01`
- 不利交換で自分だけ破壊: `-0.04`

reward shapingは過学習の原因にもなるため、`train(..., reward_shaping=False)` で無効化できます。

直接勝率とEloは見ているものが違います。直接勝率は特定相手との相性を示します。Eloは総当たり結果をもとにした相対評価なので、ある相手に負け越していても、他の相手に強ければ高く出ることがあります。

## OptionalBlock 再学習

任意ブロック導入後は、防御側が `BLOCK` / `DECLINE_BLOCK` を選ぶ局面が学習対象になります。旧モデルは攻撃判断だけでなく防御判断も未学習なので、合法手maskで実行自体はできても、リーサル逃し、自軍ブロッカー未活用、攻撃順ミスが出やすくなります。

旧モデルを上書きしないよう、OptionalBlock用モデルは別名で保存します。

```text
saved_models/ppo_optional_block.zip
saved_models/selfplay_optional_block.zip
saved_models/selfplay_optional_block_finetuned.zip
saved_models/opponents_optional_block/ppo_snapshot_*.zip
saved_models/opponents_optional_block_finetuned/ppo_snapshot_*.zip
```

PPO再学習:

```powershell
python -m dm_ai_sim.train_ppo_optional_block
```

学習step数を変える場合:

```powershell
$env:DM_PPO_OPTIONAL_BLOCK_TIMESTEPS="100000"
python -m dm_ai_sim.train_ppo_optional_block
```

SelfPlay再学習:

```powershell
python -m dm_ai_sim.train_selfplay_optional_block
```

```powershell
$env:DM_SELFPLAY_OPTIONAL_BLOCK_TIMESTEPS="100000"
python -m dm_ai_sim.train_selfplay_optional_block
```

Fine-tune:

```powershell
python -m dm_ai_sim.train_selfplay_optional_block_finetune
```

```powershell
$env:DM_SELFPLAY_OPTIONAL_BLOCK_FINETUNE_TIMESTEPS="100000"
python -m dm_ai_sim.train_selfplay_optional_block_finetune
```

Fine-tuneでは、HeuristicAgent、PPOOptionalBlockAgent、SelfPlayOptionalBlockAgent、RandomAgentを重み付きで相手にします。reward shapingはON/OFF可能で、通常評価ではOFF、fine-tuneではONを基本にします。`blocked=True` 自体を罰する報酬は入れていません。リーサル成功、リーサル逃し、自軍ブロッカーでの敗北回避、有利交換、攻撃順により後続攻撃が通ったか、など結果ベースで加点/減点します。

OptionalBlock評価:

```powershell
python -m dm_ai_sim.evaluate_optional_block
```

存在するモデルだけを比較し、勝率表、平均ターン数、Elo、OptionalBlock系 vs Heuristic、OptionalBlock系 vs 旧FineTunedモデルの直接勝率を出します。モデルファイルが存在しないAgentはスキップします。

blocking logは以下で更新できます。

```powershell
python -m dm_ai_sim.analyze_blocking_logs
```

`logs/blocking_analysis.jsonl` には、従来のターン・action・blocked/declined・power・shield countsに加えて、リーサル可能だったか、BLOCKすれば敗北を防げたか、DECLINE_BLOCKが敗因か、BLOCK過剰か、相手ブロッカーを先に処理すべきだったか、攻撃順で後続攻撃が通ったか/通らなかったか、などの敗戦タグを出します。タグは原因候補なので、最終判断には個別event列も確認してください。

## S・トリガー

シールドブレイク時の処理を、実ルール寄りに更新しました。通常のシールドカードは墓地ではなく手札へ加わります。`shield_trigger=True` のカードは初期版では自動発動し、使用判断をActionにはしていません。

`Card` には以下の属性があります。

- `shield_trigger: bool = False`
- `card_type: "CREATURE" | "SPELL" = "CREATURE"`
- `trigger_effect: str | None = None`

現在の自動発動効果:

- `DRAW_1`: 防御側が1枚ドローし、トリガーカードは墓地へ行きます。
- `DESTROY_ATTACKER`: 攻撃クリーチャーを破壊し、トリガーカードは墓地へ行きます。シールドブレイク自体は成立済みです。
- `SUMMON_SELF`: トリガーカードがクリーチャーなら防御側のバトルゾーンへ出ます。タップせず、召喚ターンは現在ターンです。
- `GAIN_SHIELD`: 防御側の山札上から1枚をシールドへ追加し、トリガーカードは墓地へ行きます。

`BLOCK` した場合はシールドブレイクが発生しないため、S・トリガーも発生しません。`DECLINE_BLOCK` で攻撃を通した場合は、通常のシールドブレイクとしてS・トリガー判定を行います。

`step()` の `info` には以下が入ります。

```python
{
    "shield_broken": True,
    "broken_shield_card": "Shield Trigger Spell 33",
    "trigger_activated": True,
    "trigger_effect": "DESTROY_ATTACKER",
    "attacker_destroyed_by_trigger": True,
}
```

S・トリガーがない場合は `trigger_activated == False` です。

PPO/SelfPlay観測は既存モデル互換のためshape `(24,)` を維持しています。相手シールドの中身は観測に入れず、場/墓地に見えているS・トリガー数、直前のS・トリガー発動有無、直前の `trigger_effect` を簡易特徴量として使います。これは将来の不完全情報化に備え、非公開領域を直接見せない方針です。

将来的には、S・トリガーを「使う/使わない」選択や、複数トリガーの順序選択をAction化できます。その場合は `ACTION_SPACE_SIZE` の予約領域、またはpending trigger用の別action設計を追加します。現段階では自動発動なのでaction_id割り当ては変更していません。

S・トリガーログ分析:

```powershell
python -m dm_ai_sim.analyze_trigger_logs
```

`logs/trigger_analysis.jsonl` に20試合分のturn、attacker/defender、action、shield_broken、trigger_activated、trigger_effect、attacker_destroyed_by_trigger、shield_count_before/after、winnerを保存します。

## Trigger 再学習

S・トリガー導入後は、シールド攻撃のリスクとリーサル計算が変わります。OptionalBlock系モデルはS・トリガー導入前の環境で学習しているため、`DESTROY_ATTACKER` で攻撃クリーチャーを失う、`GAIN_SHIELD` でリーサルがずれる、`SUMMON_SELF` で盤面が増える、`DRAW_1` で相手リソースが増える、といった結果に適応していません。

Trigger用モデルは旧モデルを上書きせず、以下に分離します。

```text
saved_models/ppo_trigger.zip
saved_models/selfplay_trigger.zip
saved_models/selfplay_trigger_finetuned.zip
saved_models/opponents_trigger/ppo_snapshot_*.zip
saved_models/opponents_trigger_finetuned/ppo_snapshot_*.zip
```

PPO再学習:

```powershell
python -m dm_ai_sim.train_ppo_trigger
```

```powershell
$env:DM_PPO_TRIGGER_TIMESTEPS="100000"
python -m dm_ai_sim.train_ppo_trigger
```

SelfPlay再学習:

```powershell
python -m dm_ai_sim.train_selfplay_trigger
```

```powershell
$env:DM_SELFPLAY_TRIGGER_TIMESTEPS="100000"
python -m dm_ai_sim.train_selfplay_trigger
```

Fine-tune:

```powershell
python -m dm_ai_sim.train_selfplay_trigger_finetune
```

```powershell
$env:DM_SELFPLAY_TRIGGER_FINETUNE_TIMESTEPS="100000"
python -m dm_ai_sim.train_selfplay_trigger_finetune
```

Fine-tuneでは、HeuristicAgent、PPOTriggerAgent、SelfPlayTriggerAgent、OptionalBlock系の最良モデル、RandomAgentを重み付きで相手にします。reward shapingはON/OFF可能で、通常評価ではOFF、fine-tuneではONを基本にします。

S・トリガー報酬設計では、`trigger_activated=True` だけを強く罰しません。シールド攻撃は勝利に必要であり、トリガーを踏むこと自体は不確定要素だからです。報酬は、リーサル成功、リーサル逃し、S・トリガー後の勝利、重要アタッカー喪失、`GAIN_SHIELD` 後の再リーサル、`SUMMON_SELF` で出たクリーチャーへの対応、シールドブレイク成功など、結果ベースで扱います。

Trigger評価:

```powershell
python -m dm_ai_sim.evaluate_trigger
```

存在するモデルだけを比較し、勝率表、平均ターン数、Elo、Trigger系 vs Heuristic、Trigger系 vs OptionalBlock系最良モデルの直接勝率を出します。あわせて、`DRAW_1`、`DESTROY_ATTACKER`、`SUMMON_SELF`、`GAIN_SHIELD` の発動回数も集計します。

`analyze_trigger_logs.py` は、発動ログに加えて以下のようなタグを出します。

- リーサル可能だったか
- リーサルを逃したか
- trigger_activated後に勝敗が変わった可能性があるか
- DESTROY_ATTACKERで主要アタッカーを失ったか
- GAIN_SHIELDでリーサルがずれたか
- SUMMON_SELFで盤面が逆転したか
- DRAW_1で防御側の手札差が広がったか
- S・トリガーを恐れて攻撃しなかった可能性があるか
- S・トリガーを無視して無理攻めした可能性があるか

## 通常呪文

`card_type="SPELL"` のカードを、メインフェーズ中に手札から唱えられるようにしました。新しいActionは `CAST_SPELL` です。

```python
Action(ActionType.CAST_SPELL, hand_index=0)
Action(ActionType.CAST_SPELL, hand_index=0, target_index=1)
```

`trigger_effect` はS・トリガー時の効果、`spell_effect` は手札から通常詠唱した時の効果です。初期版では `spell_effect` が `None` の場合に `trigger_effect` を流用できますが、標準デッキでは通常呪文用に `spell_effect` を明示しています。

実装済みの通常呪文効果:

- `DRAW_1`: 使用者が1枚ドローし、呪文は墓地へ行きます。
- `DESTROY_TARGET`: 相手クリーチャー1体を破壊し、呪文は墓地へ行きます。`target_index` が必要です。
- `GAIN_SHIELD`: 山札上から1枚をシールドへ追加し、呪文は墓地へ行きます。
- `MANA_BOOST`: 山札上から1枚をアンタップ状態でマナゾーンへ置き、呪文は墓地へ行きます。

`DESTROY_ATTACKER` はS・トリガー専用効果です。手札から使う除去呪文は `spell_effect="DESTROY_TARGET"` として扱います。

標準デッキは、クリーチャー約30枚、呪文約10枚です。S・トリガー呪文も一部含みます。

通常呪文ログ分析:

```powershell
python -m dm_ai_sim.analyze_spell_logs
```

`logs/spell_analysis.jsonl` に20試合分のturn、player、spell_cast、spell_name、spell_effect、target_index、hand/mana/shield/battle zoneの前後、winnerを保存します。分類タグとして、除去呪文でblockerを処理した、DRAW_1で手札切れを回避した、MANA_BOOSTで高コスト召喚に繋がった、GAIN_SHIELDで延命した、呪文を使わずに負けた可能性、などを出します。

通常呪文評価:

```powershell
python -m dm_ai_sim.evaluate_spell
```

RandomAgent、HeuristicAgent、存在するTrigger系最良モデル、Spell系モデルを比較します。モデルが存在しない場合、または旧action spaceと合わない場合はスキップまたは合法手へフォールバックします。

## 通常呪文込み再学習

通常呪文導入後は `CAST_SPELL` が追加され、`ACTION_SPACE_SIZE` が256から384へ広がります。旧モデルは256 action前提の方策ヘッドを持つため、新しい合法手マスクや呪文判断に最適化されていません。そのため、旧モデルとSpell対応モデルは保存先を分けます。

```text
saved_models/ppo_spell.zip
saved_models/selfplay_spell.zip
saved_models/selfplay_spell_finetuned.zip
saved_models/opponents_spell/
saved_models/opponents_spell_finetuned/
```

PPOで通常呪文込み環境を学習します。

```powershell
$env:DM_PPO_SPELL_TIMESTEPS="100000"
python -m dm_ai_sim.train_ppo_spell
```

SelfPlayで通常呪文込み環境を学習します。相手プールにはRandom、Heuristic、存在するPPOSpell、Trigger系最良モデル、過去snapshotを使います。

```powershell
$env:DM_SELFPLAY_SPELL_TIMESTEPS="100000"
python -m dm_ai_sim.train_selfplay_spell
```

Fine-tuneでは呪文の使いどころを改善するreward shapingをONにできます。通常評価ではOFF、fine-tuneではONが基本です。

```powershell
$env:DM_SELFPLAY_SPELL_FINETUNE_TIMESTEPS="100000"
python -m dm_ai_sim.train_selfplay_spell_finetune
```

報酬は `spell_cast=True` 自体を強く評価しません。唱えただけに報酬を与えすぎると、不要なドロー、盾追加、低価値除去などを空打ちする方策になりやすいためです。Fine-tune報酬は、除去後に攻撃が通る、高powerを処理する、マナ加速後に高コスト召喚へつながる、少ない手札を回復する、盾追加で敗北を回避する、といった結果に寄せています。

`evaluate_spell.py` は勝率表、平均ターン数、Elo、Spell系 vs Heuristic、Spell系 vs Trigger系、`spell_cast`回数、`spell_effect`別回数、CAST_SPELLが勝敗に絡んだ可能性のある試合数を出力します。

`analyze_spell_logs.py` は `logs/spell_analysis.jsonl` に20試合以上のイベントを書き出し、`DESTROY_TARGET`でblockerを処理したか、リーサルにつながったか、低価値対象を取った可能性、`MANA_BOOST`後の高コスト召喚、`DRAW_1`での手札切れ回避、`GAIN_SHIELD`での敗北回避、呪文過多や召喚・攻撃優先の疑いをタグで確認できます。

## 文明支払いと多色マナ

`Card` は既存互換の `civilization` に加えて、複数文明の `civilizations` を持ちます。扱う文明は `LIGHT`、`WATER`、`DARKNESS`、`FIRE`、`NATURE`、`COLORLESS` です。単色カードは `("FIRE",)` のように、多色カードは `("FIRE", "NATURE")` のように表します。

マナチャージ時の挙動:

- 単色カードはアンタップでマナゾーンへ置かれます。
- `COLORLESS` はアンタップでマナゾーンへ置かれます。
- 多色カードはタップ状態でマナゾーンへ置かれます。

`SUMMON` と `CAST_SPELL` は、コスト分のアンタップマナに加えて、カードが要求する各文明を1枚ずつ支払える必要があります。`COLORLESS` カードはコスト分のアンタップマナだけで使用できます。多色マナ1枚は複数文明を持ちますが、支払い時に同時に2文明分を満たすことはできません。

マナ支払いはAction化していません。合法手判定と実際の支払いは同じ自動支払いロジックを使い、必要文明を満たすマナを優先し、単色を先に使い、多色をなるべく温存します。残りコストは任意のアンタップマナから支払い、使用したマナは `tapped=True` になります。

S・トリガーは初期版では文明・コストを無視して自動発動します。`SUMMON_SELF` も支払い不要です。これは実ルールの完全再現ではなく、まず通常使用の文明事故とマナ基盤を見るための簡易仕様です。

HeuristicAgentのマナチャージは文明を見ます。手札に多い文明、まだマナにない文明、低コスト初動に必要な文明、多色カードの序盤価値を考慮し、現在使えるカードをむやみにマナへ置きにくくしています。

マナ分析:

```powershell
python -m dm_ai_sim.analyze_mana_logs
```

`logs/mana_analysis.jsonl` に20試合以上を書き出し、色事故、コスト不足、多色タップインで動けなかった、2/3ターン目初動失敗、必要文明不足で `SUMMON` / `CAST_SPELL` 不可、などをタグ化します。

マナ評価:

```powershell
python -m dm_ai_sim.evaluate_mana
```

RandomAgent、HeuristicAgent、存在するSpell系モデルを比較し、勝率表、平均ターン数、Elo、平均色事故率、2/3ターン目使用可能カード率、多色タップインによる行動不能回数、平均使用可能手札枚数を出力します。

未対応の差分として、マナの手動タップ選択、実カードデータ、厳密な裁定、複雑な文明追加・軽減能力、不完全情報化はまだ扱っていません。

## GitHub移行

このリポジトリはPythonパッケージとして再現できるよう、`pyproject.toml` に依存関係をまとめています。学習済みモデルzip、pytest cache、egg-info、仮想環境、`.env` は `.gitignore` で除外します。モデル保存用ディレクトリだけは `.gitkeep` で保持します。

新規GitHubリポジトリへpushするPowerShell手順:

```powershell
git init
git add .
git commit -m "Initial dm_ai_sim project"
git branch -M main
git remote add origin https://github.com/<YOUR_USER>/<YOUR_REPO>.git
git push -u origin main
```

別PCでcloneして動かす手順:

```powershell
git clone https://github.com/<YOUR_USER>/<YOUR_REPO>.git
cd <YOUR_REPO>
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
pytest
python -m dm_ai_sim.examples.play_random_vs_random
```

環境変数は必須ではありません。Self-Playの学習step数などを変えたい場合は `.env.example` のコメントを参考にPowerShellで設定してください。

## ルール監査と実カード対応

現在の環境は、実カード大会評価用としてはまだ未完成です。実装済みルール、簡略化、未実装要素、大会評価上のリスクは [RULE_COMPATIBILITY.md](RULE_COMPATIBILITY.md) に整理しています。

標準デッキは学習・テスト用の合成デッキであり、大会用評価デッキではありません。文明配分、コスト分布、多色枚数、3-Fのマナ事故結果は [STANDARD_DECK_DIAGNOSTICS.md](STANDARD_DECK_DIAGNOSTICS.md) にまとめています。

現在のテスト範囲と不足している実ルール観点は [TEST_COVERAGE.md](TEST_COVERAGE.md) を参照してください。実カードデータ導入の方針、未対応能力タグ、デッキ互換性レポートの考え方は [REAL_CARD_DATA_PLAN.md](REAL_CARD_DATA_PLAN.md) に記載しています。

今後は全カード能力の完全再現から始めず、実カードデータを読み込み、未対応能力を警告し、対象デッキ・対象メタに含まれるカードから優先して実装する方針です。

実カードデータの入口として、`data/cards/sample_cards.json`、`data/decks/sample_deck.json`、`data/rulesets/sample_ruleset.json` を追加しています。カード能力は `ability_tags` で管理し、実装済みは `implemented_tags`、未対応は `unsupported_tags` に分けます。未対応タグがあるカードは `strict=False` では警告付きで読み込めますが、デッキ互換性レポートの信頼度が下がります。`strict=True` では例外になります。

サンプルDBの確認:

```powershell
python -m dm_ai_sim.inspect_card_database
```

出力されるデッキ互換性は、`fully_supported_count`、`partially_supported_count`、`unsupported_count`、`unknown_data_count`、`unsupported_tags_summary`、`reliability` を見ます。Rulesetは現段階では `banned_card_ids`、`restricted_card_ids`、`max_copies_per_card`、`same_name_exception_card_ids` の簡易チェックに対応しています。

提出された参考デッキ2件も取り込み済みです。

- `data/cards/reference_cards.json`
- `data/decks/reference_deck_01.json`
- `data/decks/reference_deck_02.json`
- `data/rulesets/reference_ruleset.json`
- [REFERENCE_DECK_COMPATIBILITY.md](REFERENCE_DECK_COMPATIBILITY.md)

確認CLI:

```powershell
python -m dm_ai_sim.inspect_reference_decks
```

参考デッキは未対応能力と未確認公式データが多いため、この段階の大会用評価結果は信頼できません。まず互換性レポートで `unsupported_tags_summary`、`unknown_data_count`、4枚超過カード、`SAME_NAME_MORE_THAN_4_ALLOWED` 例外候補を確認してください。

## 参考にした研究・設計観点

- [Zha et al., "DouZero: Mastering DouDizhu with Self-Play Deep Reinforcement Learning", ICML 2021](https://arxiv.org/abs/2106.06135)。可変合法手、自己対戦、Deep Monte-Carloの考え方を参照。
- [Zha et al., "RLCard: A Toolkit for Reinforcement Learning in Card Games"](https://arxiv.org/abs/1910.04376) と [RLCard documentation](https://rlcard.org/index.html)。カードゲーム環境を研究用APIとして切り出し、観測・合法手・エージェントを分ける設計方針を参照。
- [Dockhorn and Mostaghim, "Introducing the Hearthstone-AI Competition"](https://arxiv.org/abs/1906.04238)。CCGにおけるデッキ多様性、ランダム性、制限情報の課題を参照。
- [Hoover et al., "The Many AI Challenges of Hearthstone"](https://arxiv.org/abs/1907.06562)。複雑なカードゲームでは完全再現より、まず安定した簡略シミュレーターとベースラインエージェントを用意する方針を参照。
