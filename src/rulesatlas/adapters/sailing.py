"""Five-race low-point sailing series with one discard and official redress."""
from copy import deepcopy
from ..values import fields,fail
I=lambda a,b,**kw:dict(type='integer',minimum=a,maximum=b,**kw)
ENTRY=dict(type='object',properties=dict(status=dict(type='enum',values=['finished','dns','dnf','ret','ocs','ufd','bfd','dsq','dnc','dne','redress']),order=I(1,8,nullable=True),redress_numerator=I(1,500,nullable=True),redress_denominator=I(1,5,nullable=True)),required=['status','order','redress_numerator','redress_denominator'])
RESULT=dict(type='array',minItems=8,maxItems=8,items=ENTRY)
SCHEMAS=dict(start_race={},abandon_race={},submit_result=dict(results=RESULT),amend_result=dict(results=RESULT),confirm_race={})
def valid_result(row):
 for r in row:
  if r['status']=='finished' and r['order'] is None or r['status'] not in ('finished','redress') and r['order'] is not None:return False
  red=r['status']=='redress'
  if red!=(r['redress_numerator'] is not None and r['redress_denominator'] is not None):return False
  if not red and (r['redress_numerator'] is not None or r['redress_denominator'] is not None):return False
  if red and r['redress_numerator']<r['redress_denominator']:return False
 return True
def points(row):
 result=[]
 for r in row:
  if r['status']=='finished':
   before=sum(x['status'] in ('finished','redress') and x['order'] is not None and x['order']<r['order'] for x in row);tied=sum(x['status'] in ('finished','redress') and x['order'] is not None and x['order']==r['order'] for x in row)
   result.append((2*before+tied+1)*30)
  elif r['status']=='redress':result.append(r['redress_numerator']*(60//r['redress_denominator']))
  else:result.append(540)
 return result
def key(d,i):
 scores=[points(row)[i] for row in d['races']];eligible=[j for j,row in enumerate(d['races']) if row[i]['status']!='dne'];discard=max(eligible,key=lambda j:(scores[j],-j)) if eligible else None
 kept=[s for j,s in enumerate(scores) if j!=discard]
 return [sum(kept)]+sorted(kept)+[1000000]+scores[::-1],discard,scores
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 if any(not valid_result(row) for row in d['races']) or d['pending'] is not None and not valid_result(d['pending']):bad('Official result fields are inconsistent')
 if (d['phase']=='review')!=(d['pending'] is not None):bad('Pending race result requires review')
 if (d['phase']=='finished')!=(len(d['races'])==5):bad('The series ends after five confirmed races')
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params']
 allowed={'ready':['start_race'],'racing':['abandon_race','submit_result'],'review':['abandon_race','amend_result','confirm_race']}.get(d['phase'],[])
 if k not in allowed:fail('Action is not permitted in this race phase')
 fields(p,SCHEMAS[k],'/params')
 if k=='start_race':d['phase']='racing'
 elif k=='abandon_race':d.update(phase='ready',pending=None)
 elif k in ('submit_result','amend_result'):
  if not valid_result(p['results']):fail('Finishers require order; redress may retain an occupied finish place and requires an explicit rational score')
  d['pending']=deepcopy(p['results']);d['phase']='review'
 elif k=='confirm_race':
  d['races'].append(d['pending']);d['pending']=None;d['phase']='finished' if len(d['races'])==5 else 'ready'
 return d
def legal(state):
 d=state['data'];names={'ready':['start_race'],'racing':['abandon_race','submit_result'],'review':['abandon_race','amend_result','confirm_race']}.get(d['phase'],[])
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=SCHEMAS[k],preconditions=['A race must start, receive an official result and pass review before counting.'],external_observations=['Official finish order, exclusions, abandonment and redress decisions.']) for k in names],constraints=dict(phase=d['phase'],confirmed_races=len(d['races']),score_unit_denominator=60,provisional_points_units=points(d['pending']) if d['pending'] is not None else None),completeness=False,reason='official_low_point_series')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';ranked=sorted((key(d,i)[0],i) for i in range(8)) if done else [];winners=[state['players'][i]['id'] for k,i in ranked if k==ranked[0][0]] if ranked else []
 return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='review' else 'ongoing',result_kind='ranking' if done else 'none',winners=winners,losers=[p['id'] for p in state['players'] if p['id'] not in winners] if done else [],placements=[dict(player_id=state['players'][i]['id'],place=1+sum(other<k for other,_ in ranked),points_units=k[0],score_unit_denominator=60,discarded_race=key(d,i)[1]) for k,i in ranked],reason='series_confirmed' if done else 'race_review' if d['phase']=='review' else 'ongoing',evidence_required=['Official race confirmation.'] if d['phase']=='review' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
