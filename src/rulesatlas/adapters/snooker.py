"""Fifteen-red snooker frame from adjudicated pots, fouls and miss decisions."""
from copy import deepcopy
from ..values import fields,fail
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
B=dict(type='boolean')
SCHEMAS=dict(start=dict(player=I(0,1)),nominate_colour=dict(value=I(2,7)),nominate_free_ball=dict(value=I(2,7)),stroke=dict(reds=I(0,15),on_potted=B,free_potted=B),foul=dict(points=I(4,7),reds_removed=I(0,15),miss=B,full_ball_available=B,free_ball_available=B),choose_after_foul=dict(choice=dict(type='string',enum=['play','return','replace'])),choose_black_start=dict(player=I(0,1)),concede=dict(player=I(0,1)))
def on_value(d):return 1 if d['stage']=='reds' else d['nominated'] if d['stage']=='colour' else d['clearance']
def finish(d,w,reason):d.update(phase='finished',winner=w,reason=reason,free_ball=False,free_nomination=None,miss_count=0,pending=None,nominated=None)
def settle_black(d):
 if d['scores'][0]==d['scores'][1]:d.update(phase='black_toss',stage='black_tie',clearance=7,nominated=None,free_ball=False,free_nomination=None,pending=None,miss_count=0)
 else:finish(d,0 if d['scores'][0]>d['scores'][1] else 1,'points')
def reset_rights(d):d.update(free_ball=False,free_nomination=None,nominated=None,miss_count=0)
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 if d['stage']=='reds' and d['reds']==0 or d['stage'] in ('clearance','black_tie') and d['reds']!=0:bad('Ball-on stage must agree with remaining reds')
 if d['stage']!='colour' and d['nominated'] is not None:bad('Colour nomination is only needed after a red')
 if d['free_nomination'] is not None and (not d['free_ball'] or d['stage']=='colour' or d['stage']!='reds' and d['free_nomination']<=on_value(d)):bad('Free ball must differ from the ball on and require an entitlement')
 if d['free_ball'] and d['stage']=='colour':bad('The post-red colour cannot carry a free-ball entitlement')
 if d['phase']=='ready' and (d['scores']!=[0,0] or d['reds']!=15 or d['stage']!='reds' or d['free_ball'] or d['miss_count'] or d['pending'] is not None):bad('Unstarted frame must have its complete unscored rack')
 if (d['phase']=='choice')!=(d['pending'] is not None):bad('Only foul choice retains a replacement record')
 if d['pending'] is not None:
  r=d['pending']
  if r['offender']==d['turn'] or r['full_ball'] and not r['miss'] or r['old_stage']=='reds' and r['old_reds']==0:bad('Foul choice requires the opponent and a coherent miss record')
 if d['phase']=='black_toss' and (d['stage']!='black_tie' or d['scores'][0]!=d['scores'][1]):bad('Respotted black requires a tied completed frame')
 if d['stage']=='black_tie' and d['clearance']!=7:bad('Respotted-black stage has only the black on')
 if d['phase']=='finished':
  if d['winner'] is None or d['reason'] is None:bad('Finished frame requires a winner and reason')
  if d['reason']=='points' and (d['reds'] or d['clearance']!=7 or d['stage'] not in ('clearance','black_tie') or d['scores'][d['winner']]<=d['scores'][1-d['winner']]):bad('Points victory follows the final black with unequal scores')
 elif d['winner'] is not None or d['reason'] is not None:bad('Open frame cannot retain a winner')

