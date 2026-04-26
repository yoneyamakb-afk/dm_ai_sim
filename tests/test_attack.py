from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.card import Card
from dm_ai_sim.env import Env, EnvConfig


def test_summoning_sick_creature_cannot_attack_until_next_own_turn() -> None:
    deck = [Card(id=i, name=f"C{i}", cost=1, power=1000) for i in range(40)]
    env = Env(deck0=deck, deck1=deck, config=EnvConfig(seed=1))
    env.reset()

    env.step(Action(ActionType.CHARGE_MANA, card_index=0))
    env.step(next(action for action in env.legal_actions() if action.type == ActionType.SUMMON))
    env.step(Action(ActionType.END_MAIN))

    assert all(action.type != ActionType.ATTACK_SHIELD for action in env.legal_actions())


def test_creature_can_attack_shield_on_later_turn() -> None:
    deck = [Card(id=i, name=f"C{i}", cost=1, power=1000) for i in range(40)]
    env = Env(deck0=deck, deck1=deck, config=EnvConfig(seed=1))
    env.reset()

    env.step(Action(ActionType.CHARGE_MANA, card_index=0))
    env.step(next(action for action in env.legal_actions() if action.type == ActionType.SUMMON))
    env.step(Action(ActionType.END_MAIN))
    env.step(Action(ActionType.END_ATTACK))
    env.step(Action(ActionType.END_MAIN))
    env.step(Action(ActionType.END_ATTACK))
    env.step(Action(ActionType.END_MAIN))
    attack = next(action for action in env.legal_actions() if action.type == ActionType.ATTACK_SHIELD)
    observation, _reward, _done, _info = env.step(attack)

    assert observation["opponent"]["shield_count"] == 4
