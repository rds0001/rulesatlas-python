"""Three-player single-hand Thirty-One / Schwimmen with a shared three-card pool."""
from copy import deepcopy
from ..values import fields,fail
CARD=dict(type='integer',minimum=0,maximum=31)
def score(h):
    ranks=[int(c)%8 for c in h]
    if len(set(ranks))==1:return 61
    return max(sum((11 if int(c)%8==7 else min(10,7+int(c)%8))*2 for c in h if int(c)//8==s) for s in range(4))
def finish_turn(d):
    if any(score(h)==62 for h in d['hands']):d['phase']='finished';d['reason']='thirty_one';return d
    if d['knocker'] is not None:
        d['remaining']-=1
        if d['remaining']==0:d['phase']='finished';d['reason']='last_round';return d
    d['turn']=(int(d['turn'])+1)%3
    if d['passes']==3:d['phase']='refresh'
    return d

def validate(d):
    if d['phase']=='setup':
        if any(d['hands']) or d['table'] or d['stock'] or d['discard'] or d['knocker'] is not None or d['remaining'] or d['passes'] or d['reason'] is not None:fail('Setup must be empty',code='INVALID_STATE')
        return
    if any(len(h)!=3 for h in d['hands']) or len(d['table'])!=3 or sorted(sum(d['hands'],[])+d['table']+d['stock']+d['discard'])!=list(range(32)):fail('Three cards per hand and table; every deck card must occur once',code='INVALID_STATE')
    if (d['knocker'] is None and d['remaining']!=0) or (d['knocker'] is not None and d['remaining']>2):fail('Last-round counter requires a knocker',code='INVALID_STATE')
    if d['phase']=='finished':
        if d['reason']=='thirty_one':
            if not any(score(h)==62 for h in d['hands']):fail('Thirty-one ending requires a thirty-one hand',code='INVALID_STATE')
        elif d['reason']=='last_round':
            if d['knocker'] is None or d['remaining']!=0 or any(score(h)==62 for h in d['hands']):fail('Last round must be completed',code='INVALID_STATE')
        else:fail('Terminal reason is required',code='INVALID_STATE')
    elif d['reason'] is not None or any(score(h)==62 for h in d['hands']) or (d['knocker'] is not None and d['remaining']==0):fail('Completed hands must be terminal',code='INVALID_STATE')
    if d['phase']!='finished' and ((d['phase']=='refresh')!=(d['passes']==3)):fail('Three consecutive passes require a table refresh',code='INVALID_STATE')
    if d['knocker'] is not None and d['phase']!='finished' and d['turn']!=(d['knocker']+3-d['remaining'])%3:fail('Turn must follow the knocker in the last round',code='INVALID_STATE')

def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];k=action['type'];t=int(d['turn'])
    if k=='deal':
        fields(p,dict(deck=dict(type='array',minItems=32,maxItems=32,items=CARD)),'/params')
        if d['phase']!='setup' or len(set(p['deck']))!=32:fail('Supply the full thirty-two-card deck once')
        d['hands']=[p['deck'][i:9:3] for i in range(3)];d['table']=p['deck'][9:12];d['stock']=p['deck'][12:];d['phase']='play'
        if any(score(h)==62 for h in d['hands']):d['phase']='finished';d['reason']='thirty_one'
        return d
    if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
    if k=='recycle':
        fields(p,dict(order=dict(type='array',minItems=1,maxItems=31,items=CARD)),'/params')
        if d['phase']!='refresh' or len(d['stock'])>=3 or not d['discard'] or sorted(p['order'])!=sorted(d['discard']):fail('Recycle discarded former tables only when the refresh stock is short')
        d['stock']+=p['order'];d['discard']=[];return d
    if k=='refresh':
        fields(p,{},'/params')
        if d['phase']!='refresh' or len(d['stock'])<3:fail('Refresh after three passes, recycling first if needed')
        d['discard']+=d['table'];d['table']=d['stock'][:3];d['stock']=d['stock'][3:];d['passes']=0;d['phase']='play';return d
    if d['phase']!='play':fail('Deal or refresh before taking a turn')
    if k=='knock':
        fields(p,{},'/params')
        if d['knocker'] is not None:fail('Only the first knock starts the last round')
        d['knocker']=t;d['remaining']=2;d['turn']=(t+1)%3;d['passes']=0;return d
    if k=='pass':fields(p,{},'/params');d['passes']+=1;return finish_turn(d)
    if k=='exchange_all':
        fields(p,{},'/params');d['hands'][t],d['table']=d['table'],d['hands'][t]
    elif k=='exchange':
        fields(p,dict(hand=dict(type='integer',minimum=0,maximum=2),table=dict(type='integer',minimum=0,maximum=2)),'/params');i=int(p['hand']);j=int(p['table']);d['hands'][t][i],d['table'][j]=d['table'][j],d['hands'][t][i]
    else:fail('Unknown action')
    d['passes']=0;return finish_turn(d)

def legal(state):
    d=state['data'];types=[];actions=[]
    if d['phase']=='setup':types=[dict(type='deal',params_schema=dict(deck=dict(type='array',minItems=32,maxItems=32,items=CARD)),preconditions=['Every card once, in deal/draw order.'],external_observations=['External deck order.'])]
    elif d['phase']=='refresh':
        if len(d['stock'])>=3:actions=[dict(type='refresh',params={})]
        else:types=[dict(type='recycle',params_schema=dict(order=dict(type='array',minItems=1,maxItems=31,items=CARD)),preconditions=['Permutation of the discarded former tables; existing stock stays first.'],external_observations=['External reshuffle order.'])]
    else:
        actions=[dict(type='exchange',params=dict(hand=i,table=j)) for i in range(3) for j in range(3)]+[dict(type=k,params={}) for k in ('exchange_all','pass')]
        if d['knocker'] is None:actions.append(dict(type='knock',params={}))
    return dict(mode='event_types',actions=actions,action_types=types,constraints=dict(turn=d['turn'],remaining=d['remaining']),completeness=False,reason='card_actions_and_external_deck_order')
def outcome(state,pack):
    d=state['data'];done=d['phase']=='finished';scores=[score(h) for h in d['hands']] if d['phase']!='setup' else [];wins=[p for p in range(3) if scores[p]==max(scores)] if done else []
    return dict(status='terminal' if done else 'ongoing',result_kind=('draw' if len(wins)>1 else 'win') if done else 'none',winners=[state['players'][p]['id'] for p in wins],losers=[state['players'][p]['id'] for p in range(3) if p not in wins] if done else [],placements=[dict(player_id=state['players'][p]['id'],place=1+sum(x>scores[p] for x in scores),score_half_points=scores[p]) for p in range(3)] if done else [],reason=d['reason'] if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
