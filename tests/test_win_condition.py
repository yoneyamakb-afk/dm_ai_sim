from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.card import Card
from dm_ai_sim.env import Env, EnvConfig
from dm_ai_sim.state import Creature


def test_attack_player_wins_when_opponent_has_no_shields() -> None:
    deck = [Card(id=i, name=f"C{i}", cost=1, power=1000) for i in range(40)]
    env = Env(deck0=deck, deck1=deck, config=EnvConfig(seed=1))
    env.reset()
    assert env.state is not None
    env.state.players[0].battle_zone.append(Creature(card=deck[0], summoned_turn=0))
    env.state.players[1].shields.clear()
    env.state.phase = env.state.phase.ATTACK

    action = next(action for action in env.legal_actions() if action.type == ActionType.ATTACK_PLAYER)
    _observation, reward, done, info = env.step(action)

    assert done
    assert reward == 1.0
    assert info["winner"] == 0
