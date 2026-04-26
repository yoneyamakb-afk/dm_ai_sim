from __future__ import annotations

from pathlib import Path

from dm_ai_sim.agents import HeuristicAgent, PPOAgent, RandomAgent, SelfPlayPPOAgent
from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.gym_env import DuelMastersGymConfig, DuelMastersGymEnv
from dm_ai_sim.selfplay_env import DuelMastersSelfPlayEnv, SelfPlayConfig


def main() -> None:
    games = 50
    agents = ["RandomAgent", "HeuristicAgent", "PPOAgent", "SelfPlayPPOAgent"]
    results: dict[tuple[str, str], float] = {}

    for left in agents:
        for right in agents:
            if left == right:
                results[(left, right)] = 0.5
            else:
                results[(left, right)] = _win_rate(left, right, games)

    print("Win rate table for row agent as Player 0")
    print("," + ",".join(agents))
    for left in agents:
        cells = [f"{results[(left, right)]:.3f}" for right in agents]
        print(left + "," + ",".join(cells))


def _win_rate(left: str, right: str, games: int) -> float:
    if left == "PPOAgent":
        return _ppo_vs(right, games)
    if left == "SelfPlayPPOAgent":
        return _selfplay_vs(right, games)
    if right in {"PPOAgent", "SelfPlayPPOAgent"}:
        return 1.0 - _win_rate(right, left, games)
    wins = 0
    for seed in range(games):
        env = Env(config=EnvConfig(seed=seed))
        observation = env.reset()
        done = False
        agents = [_make_basic_agent(left, seed), _make_basic_agent(right, seed + 1000)]
        while not done:
            player_id = observation["current_player"]
            action = agents[player_id].act(env.legal_actions(), observation)
            observation, _reward, done, _info = env.step(action)
        if env.state is not None and env.state.winner == 0:
            wins += 1
    return wins / games


def _ppo_vs(right: str, games: int) -> float:
    model_path = Path("saved_models") / "ppo_basic.zip"
    agent = PPOAgent(model_path)
    wins = 0
    for seed in range(games):
        if right == "SelfPlayPPOAgent":
            env = DuelMastersSelfPlayEnv(
                SelfPlayConfig(
                    fixed_opponent=Path("saved_models") / "selfplay_ppo.zip",
                    include_heuristic_opponent=False,
                    include_random_opponent=False,
                    seed=seed,
                )
            )
        else:
            opponent = "heuristic" if right == "HeuristicAgent" else "random"
            env = DuelMastersGymEnv(DuelMastersGymConfig(opponent=opponent, seed=seed))
        env.reset()
        terminated = False
        truncated = False
        while not (terminated or truncated):
            action_id = agent.act(env)
            _observation, _reward, terminated, truncated, _info = env.step(action_id)
        if env.base_env.state is not None and env.base_env.state.winner == 0:
            wins += 1
    return wins / games


def _selfplay_vs(right: str, games: int) -> float:
    model_path = Path("saved_models") / "selfplay_ppo.zip"
    agent = SelfPlayPPOAgent(model_path)
    wins = 0
    if right == "PPOAgent":
        opponent: str | Path = Path("saved_models") / "ppo_basic.zip"
    elif right == "HeuristicAgent":
        opponent = "heuristic"
    else:
        opponent = "random"

    for seed in range(games):
        env = DuelMastersSelfPlayEnv(
            SelfPlayConfig(
                fixed_opponent=opponent,
                include_heuristic_opponent=False,
                include_random_opponent=False,
                seed=seed,
            )
        )
        env.reset()
        terminated = False
        truncated = False
        while not (terminated or truncated):
            action_id = agent.act(env, player_id=0)
            _observation, _reward, terminated, truncated, _info = env.step(action_id)
        if env.base_env.state is not None and env.base_env.state.winner == 0:
            wins += 1
    return wins / games


def _make_basic_agent(name: str, seed: int) -> RandomAgent | HeuristicAgent:
    if name == "HeuristicAgent":
        return HeuristicAgent()
    return RandomAgent(seed=seed)


if __name__ == "__main__":
    main()
