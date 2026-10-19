"""Ten-pin bowling: ten frames, bonus deliveries and deterministic scoring."""
from copy import deepcopy
from ..values import fields,fail
def finished(frame,index):
    if index<9:return len(frame)==2 or len(frame)==1 and frame[0]==10
    return len(frame)==3 or len(frame)==2 and sum(frame)<10
def maximum(frame,index):
    if not frame:return 10
    if index<9 or len(frame)==1:return 10-frame[0] if frame[0]!=10 else 10
    return 10-frame[1] if frame[0]==10 and frame[1]!=10 else 10
def scores(frames):
    result=[]
    for i,frame in enumerate(frames):
        if not finished(frame,i):result.append(None);continue
        later=[v for f in frames[i+1:] for v in f]
        if i==9:result.append(sum(frame))
        elif frame[0]==10:result.append(10+sum(later[:2]) if len(later)>=2 else None)
        elif sum(frame)==10:result.append(10+later[0] if later else None)
        else:result.append(sum(frame))
    return result
def validate(d):
    for p in range(2):
        for i,frame in enumerate(d['frames'][p]):
            index=i*2+p
            if index>d['current'] and frame:fail('Future frame contains deliveries',code='INVALID_STATE')
            for j,v in enumerate(frame):
                if finished(frame[:j],i) or v>maximum(frame[:j],i):fail('Delivery exceeds standing pins or frame limit',code='INVALID_STATE')
            if finished(frame,i)!=(index<d['current']):fail('Frame completion and turn mismatch',code='INVALID_STATE')
def apply(state,action):
    if action['type']!='roll':fail('Unknown action')
    fields(action['params'],dict(pins=dict(type='integer',minimum=0,maximum=10),foul=dict(type='boolean')),'/params')
    d=deepcopy(state['data']);p=int(d['current'])%2;i=int(d['current'])//2;frame=d['frames'][p][i];v=action['params']['pins']
    if action.get('actor') is not None and action['actor']!=state['players'][p]['id']:fail('Wrong actor')
    if action['params']['foul'] and v!=0:fail('A foul must score zero pins')
    if v>maximum(frame,i):fail('Delivery exceeds standing pins')
    frame.append(v)
    if finished(frame,i):d['current']+=1
    return d
def legal(state):
    d=state['data'];p=int(d['current'])%2;i=int(d['current'])//2;limit=maximum(d['frames'][p][i],i)
    return dict(mode='event_types',actions=[],action_types=[dict(type='roll',params_schema=dict(pins=dict(type='integer',minimum=0,maximum=limit),foul=dict(type='boolean')),preconditions=['A foul scores zero; the credited pinfall cannot exceed standing pins.'],external_observations=['Official credited pinfall and foul ruling; a dead ball is not a delivery.'])],constraints=dict(player=p,frame=i+1,standing_pins=limit),completeness=False,reason='externally_observed_delivery')
def outcome(state,pack):
    d=state['data'];terminal=d['current']==20;totals=[sum(v for v in scores(f) if v is not None) for f in d['frames']];winners=[state['players'][p]['id'] for p in range(2) if totals[p]==max(totals)] if terminal else []
    return dict(status='terminal' if terminal else 'ongoing',result_kind=('draw' if totals[0]==totals[1] else 'win') if terminal else 'none',winners=winners,losers=[p['id'] for p in state['players'] if p['id'] not in winners] if terminal else [],placements=[dict(player_id=state['players'][p]['id'],place=1+sum(v>totals[p] for v in totals),score=totals[p]) for p in range(2)] if terminal else [],reason='ten_frames_completed' if terminal else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if terminal else None)
