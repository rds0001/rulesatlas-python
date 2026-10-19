"""Official-event kendo bout, without movement or strike recognition."""
from copy import deepcopy
from ..values import fields, fail
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
A=lambda item:dict(type='array',minItems=2,maxItems=2,items=item)
RECORD=dict(points=A(I(0,2)),hansoku=A(I(0,1)),remaining_ms=I(0,300000))
SCHEMAS=dict(start={},resume={},pause={},elapse=dict(milliseconds=I(1,300000)),ippon=dict(player=I(0,1),target=dict(type='string',enum=['men','kote','do','tsuki'])),hansoku=dict(offenders=A(dict(type='boolean'))),correct_record=RECORD,begin_encho={},hantei=dict(votes=dict(type='array',minItems=3,maxItems=3,items=I(0,1))),forfeit=dict(player=I(0,1)),disqualify=dict(player=I(0,1)),both_disqualified={},confirm={})
def settle(d):
    d['winner']=None;d['reason']=None
    a,b=d['points']
    if max(a,b)==2 or (d['encho'] or d['remaining_ms']==0) and a!=b:
        d['winner']=0 if a>b else 1;d['reason']='points';d['phase']='review'
    elif d['remaining_ms']==0:d['phase']='decision' if d['encho'] else 'interval'
    else:d['phase']='paused'
def validate(d):
    bad=lambda message:fail(message,code='INVALID_STATE')
    terminal=d['phase'] in ('review','finished')
    if terminal!=(d['reason'] is not None):bad('Result phase mismatch')
    if d['remaining_ms']>(180000 if d['encho'] else 300000):bad('Clock exceeds period')
    if d['encho'] and d['phase']=='ready':bad('Overtime cannot be unstarted')
    if d['phase']=='ready' and (d['points']!=[0,0] or d['hansoku']!=[0,0] or d['remaining_ms']!=300000):bad('Invalid unstarted bout')
    if d['phase'] in ('interval','decision') and (d['remaining_ms'] or d['points'][0]!=d['points'][1] or (d['phase']=='decision')!=d['encho']):bad('Invalid period boundary')
    if not terminal:
        if d['winner'] is not None or max(d['points'])>=2:bad('Unresolved winning score')
        if d['phase'] in ('active','paused') and (not d['remaining_ms'] or d['encho'] and d['points'][0]!=d['points'][1]):bad('Invalid live period')
    elif d['reason']=='both_disqualified':
        if d['winner'] is not None or d['points']!=[0,0]:bad('Invalid double disqualification')
    else:
        w=d['winner']
        if w is None or d['points'][w]<=d['points'][1-w]:bad('Winner must lead')
        if d['reason']=='points' and not(max(d['points'])==2 or d['encho'] or d['remaining_ms']==0):bad('Premature points victory')
        if d['reason']=='disqualify' and d['points']!=([2,0] if w==0 else [0,2]):bad('Invalid disqualification score')
        if d['reason']=='hantei' and (not d['encho'] or d['remaining_ms']):bad('Premature hantei')
def available(d):
    phase=d['phase'];names=[]
    if phase=='ready':names=['start']
    elif phase=='active':names=['pause','elapse','ippon','hansoku']
    elif phase=='paused':names=['resume','hansoku','correct_record']
    elif phase=='interval':names=['begin_encho','correct_record']
    elif phase=='decision':names=['hantei','correct_record']
    elif phase=='review':names=['confirm']+(['correct_record'] if d['reason']=='points' else [])
    if phase not in ('review','finished'):names+=['forfeit','disqualify','both_disqualified']
    return names
def apply(state,action):
    d=deepcopy(state['data']);k=action['type'];p=action['params']
    if k not in available(d):fail('Action is not permitted in this phase')
    fields(p,SCHEMAS[k],'/params')
    if k in ('start','resume'):d['phase']='active'
    elif k=='pause':d['phase']='paused'
    elif k=='elapse':
        if p['milliseconds']>d['remaining_ms']:fail('Elapsed time crosses a period boundary')
        d['remaining_ms']-=p['milliseconds']
        if not d['remaining_ms']:settle(d)
    elif k=='ippon':d['points'][p['player']]+=1;settle(d)
    elif k=='hansoku':
        o=p['offenders']
        if not any(o):fail('At least one offender is required')
        if not(o==[True,True] and d['points']==[1,1] and d['hansoku']==[1,1]):
            for i in range(2):
                if o[i]:
                    d['hansoku'][i]+=1
                    if d['hansoku'][i]==2:d['hansoku'][i]=0;d['points'][1-i]+=1
        settle(d)
    elif k=='correct_record':
        d.update(deepcopy(p));settle(d);validate(d)
    elif k=='begin_encho':d['encho']=True;d['remaining_ms']=180000;d['phase']='paused'
    elif k=='hantei':
        w=1 if sum(p['votes'])>=2 else 0;d['points'][w]+=1;d.update(winner=w,reason=k,phase='review')
    elif k in ('forfeit','disqualify'):
        w=1-p['player'];d['points'][w]=d['points'][w]+1 if d['encho'] and k=='forfeit' else 2
        if k=='disqualify':d['points'][1-w]=0
        d.update(winner=w,reason=k,phase='review')
    elif k=='both_disqualified':d.update(points=[0,0],winner=None,reason=k,phase='review')
    elif k=='confirm':d['phase']='finished'
    return d
def legal(state):
    d=state['data']
    return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=SCHEMAS[k],preconditions=['Official decisions only; clock updates may not cross a period boundary.'],external_observations=['Final referee decisions and measured active time.']) for k in available(d)],constraints=dict(phase=d['phase'],remaining_ms=d['remaining_ms'],encho=d['encho']),completeness=False,reason='externally_adjudicated_bout')
def outcome(state,pack):
    d=state['data'];t=d['phase']=='finished';w=d['winner'];reason=d['reason'] if t else 'awaiting_confirmation' if d['phase']=='review' else 'ongoing'
    return dict(status='terminal' if t else 'ongoing',result_kind=('no_contest' if w is None else 'disqualification' if reason=='disqualify' else 'forfeit' if reason=='forfeit' else 'win') if t else 'none',winners=[state['players'][w]['id']] if t and w is not None else [],losers=([p['id'] for p in state['players']] if w is None else [state['players'][1-w]['id']]) if t else [],placements=[],reason=reason,evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if t else None)
