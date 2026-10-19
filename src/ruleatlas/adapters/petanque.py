"""Singles petanque to thirteen; official distances replace physical trajectories."""
from copy import deepcopy
from ..values import fields,fail
DIST=dict(type='integer',minimum=0,maximum=100000,nullable=True)
def remaining(d,p):return 3-sum(d['thrown'][p*3:p*3+3])
def nearest(d,p):return min([x for x in d['distances_mm'][p*3:p*3+3] if x is not None],default=None)
def tied(d):return nearest(d,0)==nearest(d,1)
def end_points(d,dead=False):
    if dead:
        rem=[remaining(d,p) for p in (0,1)]
        return rem if (rem[0]==0)!=(rem[1]==0) else [0,0]
    best=[nearest(d,p) for p in (0,1)]
    if best[0]==best[1]:return [0,0]
    winner=1 if best[0] is None else 0 if best[1] is None or best[0]<best[1] else 1
    limit=best[1-winner];points=sum(x is not None and (limit is None or x<limit) for x in d['distances_mm'][winner*3:winner*3+3]);out=[0,0];out[winner]=points;return out

def finish_end(d,points):
    d['scores']=[d['scores'][p]+points[p] for p in (0,1)];d['last_end']=points
    if max(d['scores'])>=13:d['phase']='finished';return d
    if points[0]!=points[1]:d['jack_player']=0 if points[0]>points[1] else 1
    d['turn']=d['jack_player'];d['phase']='jack_throw';d['thrown']=[False]*6;d['distances_mm']=[None]*6;d['end_number']+=1;d['tie_active']=False;return d

def validate(d):
    if any(x is not None and not d['thrown'][i] for i,x in enumerate(d['distances_mm'])):fail('Only thrown boules may have measured distances',code='INVALID_STATE')
    if d['phase'] in ('jack_throw','jack_place'):
        if any(d['thrown']) or any(x is not None for x in d['distances_mm']):fail('A new jack requires cleared boule state',code='INVALID_STATE')
        expected=d['jack_player'] if d['phase']=='jack_throw' else 1-d['jack_player']
        if d['turn']!=expected:fail('Jack throw or placement belongs to the designated player',code='INVALID_STATE')
    if d['tie_active'] and (d['phase'] not in ('boules','finished') or not tied(d) or not any(d['thrown'])):fail('Tie alternation requires an unresolved distance tie after play',code='INVALID_STATE')
    if d['phase']=='boules':
        if remaining(d,int(d['turn']))==0:fail('Next player must have a boule remaining',code='INVALID_STATE')
        if not any(d['thrown']) and d['turn']!=d['jack_player']:fail('The jack thrower plays the first boule even after an opponent places the jack',code='INVALID_STATE')
        best=[nearest(d,p) for p in (0,1)]
        if best[0]!=best[1]:
            trailing=0 if best[0] is None else 1 if best[1] is None or best[0]<best[1] else 0
            if remaining(d,trailing)>0 and d['turn']!=trailing:fail('The player without the nearest boule must play while having boules',code='INVALID_STATE')
    if (d['phase']=='finished')!=(max(d['scores'])>=13):fail('First to thirteen ends the game',code='INVALID_STATE')
    if min(d['scores'])>=13:fail('Both players cannot reach thirteen in one end',code='INVALID_STATE')
    if sum(d['last_end'])>3 or (d['last_end'][0] and d['last_end'][1]) or any(d['last_end'][p]>d['scores'][p] for p in (0,1)):fail('Invalid previous end award',code='INVALID_STATE')

def apply(state,action):
    d=deepcopy(state['data']);p=action['params'];k=action['type'];t=int(d['turn'])
    if action.get('actor') is not None and action['actor']!=state['players'][t]['id']:fail('Wrong actor')
    if k in ('throw_jack','place_jack'):
        fields(p,dict(distance_mm=dict(type='integer',minimum=0,maximum=100000),clearances_valid=dict(type='boolean')),'/params')
        if d['phase']!=('jack_throw' if k=='throw_jack' else 'jack_place'):fail('Jack action is not available in this phase')
        valid=6000<=p['distance_mm']<=10000 and p['clearances_valid']
        if k=='place_jack' and not valid:fail('The placed jack must satisfy distance and official clearances')
        if valid:d['phase']='boules';d['turn']=d['jack_player']
        else:d['phase']='jack_place';d['turn']=1-d['jack_player']
        return d
    if k!='throw':fail('Unknown action')
    fields(p,dict(boule=dict(type='integer',minimum=0,maximum=5),distances_mm=dict(type='array',minItems=6,maxItems=6,items=DIST),jack_dead=dict(type='boolean')),'/params');i=int(p['boule'])
    if d['phase']!='boules' or i//3!=t or d['thrown'][i]:fail('Throw one unused boule belonging to the current player')
    oldtie=d['tie_active'];d['thrown'][i]=True
    for j,x in enumerate(p['distances_mm']):
        if x is not None and (not d['thrown'][j] or (j!=i and d['distances_mm'][j] is None)):fail('Unthrown or already dead boules cannot acquire a distance')
    d['distances_mm']=p['distances_mm'][:];d['tie_active']=tied(d)
    if p['jack_dead']:
        if any(x is not None for x in d['distances_mm']):fail('A dead jack has no active distance measurements')
        return finish_end(d,end_points(d,True))
    if not any(remaining(d,p) for p in (0,1)):return finish_end(d,end_points(d))
    if remaining(d,0)==0:d['turn']=1
    elif remaining(d,1)==0:d['turn']=0
    elif tied(d):d['turn']=1-t if oldtie else t
    else:d['turn']=0 if nearest(d,0) is None else 1 if nearest(d,1) is None or nearest(d,0)<nearest(d,1) else 0
    return d

def legal(state):
    d=state['data']
    if d['phase'] in ('jack_throw','jack_place'):
        types=[dict(type='throw_jack' if d['phase']=='jack_throw' else 'place_jack',params_schema=dict(distance_mm=dict(type='integer',minimum=0,maximum=100000),clearances_valid=dict(type='boolean')),preconditions=['A valid jack is six through ten metres from the circle and satisfies official clearances. Only one thrown attempt; opponent places after failure.'],external_observations=['Measured jack distance and official clearance judgment.'])]
    else:types=[dict(type='throw',params_schema=dict(boule=dict(type='integer',minimum=0,maximum=5),distances_mm=dict(type='array',minItems=6,maxItems=6,items=DIST),jack_dead=dict(type='boolean')),preconditions=['Unused owned boule; supply the official new distance of every live thrown boule. Null marks unthrown or dead boules. A dead jack requires all-null distances.'],external_observations=['Official post-throw distances, dead-boule and dead-jack decisions.'])]
    return dict(mode='event_types',actions=[],action_types=types,constraints=dict(turn=d['turn'],remaining=[remaining(d,p) for p in (0,1)],end_number=d['end_number']),completeness=False,reason='official_distances_without_throw_simulation')
def outcome(state,pack):
    d=state['data'];done=d['phase']=='finished';w=0 if d['scores'][0]>=13 else 1
    return dict(status='terminal' if done else 'ongoing',result_kind='win' if done else 'none',winners=[state['players'][w]['id']] if done else [],losers=[state['players'][1-w]['id']] if done else [],placements=[dict(player_id=state['players'][p]['id'],place=1 if p==w else 2,score=d['scores'][p]) for p in (0,1)] if done else [],reason='thirteen_points' if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
