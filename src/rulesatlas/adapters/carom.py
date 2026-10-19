"""Three-cushion carom to forty with equal innings, using adjudicated shot facts."""
from copy import deepcopy
from ..values import fields,fail

def validate(d):
    a,b=d['innings'];p,q=d['points'];done=d['phase']=='finished'
    if a<1 or b>a or a-b>1 or (not done and ((d['turn']==0 and a!=b+1) or (d['turn']==1 and a!=b))):fail('Inning counts and current player disagree',code='INVALID_STATE')
    if d['equalizing']!=(p==40 and q<=40 and d['turn']==1):fail('Equalizing inning requires the first player to have reached forty',code='INVALID_STATE')
    if sum(d['points'])>d['shots'] or a+b-1>d['shots']:fail('Points or innings exceed recorded shots',code='INVALID_STATE')
    if d['shots']==0 and (d['points']!=[0,0] or d['innings']!=[1,0] or d['turn']!=0 or not d['opening_required']):fail('Invalid opening position',code='INVALID_STATE')
    if not done and p==40 and not d['equalizing']:fail('First player reaching forty requires the equalizing inning',code='INVALID_STATE')
    if done and d['decision'] is None and (d['turn']!=1 or a!=b or d['opening_required']):fail('A normal finish must complete equal innings',code='INVALID_STATE')
    if not done and (q==40 or d['decision'] is not None):fail('A completed game must be terminal',code='INVALID_STATE')
    if done and d['decision'] is None and p<40 and q<40:fail('A normal finish requires a player to reach forty',code='INVALID_STATE')
    if done and d['decision'] is not None and d['decision']['kind']=='walkover' and d['shots']!=0:fail('Walkover requires no recorded shot',code='INVALID_STATE')
    if d['opening_required'] and d['shots']>0 and not d['equalizing']:fail('A new opening position is used only for the equalizing inning',code='INVALID_STATE')

def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];k=action['type'];t=int(d['turn'])
    if k=='end_match':
        fields(p,dict(player=dict(type='integer',minimum=0,maximum=1),kind=dict(type='string',enum=['retirement','disqualification','walkover'])),'/params')
        if p['kind']=='walkover' and d['shots']:fail('Walkover requires no recorded shot')
        d['decision']=deepcopy(p);d['phase']='finished';return d
    if k!='shot':fail('Unknown action')
    fields(p,dict(contacts=dict(type='array',minItems=0,maxItems=2,items=dict(type='string',enum=['red','opponent'])),cushions_before_second=dict(type='integer',minimum=0,maximum=100),foul=dict(type='boolean')),'/params')
    if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
    if len(set(p['contacts']))!=len(p['contacts']):fail('Contacts list records the first contact with each distinct object ball')
    good=len(p['contacts'])==2 and p['cushions_before_second']>=3 and not p['foul'] and (not d['opening_required'] or p['contacts'][0]=='red')
    d['shots']+=1;d['opening_required']=False
    if good:
        d['points'][t]+=1
        if d['points'][t]==40:
            if t==1:d['phase']='finished'
            else:d['turn']=1;d['innings'][1]+=1;d['equalizing']=True;d['opening_required']=True
    elif t==0:d['turn']=1;d['innings'][1]+=1
    elif d['equalizing']:d['phase']='finished'
    else:d['turn']=0;d['innings'][0]+=1
    return d

def legal(state):
    d=state['data'];kinds=['retirement','disqualification']+(['walkover'] if d['shots']==0 else [])
    return dict(mode='event_types',actions=[],action_types=[dict(type='shot',params_schema=dict(contacts=dict(type='array',minItems=0,maxItems=2,items=dict(type='string',enum=['red','opponent'])),cushions_before_second=dict(type='integer',minimum=0,maximum=100),foul=dict(type='boolean')),preconditions=['Record each distinct object ball once in first-contact order; cushion count is before contacting the second distinct object ball. Opening requires red first.'],external_observations=['Official object contacts, cushion count and any foul.']),dict(type='end_match',params_schema=dict(player=dict(type='integer',minimum=0,maximum=1),kind=dict(type='string',enum=kinds)),preconditions=['Official decision identifies the losing player.'],external_observations=['Retirement, disqualification or pre-play walkover.'])],constraints=dict(turn=d['turn'],target=40,equalizing=d['equalizing'],opening_required=d['opening_required']),completeness=False,reason='adjudicated_shot_facts_without_ball_motion')
def outcome(state,pack):
    d=state['data'];done=d['phase']=='finished';decision=d['decision'];wins=([1-int(decision['player'])] if decision else [p for p in (0,1) if d['points'][p]==max(d['points'])]) if done else []
    return dict(status='terminal' if done else 'ongoing',result_kind=({'retirement':'technical','disqualification':'disqualification','walkover':'forfeit'}[decision['kind']] if decision else 'draw' if len(wins)==2 else 'win') if done else 'none',winners=[state['players'][p]['id'] for p in wins],losers=[state['players'][p]['id'] for p in (0,1) if p not in wins] if done else [],placements=[dict(player_id=state['players'][p]['id'],place=1 if p in wins else 2,points=d['points'][p],innings=d['innings'][p]) for p in (0,1)] if done else [],reason=decision['kind'] if decision else 'target_with_equal_innings' if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
