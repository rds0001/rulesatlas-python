"""Individual nine-pin 120-delivery total-pin contest with explicit roll-offs."""
from copy import deepcopy
from ..values import fields,fail
PINS=list(range(9));PLAYER=dict(type='integer',minimum=0,maximum=1)
def validate(d):
    if len(set(d['standing']))!=len(d['standing']):fail('Standing pins must be distinct',code='INVALID_STATE')
    for p in (0,1):
        if len(d['scores'][p])>4 or any(len(s)!=30 for s in d['scores'][p][:-1]):fail('Only the current lane may have fewer than thirty deliveries',code='INVALID_STATE')
    if d['phase']=='regulation':
        a=d['scores'][d['turn']];b=d['scores'][1-d['turn']]
        if len(a)!=d['lane']+1 or len(a[-1])>=30 or len(b) not in (d['lane'],d['lane']+1) or (len(b)==d['lane']+1 and len(b[-1])!=30):fail('Current lane and delivery order disagree with scorecards',code='INVALID_STATE')
        if len(a[-1])<15 and sorted(d['standing'])!=PINS:fail('Full-frame deliveries require all nine standing pins',code='INVALID_STATE')
        if d['rolloff_round'] or any(d['rolloff']):fail('Roll-off data requires tied completed regulation',code='INVALID_STATE')
    if d['phase']=='rolloff':
        if any(len(s)!=4 or any(len(x)!=30 for x in s) for s in d['scores']) or totals(d)[0]!=totals(d)[1]:fail('Roll-offs require tied completed regulation',code='INVALID_STATE')
        if len(d['rolloff'][d['turn']])>=3 or len(d['rolloff'][1-d['turn']]) not in (0,3):fail('Each roll-off participant takes three deliveries',code='INVALID_STATE')
        if sorted(d['standing'])!=PINS:fail('Roll-off deliveries are into a full frame',code='INVALID_STATE')
    if d['phase']!='finished':
        if d['winner'] is not None or d['withdrawn'] is not None:fail('Ongoing contest cannot have a winner or withdrawal',code='INVALID_STATE')
    else:
        w=d['winner']
        if w is None:fail('A finished contest requires a winner',code='INVALID_STATE')
        if d['withdrawn'] is not None:
            if w==d['withdrawn']:fail('Withdrawn participant cannot win',code='INVALID_STATE')
        else:
            if any(len(s)!=4 or any(len(x)!=30 for x in s) for s in d['scores']):fail('Complete all four lanes before declaring a total winner',code='INVALID_STATE')
            scores=totals(d)
            if scores[0]==scores[1]:
                if any(len(x)!=3 for x in d['rolloff']) or sum(d['rolloff'][w])<=sum(d['rolloff'][1-w]):fail('Tied regulation requires a winning roll-off',code='INVALID_STATE')
            elif scores[w]<=scores[1-w]:fail('Highest total must win',code='INVALID_STATE')
def totals(d):return [sum(sum(lane) for lane in s) for s in d['scores']]
def apply(state,action):
    d=deepcopy(state['data']);k=action['type'];p=action['params'];t=d['turn']
    if k=='withdraw':
        fields(p,dict(player=PLAYER),'/params');q=p['player']
        if action.get('actor') is not None and action['actor']!=state['players'][q]['id']:fail('Wrong actor')
        d['withdrawn']=q;d['winner']=1-q;d['phase']='finished';return d
    if k!='delivery':fail('Unknown action')
    fields(p,dict(knocked=dict(type='array',minItems=0,maxItems=9,items=dict(type='integer',minimum=0,maximum=8)),foul=dict(type='boolean')),'/params')
    if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
    pins=p['knocked']
    if len(set(pins))!=len(pins) or any(x not in d['standing'] for x in pins):fail('Only distinct standing pins can be knocked down')
    score=0 if p['foul'] else len(pins)
    if d['phase']=='rolloff':
        d['rolloff'][t].append(score)
        if len(d['rolloff'][t])==3:
            if not d['rolloff'][1-t]:d['turn']=1-t
            elif sum(d['rolloff'][0])!=sum(d['rolloff'][1]):d['winner']=0 if sum(d['rolloff'][0])>sum(d['rolloff'][1]) else 1;d['phase']='finished'
            else:d['rolloff_round']+=1;d['rolloff']=[[],[]];d['turn']=d['rolloff_round']%2
        return d
    lane=d['scores'][t][-1];clearing=len(lane)>=15;lane.append(score)
    if clearing and not p['foul']:d['standing']=[x for x in d['standing'] if x not in pins]
    if not d['standing'] or len(lane)<=15:d['standing']=PINS[:]
    if len(lane)==30:
        d['standing']=PINS[:]
        if len(d['scores'][1-t])==d['lane']:
            d['turn']=1-t;d['scores'][1-t].append([])
        elif d['lane']<3:
            d['lane']+=1;d['turn']=d['lane']%2;d['scores'][d['turn']].append([])
        else:
            total=totals(d)
            if total[0]==total[1]:d['phase']='rolloff';d['turn']=0
            else:d['phase']='finished';d['winner']=0 if total[0]>total[1] else 1
    return d
def legal(state):
    d=state['data'];return dict(mode='event_types',actions=[dict(type='withdraw',params=dict(player=p)) for p in (0,1)],action_types=[dict(type='delivery',params_schema=dict(knocked=dict(type='array',minItems=0,maxItems=9,items=dict(type='integer',minimum=0,maximum=8)),foul=dict(type='boolean')),preconditions=['Distinct knocked pins must be a subset of the standing frame. A foul consumes a delivery, scores zero and restores its previous frame.'],external_observations=['Adjudicated knocked-pin identities and foul flag.'])],constraints=dict(turn=d['turn'],lane=d['lane']+1,standing=d['standing'],mode='full' if d['phase']=='rolloff' or len(d['scores'][d['turn']][-1])<15 else 'clearing'),completeness=False,reason='externally_observed_pinfall')
def outcome(state,pack):
    d=state['data'];done=d['phase']=='finished';w=d['winner'];ts=totals(d)
    return dict(status='terminal' if done else 'ongoing',result_kind='win' if done else 'none',winners=[state['players'][w]['id']] if done else [],losers=[state['players'][1-w]['id']] if done else [],placements=[dict(player_id=state['players'][p]['id'],place=1 if p==w else 2,pins=ts[p],rolloff_pins=sum(d['rolloff'][p])) for p in (0,1)] if done else [],reason=('withdrawal' if d['withdrawn'] is not None else 'rolloff' if ts[0]==ts[1] else 'highest_total') if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
