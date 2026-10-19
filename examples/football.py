"""ruleatlas-python: referee-confirmed events and automatic rule consequences."""
from ruleatlas import new_state, apply_action, legal_actions, outcome

state = new_state('S001', players=[{'id': 'home'}, {'id': 'away'}])
state = apply_action(state, {'type': 'start_period', 'params': {}})
state = apply_action(state, {'type': 'goal', 'params': {'team': 0}})
for _ in range(2):
    state = apply_action(state, {
        'type': 'card', 'params': {'team': 1, 'player': 3, 'color': 'yellow'},
    })
assert state['data']['teams'][1]['red'][3] is True
print(state['data']['goals'])
print(legal_actions(state)['constraints'])
print(outcome(state))
