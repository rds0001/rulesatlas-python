"""Vertical-jump qualification with carried failures and height countback."""
from copy import deepcopy
from ..values import fields,fail
HEIGHTS=dict(type='array',minItems=1,maxItems=50,items=dict(type='integer',minimum=10,maximum=10000))
def failures(rows):
    count=0
    for row in rows:
        for v in row:
            if v=='clear':count=0
            elif v=='fail':count+=1
    return count
def done(d,p,h):
    row=d['attempts'][p][h]
    return d['status'][p]!='active' or failures(d['attempts'][p])>=3 or bool(row) and row[-1] in ('clear','pass')
def advance(d):
    while d['height']<len(d['heights_mm']):
        h=int(d['height'])
        for step in range(12):
            p=(int(d['turn'])+step)%12
            if not done(d,p,h):d['turn']=p;return d
        d['height']+=1;d['turn']=0
    return d
def rank(d,p):
    cleared=[i for i,row in enumerate(d['attempts'][p]) if 'clear' in row]
    if not cleared:return (0,0,0)
    h=cleared[-1];row=d['attempts'][p][h]
    return (d['heights_mm'][h],-len(row),-sum(r.count('fail') for r in d['attempts'][p][:h+1]))
def validate(d):
    if not d['configured']:
        if d['heights_mm'] or any(d['attempts']) or d['height'] or d['turn'] or d['places']!=8 or any(v!='active' for v in d['status']):fail('Unconfigured event contains results',code='INVALID_STATE')
        return
    heights=d['heights_mm'];n=len(heights)
    if not n or any(h%10 for h in heights) or any(a>=b for a,b in zip(heights,heights[1:])):fail('Heights must increase in ten-millimeter units',code='INVALID_STATE')
    if d['height']>n or any(len(rows)!=n for rows in d['attempts']):fail('Height dimensions mismatch',code='INVALID_STATE')
    for p,rows in enumerate(d['attempts']):
        fails=0
        for h,row in enumerate(rows):
            if h>d['height'] and row:fail('Future height contains attempts',code='INVALID_STATE')
            for j,value in enumerate(row):
                if fails>=3 or j and row[j-1] in ('clear','pass'):fail('Attempt continued after elimination or completed height',code='INVALID_STATE')
                if value=='clear':fails=0
                elif value=='fail':fails+=1
            if h<d['height'] and d['status'][p]=='active' and fails<3 and (not row or row[-1] not in ('clear','pass')):fail('Earlier height was not completed',code='INVALID_STATE')
    if d['height']<n and done(d,int(d['turn']),int(d['height'])):fail('Current athlete must be eligible',code='INVALID_STATE')
    if d['height']==n and d['turn']!=0:fail('Completed qualification has no current athlete',code='INVALID_STATE')
def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];kind=action['type']
    if not d['configured']:
        if kind!='configure':fail('Supply the height schedule first')
        fields(p,dict(heights_mm=HEIGHTS,places=dict(type='integer',minimum=1,maximum=12)),'/params');d.update(configured=True,heights_mm=deepcopy(p['heights_mm']),places=p['places'],attempts=[[[] for _ in p['heights_mm']] for _ in range(12)]);return d
    if kind in ('withdraw','disqualify'):
        fields(p,dict(player=dict(type='integer',minimum=0,maximum=11)),'/params');t=int(p['player'])
        if d['status'][t]=='dq' or kind=='withdraw' and d['status'][t]!='active':fail('Athlete is already inactive')
        d['status'][t]='dq' if kind=='disqualify' else 'withdrawn';return advance(d)
    if kind!='attempt':fail('Unknown action')
    fields(p,dict(result=dict(type='string',enum=['clear','fail','pass'])),'/params');t=int(d['turn']);h=int(d['height'])
    if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
    d['attempts'][t][h].append(p['result']);d['turn']=(t+1)%12;return advance(d)
def legal(state):
    d=state['data']
    if not d['configured']:schemas=dict(configure=dict(heights_mm=HEIGHTS,places=dict(type='integer',minimum=1,maximum=12)));constraints={}
    else:
        schemas=dict(attempt=dict(result=dict(type='string',enum=['clear','fail','pass'])),withdraw=dict(player=dict(type='integer',minimum=0,maximum=11)),disqualify=dict(player=dict(type='integer',minimum=0,maximum=11)))
        constraints=dict(player=d['turn'],height_mm=d['heights_mm'][int(d['height'])],consecutive_failures=failures(d['attempts'][int(d['turn'])]))
    return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['The current athlete, height schedule and carried failure count must permit the action.'],external_observations=['Official clearance, failed attempt, voluntary height pass or administrative ruling.']) for k,v in schemas.items()],constraints=constraints,completeness=False,reason='externally_adjudicated_vertical_attempts')
def outcome(state,pack):
    d=state['data'];terminal=d['configured'] and d['height']==len(d['heights_mm'])
    eligible=sorted([(rank(d,p),p) for p in range(12) if d['status'][p]=='active' and rank(d,p)[0]>0],key=lambda x:(tuple(-v for v in x[0]),x[1])) if terminal else []
    cutoff=eligible[min(int(d['places']),len(eligible))-1][0] if eligible else None
    placements=[dict(player_id=state['players'][p]['id'],place=1+sum(other>k for other,_ in eligible),best_mm=k[0],attempts_at_best=-k[1],failures_through_best=-k[2],qualified=k[0]==d['heights_mm'][-1] or k>=cutoff) for k,p in eligible]
    winners=[state['players'][p]['id'] for k,p in eligible if k==eligible[0][0]] if eligible else []
    return dict(status='terminal' if terminal else 'ongoing',result_kind=('ranking' if eligible else 'no_contest') if terminal else 'none',winners=winners,losers=[state['players'][p]['id'] for k,p in eligible if k!=eligible[0][0]] if eligible else [],placements=placements,reason='qualification_completed' if terminal else 'ongoing' if d['configured'] else 'awaiting_configuration',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
