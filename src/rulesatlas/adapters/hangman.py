"""Two-player Latin-uppercase Hangman, six incorrect distinct letters allowed."""
from copy import deepcopy
from ..values import fields,fail
ALPHABET='ABCDEFGHIJKLMNOPQRSTUVWXYZ'
WORD={'type':'string','minLength':1,'maxLength':64}
LETTER={'type':'enum','values':list(ALPHABET)}
def wrong(d):return sum(c not in d['word'] for c in d['guesses']) if d['word'] else 0
def solved(d):return d['word'] is not None and set(d['word'])<=set(d['guesses'])
def validate(d):
    if d['word'] is not None and any(c not in ALPHABET for c in d['word']):fail('Word must contain uppercase Latin letters only',code='INVALID_STATE')
    if len(set(d['guesses']))!=len(d['guesses']):fail('Repeated letter guess',code='INVALID_STATE')
    if d['word'] is None and d['guesses']:fail('A word is required before guessing',code='INVALID_STATE')
    if wrong(d)>6:fail('Too many incorrect guesses',code='INVALID_STATE')
    if d['guesses']:
        previous=dict(word=d['word'],guesses=d['guesses'][:-1])
        if solved(previous) or wrong(previous)==6:fail('Guesses continued after the end',code='INVALID_STATE')
def apply(state,action):
    d=deepcopy(state['data']);setup=d['word'] is None
    if action.get('actor') is not None and action['actor']!=state['players'][0 if setup else 1]['id']:fail('Wrong actor')
    if setup:
        if action['type']!='set_word':fail('Supply the word first')
        fields(action['params'],{'word':WORD},'/params');d['word']=action['params']['word']
    else:
        if action['type']!='guess':fail('Unknown action')
        fields(action['params'],{'letter':LETTER},'/params');c=action['params']['letter']
        if c in d['guesses']:fail('Letter already guessed')
        d['guesses'].append(c)
    return d
def legal(state):
    if state['data']['word'] is None:return dict(mode='event_types',actions=[],action_types=[dict(type='set_word',params_schema={'word':WORD},preconditions=['Only uppercase Latin letters A through Z.'],external_observations=['An externally chosen word.'])],constraints={},completeness=False,reason='external_word_required')
    return [dict(type='guess',params={'letter':c}) for c in ALPHABET if c not in state['data']['guesses']]
def outcome(state,pack):
    d=state['data'];win=solved(d);terminal=win or wrong(d)==6;w=1 if win else 0
    return dict(status='terminal' if terminal else 'ongoing',result_kind='win' if terminal else 'none',winners=[state['players'][w]['id']] if terminal else [],losers=[state['players'][1-w]['id']] if terminal else [],placements=[],reason='word_completed' if win else 'miss_limit_reached' if terminal else 'awaiting_word' if d['word'] is None else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