def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params']
 if k not in SCHEMAS:fail('Unknown snooker event')
 fields(p,SCHEMAS[k],'/params')
 if d['phase']=='finished':fail('Frame is finished')
 if k=='concede':finish(d,1-p['player'],'concession');return d
 if k=='start':
  if d['phase']!='ready':fail('Frame already started')
  d.update(phase='turn',turn=p['player']);return d
 if k=='choose_black_start':
  if d['phase']!='black_toss':fail('No respotted-black toss is due')
  d.update(phase='turn',turn=p['player']);return d
 if k=='choose_after_foul':
  if d['phase']!='choice':fail('No foul choice is pending')
  r=d['pending'];choice=p['choice'];reset_rights(d)
  if choice=='replace':
   if not r['miss']:fail('Replacement requires an official foul-and-miss call')
   d.update(turn=r['offender'],reds=r['old_reds'],stage=r['old_stage'],clearance=r['old_clearance'],nominated=r['old_nomination'],miss_count=r['sequence'] if r['full_ball'] else 0,free_ball=r['old_free_ball'],free_nomination=r['old_free_nomination'])
  elif choice=='return':d['turn']=r['offender']
  else:d['free_ball']=r['free_ball']
  d.update(phase='turn',pending=None);return d
 if d['phase']!='turn':fail('A stroke requires an open visit')
 if k=='nominate_colour':
  if d['stage']!='colour':fail('Choose a colour only after scoring a red')
  d['nominated']=p['value'];return d
 if k=='nominate_free_ball':
  if not d['free_ball'] or d['stage']=='colour' or d['stage']!='reds' and p['value']<=on_value(d):fail('A free-ball nomination must differ from the ball on')
  d['free_nomination']=p['value'];return d
 value=on_value(d)
 if value is None:fail('Nominate the post-red colour before adjudicating a stroke')
 if k=='stroke':
  if p['reds']>d['reds'] or p['free_potted'] and d['free_nomination'] is None:fail('Pots exceed the remaining balls or free-ball entitlement')
  oldstage=d['stage'];points=0
  if oldstage=='reds':
   if p['on_potted']:fail('Red pots use their explicit count')
   points=p['reds']+int(p['free_potted']);d['reds']-=p['reds']
   if points:d['stage']='colour'
  else:
   if p['reds']:fail('Reds cannot be legally potted while a colour is on')
   points=value if p['on_potted'] or p['free_potted'] else 0
   if points:
    if oldstage=='colour':d['stage']='reds' if d['reds'] else 'clearance';d['clearance']=2
    elif p['on_potted'] and value<7:d['clearance']+=1
  d['scores'][d['turn']]+=points;reset_rights(d)
  if oldstage in ('clearance','black_tie') and value==7 and p['on_potted']:settle_black(d)
  elif not points:d['turn']=1-d['turn'];d['stage']='reds' if d['reds'] else 'clearance' if oldstage=='colour' else d['stage']
  return d
 if k=='foul':
  if p['points']<max(4,value) or p['reds_removed']>d['reds'] or p['full_ball_available'] and not p['miss']:fail('Foul points and miss context must agree with the ball on and available reds')
  offender=d['turn'];sequence=d['miss_count']+1 if p['miss'] and p['full_ball_available'] else 0
  r=dict(offender=offender,old_reds=d['reds'],old_stage=d['stage'],old_clearance=d['clearance'],old_nomination=d['nominated'],old_free_ball=d['free_ball'],old_free_nomination=d['free_nomination'],miss=p['miss'],full_ball=p['full_ball_available'],sequence=sequence,free_ball=p['free_ball_available'])
  d['scores'][1-offender]+=p['points'];d['reds']-=p['reds_removed'];reset_rights(d)
  if d['stage'] in ('clearance','black_tie') and value==7:settle_black(d);return d
  if sequence>=3:finish(d,1-offender,'three_misses');return d
  if d['stage']=='colour' or d['stage']=='reds' and d['reds']==0:d['stage']='reds' if d['reds'] else 'clearance';d['clearance']=2
  d.update(phase='choice',turn=1-offender,pending=r);return d
 fail('Unknown snooker event')

def legal(state):
 d=state['data'];phase=d['phase'];names=[]
 if phase=='ready':names=['start']
 elif phase=='black_toss':names=['choose_black_start']
 elif phase=='choice':names=['choose_after_foul']
 elif phase=='turn':
  if d['stage']=='colour':names+=['nominate_colour']
  if d['free_ball']:names+=['nominate_free_ball']
  if on_value(d) is not None:names+=['stroke','foul']
 if phase!='finished':names+=['concede']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=SCHEMAS[k],preconditions=['Ball-on sequence, nomination, available reds and pending referee decision must permit the event.'],external_observations=['Legal pots, foul value, miss and free-ball rulings; no ball coordinates.']) for k in names],constraints=dict(phase=phase,player=d['turn'],ball_on=on_value(d),reds_remaining=d['reds'],free_ball=d['free_ball'],miss_warning=d['miss_count']==2),completeness=False,reason='official_snooker_strokes')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';w=d['winner']
 return dict(status='terminal' if done else 'ongoing',result_kind='win' if done else 'none',winners=[state['players'][w]['id']] if done else [],losers=[state['players'][1-w]['id']] if done else [],placements=[],reason=d['reason'] if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
