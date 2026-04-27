from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.action_encoder import ACTION_SPACE_SIZE, decode_action, encode_action, legal_action_mask
from dm_ai_sim.card import Card, make_vanilla_deck
from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.gym_env import DuelMastersGymConfig, DuelMastersGymEnv
from dm_ai_sim.agents.heuristic_agent import HeuristicAgent
from dm_ai_sim.agents.random_agent import RandomAgent
from dm_ai_sim.selfplay_env import DuelMastersSelfPlayEnv, SelfPlayConfig
from dm_ai_sim.state import Creature, Phase


def test_card_can_be_blocker_and_deck_mixes_blockers() -> None:
    card = Card(id=1, name="Guard", cost=2, power=2000, blocker=True)
    deck = make_vanilla_deck()
    block = Action(ActionType.BLOCK, blocker_index=0)
    decline = Action(ActionType.DECLINE_BLOCK)

    assert card.blocker
    assert block.blocker_index == 0
    assert decline.type == ActionType.DECLINE_BLOCK
    assert 0 < sum(1 for deck_card in deck if deck_card.blocker) < len(deck)


def _attack_env(blocker: Creature | None = None, attacker_power: int = 3000) -> Env:
    deck0 = [Card(id=i, name=f"A{i}", cost=1, power=1000) for i in range(40)]
    deck1 = [Card(id=1000 + i, name=f"D{i}", cost=1, power=1000) for i in range(40)]
    env = Env(deck0=deck0, deck1=deck1, config=EnvConfig(seed=1))
    env.reset()
    assert env.state is not None
    env.state.phase = Phase.ATTACK
    env.state.turn_number = 2
    env.state.players[0].battle_zone.append(
        Creature(Card(id=9001, name="Attacker", cost=1, power=attacker_power), summoned_turn=1)
    )
    if blocker is not None:
        env.state.players[1].battle_zone.append(blocker)
    return env


def _blocker(power: int, tapped: bool = False) -> Creature:
    return Creature(
        Card(id=9002, name="Blocker", cost=2, power=power, blocker=True),
        tapped=tapped,
        summoned_turn=1,
    )


def test_no_blocker_breaks_shield_normally() -> None:
    env = _attack_env()
    shields_before = len(env.state.players[1].shields)

    _obs, _reward, _done, info = env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    assert not info["blocked"]
    assert len(env.state.players[1].shields) == shields_before - 1


def test_untapped_blocker_blocks_shield_attack_and_shield_does_not_decrease() -> None:
    env = _attack_env(blocker=_blocker(power=5000))
    shields_before = len(env.state.players[1].shields)

    _obs, _reward, _done, info = env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    assert info["pending_attack_created"]
    assert env.state.pending_attack is not None
    assert env.state.current_player == 1
    assert {action.type for action in env.legal_actions()} == {ActionType.BLOCK, ActionType.DECLINE_BLOCK}

    _obs, _reward, _done, info = env.step(Action(ActionType.BLOCK, blocker_index=0))

    assert info["blocked"]
    assert info["blocker_index"] == 0
    assert info["blocker_name"] == "Blocker"
    assert len(env.state.players[1].shields) == shields_before
    assert env.state.pending_attack is None
    assert env.state.current_player == 0


def test_tapped_blocker_cannot_block() -> None:
    env = _attack_env(blocker=_blocker(power=5000, tapped=True))
    shields_before = len(env.state.players[1].shields)

    _obs, _reward, _done, info = env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    assert not info["blocked"]
    assert not info["pending_attack_created"]
    assert len(env.state.players[1].shields) == shields_before - 1


def test_blocker_battle_destroys_only_attacker() -> None:
    env = _attack_env(blocker=_blocker(power=5000), attacker_power=3000)

    env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))
    _obs, _reward, _done, info = env.step(Action(ActionType.BLOCK, blocker_index=0))

    assert info["blocked"]
    assert len(env.state.players[0].battle_zone) == 0
    assert len(env.state.players[1].battle_zone) == 1


def test_blocker_battle_destroys_only_blocker() -> None:
    env = _attack_env(blocker=_blocker(power=2000), attacker_power=5000)

    env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))
    _obs, _reward, _done, info = env.step(Action(ActionType.BLOCK, blocker_index=0))

    assert info["blocked"]
    assert len(env.state.players[0].battle_zone) == 1
    assert len(env.state.players[1].battle_zone) == 0


