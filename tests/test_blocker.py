from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.card import Card, make_vanilla_deck
from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.gym_env import DuelMastersGymConfig, DuelMastersGymEnv
from dm_ai_sim.selfplay_env import DuelMastersSelfPlayEnv, SelfPlayConfig
from dm_ai_sim.state import Creature, Phase


def test_card_can_be_blocker_and_deck_mixes_blockers() -> None:
    card = Card(id=1, name="Guard", cost=2, power=2000, blocker=True)
    deck = make_vanilla_deck()

    assert card.blocker
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

    assert info["blocked"]
    assert info["blocker_index"] == 0
    assert info["blocker_name"] == "Blocker"
    assert len(env.state.players[1].shields) == shields_before


def test_tapped_blocker_cannot_block() -> None:
    env = _attack_env(blocker=_blocker(power=5000, tapped=True))
    shields_before = len(env.state.players[1].shields)

    _obs, _reward, _done, info = env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    assert not info["blocked"]
    assert len(env.state.players[1].shields) == shields_before - 1


def test_blocker_battle_destroys_only_attacker() -> None:
    env = _attack_env(blocker=_blocker(power=5000), attacker_power=3000)

    _obs, _reward, _done, info = env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    assert info["blocked"]
    assert len(env.state.players[0].battle_zone) == 0
    assert len(env.state.players[1].battle_zone) == 1


def test_blocker_battle_destroys_only_blocker() -> None:
    env = _attack_env(blocker=_blocker(power=2000), attacker_power=5000)

    _obs, _reward, _done, info = env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    assert info["blocked"]
    assert len(env.state.players[0].battle_zone) == 1
    assert len(env.state.players[1].battle_zone) == 0


def test_blocker_battle_trade() -> None:
    env = _attack_env(blocker=_blocker(power=3000), attacker_power=3000)

    _obs, _reward, _done, info = env.step(Action(ActionType.ATTACK_SHIELD, attacker_index=0))

    assert info["blocked"]
    assert len(env.state.players[0].battle_zone) == 0
    assert len(env.state.players[1].battle_zone) == 0


def test_player_attack_can_be_blocked_without_win() -> None:
    env = _attack_env(blocker=_blocker(power=5000), attacker_power=3000)
    env.state.players[1].shields.clear()

    _obs, _reward, done, info = env.step(Action(ActionType.ATTACK_PLAYER, attacker_index=0))

    assert info["blocked"]
    assert not done
    assert env.state.winner is None


def test_gym_and_selfplay_envs_survive_blocker_observation() -> None:
    gym_env = DuelMastersGymEnv(DuelMastersGymConfig(seed=1))
    gym_obs, gym_info = gym_env.reset()
    selfplay_env = DuelMastersSelfPlayEnv(SelfPlayConfig(seed=1, fixed_opponent="random"))
    selfplay_obs, selfplay_info = selfplay_env.reset()

    assert gym_obs.shape == gym_env.observation_space.shape
    assert selfplay_obs.shape == selfplay_env.observation_space.shape
    assert len(gym_info["action_mask"]) == 256
    assert len(selfplay_info["action_mask"]) == 256
