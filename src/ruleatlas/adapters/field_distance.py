"""Three-round distance-event qualification: official marks, ranking and cutoff."""
from copy import deepcopy
from ..values import fields,fail
ATTEMPT=dict(type='object',properties=dict(kind=dict(type='string',enum=['valid','foul','pass']),distance_mm=dict(type='integer',minimum=0,maximum=200000)),required=['kind','distance_mm'])
def key(attempts):return tuple(sorted([a['distance_mm'] for a in attempts if a['kind']=='valid'],reverse=True)+[0]*(3-sum(a['kind']=='valid' for a in attempts)))
def automatic(d,p):return d['qualifying_mm'] is not None and key(d['attempts'][p])[0]>=d['qualifying_mm']
def advance(d):
    while d['current']<36 and (d['status'][int(d['current'])%12]!='active' or automatic(d,int(d['current'])%12)):d['current']+=1
    return d
def validate(d):
    if not d['configured'] and (d['current'] or any(d['attempts']) or d['qualifying_mm'] is not None or d['places']!=8 or any(s!='active' for s in d['status'])):fail('Unconfigured event contains results',code='INVALID_STATE')
    if d['qualifying_mm'] is not None and d['qualifying_mm']%10:fail('Qualification mark must use ten-millimeter units',code='INVALID_STATE')
    for p,attempts in enumerate(d['attempts']):
        available=sum(r*12+p<d['current'] for r in range(3))
        if len(attempts)>available:fail('Attempt belongs to a future round',code='INVALID_STATE')
        for i,a in enumerate(attempts):
            if (a['kind']=='valid' and (a['distance_mm']<=0 or a['distance_mm']%10)) or (a['kind']!='valid' and a['distance_mm']!=0):fail('Invalid official mark',code='INVALID_STATE')
            if d['qualifying_mm'] is not None and any(x['distance_mm']>=d['qualifying_mm'] for x in attempts[:i]):fail('Attempts continued after automatic qualification',code='INVALID_STATE')
        if d['status'][p]=='active' and not automatic(d,p) and len(attempts)!=available:fail('Missing scheduled attempt',code='INVALID_STATE')
    if d['current']<36 and (d['status'][int(d['current'])%12]!='active' or automatic(d,int(d['current'])%12)):fail('Inactive athlete must be skipped',code='INVALID_STATE')
def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];kind=action['type']
    if not d['configured']:
        if kind!='configure':fail('Configure qualification first')
        fields(p,dict(places=dict(type='integer',minimum=1,maximum=12),qualifying_mm=dict(type='integer',minimum=10,maximum=200000,nullable=True)),'/params');d.update(p);d['configured']=True;return d
    if kind in ('withdraw','disqualify'):
        fields(p,dict(player=dict(type='integer',minimum=0,maximum=11)),'/params');t=int(p['player'])
        if d['status'][t]=='dq' or kind=='withdraw' and d['status'][t]!='active':fail('Athlete is already inactive')
        d['status'][t]='dq' if kind=='disqualify' else 'withdrawn';return advance(d)
    if kind!='attempt':fail('Unknown action')
    fields(p,ATTEMPT['properties'],'/params');t=int(d['current'])%12
    if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
    d['attempts'][t].append(deepcopy(p));d['current']+=1;return advance(d)
def legal(state):
    d=state['data']
    if not d['configured']:
        types=[dict(type='configure',params_schema=dict(places=dict(type='integer',minimum=1,maximum=12),qualifying_mm=dict(type='integer',minimum=10,maximum=200000,nullable=True)),preconditions=['The automatic qualification mark is null or a multiple of ten millimeters.'],external_observations=['Published qualifying standard and minimum final field size.'])];constraints={}
    else:
        types=[dict(type='attempt',params_schema=ATTEMPT['properties'],preconditions=['Valid distances are positive multiples of ten millimeters; foul and pass use zero.'],external_observations=['Official valid mark, foul ruling or voluntary pass.'])]
        types += [dict(type=k,params_schema=dict(player=dict(type='integer',minimum=0,maximum=11)),preconditions=['Athlete status permits the administrative decision.'],external_observations=['Official withdrawal or disqualification.']) for k in ('withdraw','disqualify')]
        constraints=dict(player=int(d['current'])%12,round=int(d['current'])//12+1)
    return dict(mode='event_types',actions=[],action_types=types,constraints=constraints,completeness=False,reason='externally_adjudicated_distance_attempts')
def outcome(state,pack):
    d=state['data'];terminal=d['configured'] and d['current']==36
    eligible=sorted([(key(a),p) for p,a in enumerate(d['attempts']) if d['status'][p]=='active' and key(a)[0]>0],key=lambda x:(tuple(-v for v in x[0]),x[1])) if terminal else []
    cutoff=eligible[min(int(d['places']),len(eligible))-1][0] if eligible else None
    placements=[dict(player_id=state['players'][p]['id'],place=1+sum(other>k for other,_ in eligible),best_mm=k[0],qualified=automatic(d,p) or k>=cutoff) for k,p in eligible]
    winners=[state['players'][p]['id'] for k,p in eligible if k==eligible[0][0]] if eligible else []
    return dict(status='terminal' if terminal else 'ongoing',result_kind=('ranking' if eligible else 'no_contest') if terminal else 'none',winners=winners,losers=[state['players'][p]['id'] for k,p in eligible if k!=eligible[0][0]] if eligible else [],placements=placements,reason='qualification_completed' if terminal else 'ongoing' if d['configured'] else 'awaiting_configuration',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
