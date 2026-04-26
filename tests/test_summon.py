from dm_ai_sim.actions import Action, ActionType
from dm_ai_sim.card import Card
from dm_ai_sim.env import Env, EnvConfig


def test_summon_taps_mana_and_puts_creature_in_battle_zone() -> None:
    deck = [Card(id=i, name=f"C{i}", cost=1, power=1000) for i in range(40)]
    env = Env(deck0=deck, deck1=deck, config=EnvConfig(seed=1))
    env.reset()

    env.step(Action(ActionType.CHARGE_MANA, card_index=0))
    summon = next(action for action in env.legal_actions() if action.type == ActionType.SUMMON)
    observation, _reward, _done, _info = env.step(summon)

    assert observation["self"]["hand_count"] == 3
    assert len(observation["self"]["battle_zone"]) == 1
    assert observation["self"]["mana"][0]["tapped"]
