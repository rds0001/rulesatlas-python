"""Two-player 501, straight-in and double-out, one leg."""
from copy import deepcopy
from ..values import fields,fail
THROWS=[(0,0)]+[(s,m) for s in range(1,21) for m in (1,2,3)]+[(25,1),(25,2)]
def validate(d):
    scores=d['remaining'];t=int(d['turn']);used=d['darts_used']
    if 1 in scores or scores.count(0)>1:fail('Invalid remaining scores',code='INVALID_STATE')
    if used==3 and 0 not in scores:fail('A three-dart turn must be closed',code='INVALID_STATE')
    if scores[t]>d['turn_start'] or d['turn_start']-scores[t]>60*used:fail('Turn score is inconsistent',code='INVALID_STATE')
    if 0 in scores and (scores[t]!=0 or used==0):fail('Invalid completed leg',code='INVALID_STATE')
def legal(state):return [dict(type='throw',params={'segment':s,'multiplier':m}) for s,m in THROWS]
def apply(state,action):
    if action['type']!='throw':fail('Unknown action')
    fields(action['params'],{'segment':{'type':'integer','minimum':0,'maximum':25},'multiplier':{'type':'integer','minimum':0,'maximum':3}},'/params')
    s=action['params']['segment'];m=action['params']['multiplier']
    if (s,m) not in THROWS:fail('Invalid dartboard target')
    d=deepcopy(state['data']);t=int(d['turn'])
    if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
    remaining=d['remaining'][t]-s*m;d['darts_used']+=1
    bust=remaining<0 or remaining==1 or (remaining==0 and m!=2)
    d['remaining'][t]=d['turn_start'] if bust else remaining
    if bust or (remaining!=0 and d['darts_used']==3):
        d['turn']=1-t;d['darts_used']=0;d['turn_start']=d['remaining'][1-t]
    return d
def outcome(state,pack):
    d=state['data'];terminal=0 in d['remaining'];w=d['remaining'].index(0) if terminal else None
    return dict(status='terminal' if terminal else 'ongoing',result_kind='win' if terminal else 'none',winners=[] if w is None else [state['players'][w]['id']],losers=[] if w is None else [state['players'][1-w]['id']],placements=[],reason='double_out' if terminal else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
