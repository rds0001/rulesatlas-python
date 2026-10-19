"""Two-player Shut the Box: one round each, tiles 1–9, lowest total wins."""
from copy import deepcopy
from itertools import combinations
from ..values import fields,fail

def choices(d):
    if d['roll_sum'] is None:return []
    opened=[i+1 for i,x in enumerate(d['open']) if x]
    return [list(c) for n in range(1,len(opened)+1) for c in combinations(opened,n) if sum(c)==d['roll_sum']]
def validate(d):
    t=int(d['turn']);scores=d['scores'];phase=d['phase']
    if t==0 and scores[0] is not None or t==1 and scores[0] is None:fail('Round order mismatch',code='INVALID_STATE')
    if phase=='finished':
        if t!=1 or scores[1]!=sum(i+1 for i,x in enumerate(d['open']) if x) or d['roll_sum'] is not None:fail('Final round score mismatch',code='INVALID_STATE')
    elif scores[t] is not None or not any(d['open']):fail('Round must be closed',code='INVALID_STATE')
    if (phase=='close')!=(d['roll_sum'] is not None):fail('Roll phase mismatch',code='INVALID_STATE')
    if phase=='close':
        if d['roll_sum']==1 and any(d['open'][6:]):fail('One die is not available',code='INVALID_STATE')
        if not choices(d):fail('A blocked roll must end the round',code='INVALID_STATE')
def end_round(d):
    d['scores'][int(d['turn'])]=sum(i+1 for i,x in enumerate(d['open']) if x);d['roll_sum']=None
    if d['turn']==0:d['turn']=1;d['open']=[True]*9;d['phase']='roll'
    else:d['phase']='finished'
def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];t=int(d['turn'])
    if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
    if d['phase']=='roll':
        if action['type']!='roll':fail('A dice result is required')
        fields(p,{'dice':{'type':'array','items':{'type':'integer','minimum':1,'maximum':6},'minItems':1,'maxItems':2}},'/params')
        if len(p['dice'])==1 and any(d['open'][6:]):fail('One die is unavailable while 7, 8 or 9 is open')
        d['roll_sum']=sum(p['dice']);d['phase']='close'
        if not choices(d):end_round(d)
    else:
        if action['type']!='close':fail('Choose tiles matching the roll')
        fields(p,{'tiles':{'type':'array','items':{'type':'integer','minimum':1,'maximum':9},'minItems':1,'maxItems':9}},'/params');tiles=p['tiles']
        if sorted(tiles) not in choices(d):fail('Tiles must be distinct, open and sum to the roll')
        for tile in tiles:d['open'][int(tile)-1]=False
        d['roll_sum']=None;d['phase']='roll'
        if not any(d['open']):end_round(d)
    return d
def legal(state):
    d=state['data']
    if d['phase']=='close':return [dict(type='close',params={'tiles':tiles}) for tiles in choices(d)]
    return dict(mode='event_types',actions=[],action_types=[dict(type='roll',params_schema={'dice':{'type':'array','items':{'type':'integer','minimum':1,'maximum':6},'minItems':1 if not any(d['open'][6:]) else 2,'maxItems':2}},preconditions=['One die is optional only when tiles 7, 8 and 9 are all closed.'],external_observations=['Observed dice result; no dice are generated.'])],constraints={'actor':state['players'][int(d['turn'])]['id']},completeness=False,reason='external_dice_result')
def outcome(state,pack):
    d=state['data'];terminal=d['phase']=='finished';w=None if not terminal or d['scores'][0]==d['scores'][1] else 0 if d['scores'][0]<d['scores'][1] else 1
    return dict(status='terminal' if terminal else 'ongoing',result_kind=('draw' if w is None else 'win') if terminal else 'none',winners=[] if w is None else [state['players'][w]['id']],losers=[] if w is None else [state['players'][1-w]['id']],placements=[],reason='both_rounds_completed' if terminal else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
