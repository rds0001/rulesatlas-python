"""Scratch stroke-play round with official penalties and returned scorecards."""
from copy import deepcopy
from ..values import fields,fail
I=lambda a,b,**kw:dict(type='integer',minimum=a,maximum=b,**kw)
PLAYER=I(0,3)
SCHEMAS=dict(start_hole=dict(player=PLAYER),stroke=dict(player=PLAYER),penalty=dict(player=PLAYER,hole=I(0,17),strokes=I(1,2)),hole_out=dict(player=PLAYER),correct_hole=dict(player=PLAYER,hole=I(0,17),strokes=I(1,1000)),return_card=dict(player=PLAYER,scores=dict(type='array',minItems=18,maxItems=18,items=I(1,1000,nullable=True)),certified=dict(type='boolean')),withdraw=dict(player=PLAYER),disqualify=dict(player=PLAYER),confirm_result={})
SCHEMAS['unknown_penalty']=dict(player=PLAYER,hole=I(0,17),strokes=I(1,2))
def settled(d):return all(r['status'] in ('returned','dns','dnf','dq') for r in d['golfers'])
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 for r in d['golfers']:
  status=r['status'];n=len(r['holes'])
  if status=='playing' and n>=18 or status=='ready' and n>=18 or status=='card' and n!=18:bad('Round phase and completed holes disagree')
  if status not in ('playing','dnf','dq') and r['current_strokes']!=0:bad('Strokes exist outside an active hole')
  if r['current_played'] and (r['current_strokes']==0 or status not in ('playing','dnf','dq')):bad('Played-stroke flag disagrees with active hole')
  if status=='dns' and (n or r['current_strokes']):bad('DNS golfer already played')
  if status=='returned' and (n!=18 or r['card'] is None or any(x is None for x in r['card']) or any(a>b for a,b in zip(r['holes'],r['card']))):bad('Returned scorecard understates or omits a completed hole')
  if r['card'] is not None and status not in ('returned','dq'):bad('Scorecard exists before return')
  if r['card'] is not None and n!=18:bad('Only completed rounds may return cards')
  if (status=='dq')!=(r['disqualification_reason'] is not None):bad('Disqualification reason mismatch')
 if (d['phase'] in ('review','finished'))!=settled(d):bad('All golfers must resolve their rounds and scorecards before review')
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params']
 if k not in SCHEMAS:fail('Unknown golf action')
 fields(p,SCHEMAS[k],'/params')
 if k=='confirm_result':
  if d['phase']!='review':fail('Every round and scorecard must be resolved first')
  d['phase']='finished';return d
 r=d['golfers'][p['player']];status=r['status']
 if k=='start_hole':
  if status!='ready':fail('This golfer cannot start another hole')
  r['status']='playing'
 elif k=='stroke':
  if status!='playing' or r['current_strokes']>=1000:fail('Stroke requires an active hole within the supported score bound')
  r['current_strokes']+=1;r['current_played']=True
 elif k=='penalty':
  h=p['hole'];n=len(r['holes'])
  if status not in ('ready','playing','card') or h>n or h==n and status!='playing':fail('Apply an official penalty to a started hole before card return')
  if h==n:r['current_strokes']+=p['strokes']
  else:r['holes'][h]+=p['strokes']
  if max(r['holes']+[r['current_strokes']])>1000:fail('Hole score exceeds the supported bound')
 elif k=='unknown_penalty':
  if status!='returned':fail('The unknown-penalty exception requires a returned certified card')
  h=p['hole'];r['holes'][h]+=p['strokes'];r['card'][h]+=p['strokes']
  if max(r['holes']+r['card'])>1000:fail('Hole score exceeds the supported bound')
 elif k=='hole_out':
  if status!='playing' or not r['current_played']:fail('Holing out requires a played stroke')
  r['holes'].append(r['current_strokes']);r['current_strokes']=0;r['current_played']=False;r['status']='card' if len(r['holes'])==18 else 'ready'
 elif k=='correct_hole':
  if status not in ('ready','playing','card') or p['hole']>=len(r['holes']):fail('Correct a completed hole before returning the card')
  r['holes'][p['hole']]=p['strokes']
 elif k=='return_card':
  if status!='card':fail('Complete all eighteen holes before returning the card')
  r['card']=deepcopy(p['scores'])
  reason='uncertified_card' if not p['certified'] else 'missing_hole' if any(x is None for x in p['scores']) else 'understated_hole' if any(a>b for a,b in zip(r['holes'],p['scores'])) else None
  r['status']='dq' if reason else 'returned';r['disqualification_reason']=reason
 elif k=='withdraw':
  if status not in ('ready','playing','card'):fail('Only an unfinished or unreturned round can be withdrawn')
  r['status']='dns' if status=='ready' and not r['holes'] else 'dnf'
 elif k=='disqualify':
  if status=='dq':fail('Golfer is already disqualified')
  r['status']='dq';r['disqualification_reason']='official_ruling'
 d['phase']='review' if settled(d) else 'round';return d
def legal(state):
 d=state['data'];s={k:v for k,v in SCHEMAS.items() if k!='confirm_result'} if d['phase']=='round' else dict(disqualify=SCHEMAS['disqualify'],unknown_penalty=SCHEMAS['unknown_penalty'],confirm_result={}) if d['phase']=='review' else {}
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['Golfer phase, hole completion and scorecard return must permit this event.'],external_observations=['Played strokes, official one- or two-stroke penalties, holed balls and certified cards.']) for k,v in s.items()],constraints=dict(phase=d['phase'],next_holes=[len(r['holes']) if len(r['holes'])<18 else None for r in d['golfers']],target_holes=18),completeness=False,reason='official_scratch_stroke_play')
def outcome(state,pack):
 d=state['data'];t=d['phase']=='finished';ranked=sorted((sum(r['card']),i) for i,r in enumerate(d['golfers']) if r['status']=='returned') if t else [];winners=[state['players'][i]['id'] for s,i in ranked if s==ranked[0][0]] if ranked else []
 return dict(status='terminal' if t else 'awaiting_adjudication' if d['phase']=='review' else 'ongoing',result_kind=('ranking' if ranked else 'no_contest') if t else 'none',winners=winners,losers=[p['id'] for p in state['players'] if p['id'] not in winners] if winners else [],placements=[dict(player_id=state['players'][i]['id'],place=1+sum(other<s for other,_ in ranked),strokes=s) for s,i in ranked],reason='round_confirmed' if t else 'scorecard_review' if d['phase']=='review' else 'ongoing',evidence_required=['Official scorecard confirmation.'] if d['phase']=='review' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if t else None)