def test_blocker_battle_trade() -> None:
    env = _attack_env(blocker=_blocker(power=3000), attacker_power=3000)

    env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))
    _obs, _reward, _done, info = env.step(Action(ActionType.BLOCK, blocker_index=0))

    assert info["blocked"]
    assert len(env.state.players[0].battle_zone) == 0
    assert len(env.state.players[1].battle_zone) == 0


def test_player_attack_can_be_blocked_without_win() -> None:
    env = _attack_env(blocker=_blocker(power=5000), attacker_power=3000)
    env.state.players[1].shields.clear()

    env.step(Action(ActionType.ATTACK_PLAYER, attacker_index=0))
    _obs, _reward, done, info = env.step(Action(ActionType.BLOCK, blocker_index=0))

    assert info["blocked"]
    assert not done
    assert env.state.winner is None


def test_decline_block_breaks_shield_and_returns_to_attacker() -> None:
    env = _attack_env(blocker=_blocker(power=5000))
    shields_before = len(env.state.players[1].shields)

    env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))
    _obs, _reward, _done, info = env.step(Action(ActionType.DECLINE_BLOCK))

    assert info["declined_block"]
    assert len(env.state.players[1].shields) == shields_before - 1
    assert env.state.pending_attack is None
    assert env.state.current_player == 0
    assert env.state.phase == Phase.ATTACK


def test_pending_attack_rejects_wrong_actions_and_missing_pending_rejects_block() -> None:
    env = _attack_env(blocker=_blocker(power=5000))

    env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))
    try:
        env.step(Action(ActionType.END_ATTACK))
    except ValueError:
        pass
    else:
        raise AssertionError("Expected normal action to fail during pending attack.")

    env.step(Action(ActionType.DECLINE_BLOCK))
    try:
        env.step(Action(ActionType.BLOCK, blocker_index=0))
    except ValueError:
        pass
    else:
        raise AssertionError("Expected BLOCK without pending attack to fail.")


def test_block_action_ids_and_mask_are_available_during_pending_attack() -> None:
    env = _attack_env(blocker=_blocker(power=5000))

    env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))
    action_ids = env.legal_action_ids()
    mask = legal_action_mask(env)

    assert encode_action(Action(ActionType.BLOCK, blocker_index=0)) == 242
    assert decode_action(250) == Action(ActionType.DECLINE_BLOCK)
    assert action_ids == [242, 250]
    assert mask[242] == 1
    assert mask[250] == 1


def test_gym_and_selfplay_envs_survive_blocker_observation() -> None:
    gym_env = DuelMastersGymEnv(DuelMastersGymConfig(seed=1))
    gym_obs, gym_info = gym_env.reset()
    selfplay_env = DuelMastersSelfPlayEnv(SelfPlayConfig(seed=1, fixed_opponent="random"))
    selfplay_obs, selfplay_info = selfplay_env.reset()

    assert gym_obs.shape == gym_env.observation_space.shape
    assert selfplay_obs.shape == selfplay_env.observation_space.shape
    assert len(gym_info["action_mask"]) == ACTION_SPACE_SIZE
    assert len(selfplay_info["action_mask"]) == ACTION_SPACE_SIZE


def test_gym_and_selfplay_envs_process_pending_block_choice() -> None:
    gym_env = DuelMastersGymEnv(DuelMastersGymConfig(seed=1, opponent="heuristic"))
    gym_env.reset()
    gym_env.base_env = _attack_env(blocker=_blocker(power=5000))
    _obs, _reward, done, truncated, _info = gym_env.step(80)

    assert not done
    assert not truncated
    assert gym_env.base_env.state.pending_attack is None
    assert gym_env.base_env.state.current_player == 0

    selfplay_env = DuelMastersSelfPlayEnv(SelfPlayConfig(seed=1, fixed_opponent="heuristic"))
    selfplay_env.reset()
    selfplay_env.base_env = _attack_env(blocker=_blocker(power=5000))
    _obs, _reward, done, truncated, _info = selfplay_env.step(80)

    assert not done
    assert not truncated
    assert selfplay_env.base_env.state.pending_attack is None
    assert selfplay_env.base_env.state.current_player == 0


def test_agents_can_act_during_pending_attack() -> None:
    env = _attack_env(blocker=_blocker(power=5000))

    env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))
    observation = env.get_observation()

    assert RandomAgent(seed=1).act(env.legal_actions(), observation).type in {
        ActionType.BLOCK,
        ActionType.DECLINE_BLOCK,
    }
    assert HeuristicAgent().act(env.legal_actions(), observation).type in {
        ActionType.BLOCK,
        ActionType.DECLINE_BLOCK,
    }
