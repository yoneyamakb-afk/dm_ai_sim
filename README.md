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

`action_id` の割り当ては以下です。現在の仕様では最大40枚手札、最大40体クリーチャーを上限として扱います。`ACTION_SPACE_SIZE` は将来拡張用の余裕を含めて256です。

| action_id | 対応アクション |
| --- | --- |
| `0` - `39` | `CHARGE_MANA(card_index)` |
| `40` - `79` | `SUMMON(card_index)` |
| `80` - `119` | `ATTACK_SHIELD(attacker_index)` |
| `120` - `159` | `ATTACK_PLAYER(attacker_index)` |
| `160` | `END_MAIN` |
| `161` | `END_ATTACK` |
| `162` - `255` | 将来拡張用の予約領域 |

`dm_ai_sim.action_encoder` には以下があります。

- `encode_action(action)` は `Action` または dict を `action_id` に変換します。
- `decode_action(action_id)` は `action_id` を `Action` に戻します。
- `legal_action_mask(env)` は現在選択可能な `action_id` を1、それ以外を0にした長さ256のリストを返します。

`EnvConfig(include_action_mask=True)` を使うと、観測に `action_mask` が追加されます。PPOなどへ接続する場合は、方策の出力次元を `ACTION_SPACE_SIZE` にし、`action_mask` で非合法手を選ばないようにします。

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
- シールド0枚時のプレイヤー攻撃による勝利

## 未実装ルール

- 呪文
- S・トリガー
- ブロッカー
- 複雑な能力
- クリーチャー同士のバトル
- 文明支払い
- 本格的な不完全情報観測

## 今後の拡張方針

- アクションは `Action` と `ActionType` に集約し、合法手生成を `rules.py` に寄せています。DouZero などのカードゲーム強化学習研究で重要になる「状態ごとに大きく変わる合法手集合」を扱いやすくするためです。
- 観測は `get_observation(player_id=...)` に閉じ込めています。将来、相手手札を枚数だけにする、公開情報だけを返す、履歴や信念状態を追加する、といった不完全情報向けの変更をここで吸収できます。
- 報酬は終局報酬を基本にし、中間報酬は `intermediate_rewards` 設定から拡張できる形にしています。自己対戦やDeep Monte-Carlo系の学習にも接続しやすい構造です。
- ルール解決は `Env` から分離し、ブロッカー、S・トリガー、文明支払い、クリーチャーバトルを段階的に追加できるようにします。

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

## 参考にした研究・設計観点

- [Zha et al., "DouZero: Mastering DouDizhu with Self-Play Deep Reinforcement Learning", ICML 2021](https://arxiv.org/abs/2106.06135)。可変合法手、自己対戦、Deep Monte-Carloの考え方を参照。
- [Zha et al., "RLCard: A Toolkit for Reinforcement Learning in Card Games"](https://arxiv.org/abs/1910.04376) と [RLCard documentation](https://rlcard.org/index.html)。カードゲーム環境を研究用APIとして切り出し、観測・合法手・エージェントを分ける設計方針を参照。
- [Dockhorn and Mostaghim, "Introducing the Hearthstone-AI Competition"](https://arxiv.org/abs/1906.04238)。CCGにおけるデッキ多様性、ランダム性、制限情報の課題を参照。
- [Hoover et al., "The Many AI Challenges of Hearthstone"](https://arxiv.org/abs/1907.06562)。複雑なカードゲームでは完全再現より、まず安定した簡略シミュレーターとベースラインエージェントを用意する方針を参照。
