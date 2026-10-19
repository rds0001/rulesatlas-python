"""Three-player Maexchen with externally supplied secret dice and public claims."""
from copy import deepcopy
from ..values import fields,fail
VALUES=sorted([10*a+b for a in range(1,7) for b in range(1,a+1) if a!=b and (a,b)!=(2,1)])+[11,22,33,44,55,66,21]
def value(dice):return 10*max(dice)+min(dice)
def next_player(d,t):return next((t+i)%3 for i in range(1,4) if d['lives'][(t+i)%3]>0)
def validate(d):
    alive=[i for i,v in enumerate(d['lives']) if v>0]
    if not alive or d['turn'] not in alive or (d['phase']=='finished')!=(len(alive)==1):fail('Lives, turn and phase mismatch',code='INVALID_STATE')
    bid=d['bid']
    if bid is not None:
        if bid['claim'] not in VALUES or bid['actual'] not in VALUES or bid['player'] not in alive or d['turn']!=next_player(d,int(bid['player'])):fail('Invalid claim or responding player',code='INVALID_STATE')
    if d['phase']=='respond' and bid is None or d['phase'] in ('roll','finished') and bid is not None:fail('Claim and phase mismatch',code='INVALID_STATE')
    if len(d['dice'])!=(2 if d['phase']=='claim' else 0):fail('Only the claiming player holds a fresh roll',code='INVALID_STATE')
    if d['phase']=='claim' and bid is not None and bid['claim']==21:fail('Maexchen must be challenged',code='INVALID_STATE')
def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];kind=action['type'];t=int(d['turn'])
    if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
    if kind=='roll':
        fields(p,dict(dice=dict(type='array',minItems=2,maxItems=2,items=dict(type='integer',minimum=1,maximum=6))),'/params')
        if d['phase'] not in ('roll','respond') or d['bid'] is not None and d['bid']['claim']==21:fail('Cannot accept and reroll in this phase')
        d['dice']=p['dice'][:];d['phase']='claim';return d
    if kind=='claim':
        fields(p,dict(value=dict(type='integer',minimum=11,maximum=66)),'/params');v=p['value']
        if d['phase']!='claim' or v not in VALUES or d['bid'] is not None and VALUES.index(v)<=VALUES.index(d['bid']['claim']):fail('Claim must strictly increase in dice rank')
        d['bid']=dict(player=t,claim=v,actual=value(d['dice']));d['dice']=[];d['turn']=next_player(d,t);d['phase']='respond';return d
    if kind!='challenge':fail('Unknown action')
    fields(p,{},'/params')
    if d['phase']!='respond':fail('Only the next player may challenge before accepting the dice')
    bid=d['bid'];loser=t if VALUES.index(bid['actual'])>=VALUES.index(bid['claim']) else int(bid['player']);penalty=2 if bid['claim']==21 else 1
    d['lives'][loser]=max(0,d['lives'][loser]-penalty);d['turn']=loser if d['lives'][loser]>0 else next_player(d,loser);d['bid']=None;d['phase']='finished' if sum(v>0 for v in d['lives'])==1 else 'roll';return d

def legal(state):
    d=state['data'];bid=d['bid']
    if d['phase']=='claim':return [dict(type='claim',params=dict(value=v)) for v in VALUES if bid is None or VALUES.index(v)>VALUES.index(bid['claim'])]
    actions=[dict(type='challenge',params={})] if d['phase']=='respond' else []
    types=[]
    if bid is None or bid['claim']!=21:types=[dict(type='roll',params_schema=dict(dice=dict(type='array',minItems=2,maxItems=2,items=dict(type='integer',minimum=1,maximum=6))),preconditions=['Rolling accepts the previous claim and prevents challenging it.'],external_observations=['Two secret dice supplied by the current player to the host.'])]
    return dict(mode='event_types',actions=actions,action_types=types,constraints=dict(player=d['turn']),completeness=False,reason='externally_observed_dice')
def outcome(state,pack):
    d=state['data'];terminal=d['phase']=='finished';wins=[state['players'][p]['id'] for p,v in enumerate(d['lives']) if v>0] if terminal else []
    return dict(status='terminal' if terminal else 'ongoing',result_kind='win' if terminal else 'none',winners=wins,losers=[p['id'] for p in state['players'] if p['id'] not in wins] if terminal else [],placements=[],reason='last_player_with_lives' if terminal else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
