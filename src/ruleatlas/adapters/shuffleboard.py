"""Longboard table shuffleboard, four pucks each and a twenty-one point game."""
from copy import deepcopy
from ..values import fields,fail
I=lambda a,b,**kw:dict(type='integer',minimum=a,maximum=b,**kw)
PUCK=dict(type='object',properties=dict(status=dict(type='enum',values=['unplayed','live','dead']),zone=I(1,4,nullable=True),order=I(1,8,nullable=True)),required=['status','zone','order'])
BOARD=dict(type='array',minItems=8,maxItems=8,items=PUCK)
SCHEMAS=dict(choose_first=dict(team=I(0,1)),shoot=dict(pucks=BOARD),correct_board=dict(pucks=BOARD),confirm_frame={},concede=dict(team=I(0,1)))
def blank():return [dict(status='unplayed',zone=None,order=None) for _ in range(8)]
def next_puck(d):return (d['first_team']+d['shots'])%2*4+d['shots']//2 if d['first_team'] is not None and d['shots']<8 else None
def board_valid(board,played):
 for j,p in enumerate(board):
  if (p['status']=='unplayed')!=(j not in played) or (p['status']=='live')!=(p['zone'] is not None and p['order'] is not None) or p['status']!='live' and (p['zone'] is not None or p['order'] is not None):return False
 live=[p for p in board if p['status']=='live']
 return all(not(a['zone']>b['zone'] and a['order']>=b['order']) for a in live for b in live)
def played_ids(first,shots):return {(first+j)%2*4+j//2 for j in range(shots)}
def frame_score(d):
 best=[min((p['order'] for p in d['pucks'][t*4:t*4+4] if p['status']=='live'),default=9) for t in range(2)]
 if best[0]==best[1]:return [0,0]
 w=0 if best[0]<best[1] else 1;s=[0,0];s[w]=sum(p['zone'] for p in d['pucks'][w*4:w*4+4] if p['status']=='live' and p['order']<best[1-w]);return s
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 if d['phase']=='setup':
  if d['first_team'] is not None or d['shots'] or any(d['scores']) or d['frame']!=1:bad('Invalid unstarted game')
 elif d['first_team'] is None:bad('Started game requires its first shooter')
 if not board_valid(d['pucks'],played_ids(d['first_team'] or 0,d['shots'])):bad('Puck status, order or scoring zone is inconsistent')
 if d['phase']=='shooting' and d['shots']>=8 or d['phase']=='review' and d['shots']!=8:bad('Frame phase and shot count mismatch')
 if d['phase']=='finished':
  if d['winner'] is None or d['reason'] is None:bad('Terminal game needs its result')
  if d['reason']=='target' and (d['scores'][d['winner']]<21 or d['scores'][1-d['winner']]>=21 or d['shots']!=8):bad('Invalid target-score victory')
 elif d['winner'] is not None or d['reason'] is not None or max(d['scores'])>=21:bad('Unresolved or premature result')
def available(d):
 if d['phase']=='setup':return ['choose_first']
 if d['phase']=='shooting':return ['shoot','concede']
 if d['phase']=='review':return ['correct_board','confirm_frame','concede']
 return []
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params']
 if k not in available(d):fail('Action is not permitted in this phase')
 fields(p,SCHEMAS[k],'/params')
 if k=='choose_first':d['first_team']=p['team'];d['phase']='shooting'
 elif k in ('shoot','correct_board'):
  shots=d['shots']+(k=='shoot');new=p['pucks']
  if not board_valid(new,played_ids(d['first_team'],shots)):fail('Board must contain exactly the delivered pucks with consistent official ranks and zones')
  if k=='shoot' and any(old['status']=='dead' and new[j]['status']!='dead' for j,old in enumerate(d['pucks'])):fail('A removed puck cannot return on a later shot')
  d['pucks']=deepcopy(new);d['shots']=shots;d['phase']='review' if shots==8 else 'shooting'
 elif k=='confirm_frame':
  gains=frame_score(d);d['scores']=[a+b for a,b in zip(d['scores'],gains)]
  if max(d['scores'])>=21:d.update(phase='finished',winner=0 if d['scores'][0]>=21 else 1,reason='target')
  else:
   if any(gains):d['first_team']=0 if gains[0] else 1
   d['frame']+=1;d['shots']=0;d['pucks']=blank();d['phase']='shooting'
 elif k=='concede':d.update(phase='finished',winner=1-p['team'],reason='concede')
 return d
def legal(state):
 d=state['data']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=SCHEMAS[k],preconditions=['Alternate four pucks per team; only official settled boards may be recorded.'],external_observations=['Official live/dead puck rulings, scoring zones and distance order.']) for k in available(d)],constraints=dict(phase=d['phase'],next_puck=next_puck(d),frame=d['frame'],provisional_frame_points=frame_score(d) if d['phase']=='review' else None),completeness=False,reason='official_table_shuffleboard_positions')
def outcome(state,pack):
 d=state['data'];t=d['phase']=='finished';w=d['winner']
 return dict(status='terminal' if t else 'awaiting_adjudication' if d['phase']=='review' else 'ongoing',result_kind=('forfeit' if d['reason']=='concede' else 'win') if t else 'none',winners=[state['players'][w]['id']] if t else [],losers=[state['players'][1-w]['id']] if t else [],placements=[],reason=d['reason'] if t else 'frame_review' if d['phase']=='review' else 'ongoing',evidence_required=['Official settled-board confirmation.'] if d['phase']=='review' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if t else None)
