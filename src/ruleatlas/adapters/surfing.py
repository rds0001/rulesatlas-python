"""Four-surfer priority heat with wave panels and adjudicated interference."""
from copy import deepcopy
from ..values import fields,fail
SURFER=dict(type='integer',minimum=0,maximum=3)
WAVE=dict(type='integer',minimum=0,maximum=39)
MARKS=dict(type='array',minItems=5,maxItems=5,items=dict(type='integer',minimum=0,maximum=1000))
def pending(d,i):return bool(d['waves'][i] and d['waves'][i][-1] is None)
def disqualified(d,i):return d['status'][i]=='dq' or sum(p['kind']=='priority' for p in d['interferences'][i])==2
def can_surf(d,i):return d['status'][i]=='eligible' and len(d['interferences'][i])<2 and len(d['waves'][i])<d['wave_limit']+d['extra_waves'][i]
def settle(d):
 if d['remaining_ms']==0 and d['phase']!='finished':d['phase']='closing' if any(pending(d,i) for i in range(4)) else 'review'
 d['priority']=[i for i in d['priority'] if can_surf(d,i) and not pending(d,i)]
def values(d,i,all_judges=False):
 zero={p['wave'] for p in d['interferences'][i] if p['wave'] is not None};scores=[]
 for j,m in enumerate(d['waves'][i]):
  if m is not None:scores.append(0 if j in zero else (sum(m)+2)//5 if all_judges else (sum(sorted(m)[1:-1])+1)//3)
 scores=sorted(scores,reverse=True)+[0]*40;scores=scores[:40];ps=d['interferences'][i]
 if len(ps)==1:scores[1]=(scores[1]+1)//2 if ps[0]['kind']=='non_priority' else 0
 elif len(ps)==2:
  scores[0]=(scores[0]+1)//2;scores[1]=(scores[1]+1)//2 if all(p['kind']=='non_priority' for p in ps) else 0
 return scores
def ranking_key(d,i):
 result=[]
 for all_judges in (False,True):
  s=values(d,i,all_judges);result.extend([sum(s[:2]),s[0]]+[sum(s[:n]) for n in range(3,41)])
 return result
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 for i in range(4):
  ws=d['waves'][i]
  if len(ws)>d['wave_limit']+d['extra_waves'][i] or any(m is None for m in ws[:-1]):bad('Wave allowance or unfinished-wave order is invalid')
  if pending(d,i) and d['status'][i] in ('dns','withdrawn'):bad('Resolve a started wave before withdrawal')
  if d['status'][i]=='dns' and ws:bad('A non-starter cannot have rides')
  for p in d['interferences'][i]:
   if p['wave'] is not None and p['wave']>=len(ws):bad('Interference must refer to an existing ride or a paddling incident')
 if len(set(d['priority']))!=len(d['priority']) or any(not can_surf(d,i) or pending(d,i) for i in d['priority']):bad('Priority order contains an ineligible or duplicate surfer')
 if d['phase']=='setup' and (any(d['waves']) or any(d['interferences']) or any(d['extra_waves']) or d['priority'] or d['remaining_ms']!=d['duration_ms']):bad('Setup precedes rides, penalties and elapsed heat time')
 if d['remaining_ms']>d['duration_ms']:bad('Remaining heat time exceeds configured duration')
 if d['phase'] in ('live','paused') and d['remaining_ms']==0:bad('Expired heat must enter closing or review')
 if d['phase'] in ('closing','review','finished') and d['remaining_ms']!=0:bad('Closed heat cannot retain time')
 if d['phase']=='closing' and not any(pending(d,i) for i in range(4)) or d['phase'] in ('review','finished') and any(pending(d,i) for i in range(4)):bad('Pending ride marks and heat phase disagree')
def schemas(d):
 phase=d['phase'];s={}
 if phase=='finished':return s
 if phase=='setup':return dict(configure=dict(duration_ms=dict(type='integer',minimum=600000,maximum=2400000),wave_limit=dict(type='integer',minimum=1,maximum=20)),start_heat={},withdraw=dict(surfer=SURFER),disqualify=dict(surfer=SURFER))
 if phase=='live':s.update(start_wave=dict(surfer=SURFER),elapse=dict(milliseconds=dict(type='integer',minimum=1,maximum=2400000)),pause_heat={})
 if phase=='paused':s['resume_heat']={}
 if phase in ('live','paused'):
  s.update(set_priority=dict(order=dict(type='array',minItems=0,maxItems=4,items=SURFER)),grant_extra_wave=dict(surfer=SURFER),end_heat={},withdraw=dict(surfer=SURFER))
 if phase in ('live','paused','closing'):s['complete_wave']=dict(surfer=SURFER,marks=MARKS)
 if phase=='review':s.update(correct_marks=dict(surfer=SURFER,wave=WAVE,marks=MARKS),confirm_result={},correct_interference=dict(surfer=SURFER,index=dict(type='integer',minimum=0,maximum=1),kind=dict(type='enum',values=['non_priority','priority'],nullable=True)))
 s.update(interference=dict(surfer=SURFER,kind=dict(type='enum',values=['non_priority','priority']),wave=dict(WAVE,nullable=True)),disqualify=dict(surfer=SURFER))
 return s
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];s=schemas(d)
 if k not in s:fail('Action is not permitted in this phase')
 fields(p,s[k],'/params');i=p.get('surfer')
 if k=='configure':d.update(duration_ms=p['duration_ms'],remaining_ms=p['duration_ms'],wave_limit=p['wave_limit'])
 elif k=='start_heat':d['phase']='live'
 elif k=='start_wave':
  if not can_surf(d,i) or pending(d,i):fail('Surfer is unavailable, already riding or has used the wave allowance')
  d['waves'][i].append(None);d['priority']=[j for j in d['priority'] if j!=i]
 elif k=='complete_wave':
  if not pending(d,i):fail('A wave must begin before its marks are entered')
  d['waves'][i][-1]=p['marks'][:]
 elif k=='correct_marks':
  if p['wave']>=len(d['waves'][i]):fail('Correct an existing ride only')
  d['waves'][i][p['wave']]=p['marks'][:]
 elif k=='elapse':
  if p['milliseconds']>d['remaining_ms']:fail('Heat clock cannot pass zero')
  d['remaining_ms']-=p['milliseconds']
 elif k=='pause_heat':d['phase']='paused'
 elif k=='resume_heat':d['phase']='live'
 elif k=='set_priority':
  if len(set(p['order']))!=len(p['order']) or any(not can_surf(d,j) or pending(d,j) for j in p['order']):fail('Priority must list distinct available surfers')
  d['priority']=p['order'][:]
 elif k=='grant_extra_wave':
  if d['status'][i]!='eligible' or len(d['interferences'][i])==2 or d['extra_waves'][i]>=20:fail('An additional official wave requires an eligible surfer')
  d['extra_waves'][i]+=1
 elif k=='end_heat':d['remaining_ms']=0
 elif k in ('withdraw','disqualify'):
  if d['status'][i] in ('dns','dq') or k=='withdraw' and d['status'][i]!='eligible':fail('Surfer cannot receive this status now')
  if k=='withdraw' and pending(d,i):fail('Resolve the started ride before withdrawal')
  d['status'][i]='dq' if k=='disqualify' else 'withdrawn' if d['waves'][i] else 'dns'
 elif k=='interference':
  if d['status'][i] in ('dns','dq') or len(d['interferences'][i])==2:fail('A surfer can receive at most two interference calls')
  if p['wave'] is not None and p['wave']>=len(d['waves'][i]):fail('The interference ride must already exist')
  d['interferences'][i].append(dict(kind=p['kind'],wave=p['wave']));d['priority']=[j for j in d['priority'] if j!=i]
 elif k=='correct_interference':
  if p['index']>=len(d['interferences'][i]):fail('Correct an existing interference call only')
  if p['kind'] is None:d['interferences'][i].pop(p['index'])
  else:d['interferences'][i][p['index']]['kind']=p['kind']
 elif k=='confirm_result':d['phase']='finished'
 settle(d);return d
def legal(state):
 d=state['data']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['Clock, wave allowance, eligibility and judging phase must permit the event.'],external_observations=['Official ride starts, five judge marks, priority order and interference calls.']) for k,v in schemas(d).items()],constraints=dict(phase=d['phase'],remaining_ms=d['remaining_ms'],priority=d['priority'],wave_allowance_remaining=[d['wave_limit']+d['extra_waves'][i]-len(d['waves'][i]) for i in range(4)],score_unit_denominator=100),completeness=False,reason='official_surfing_heat_events')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';ranked=sorted([(ranking_key(d,i),i) for i in range(4) if d['status'][i]!='dns' and not disqualified(d,i)],key=lambda x:tuple(-v for v in x[0])+(x[1],)) if done else []
 winners=[state['players'][i]['id'] for key,i in ranked if key==ranked[0][0]] if ranked else []
 return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='review' else 'ongoing',result_kind=('ranking' if ranked else 'no_contest') if done else 'none',winners=winners,losers=[p['id'] for p in state['players'] if p['id'] not in winners] if winners else [],placements=[dict(player_id=state['players'][i]['id'],place=1+sum(other>key for other,_ in ranked),score_units=key[0],score_unit_denominator=100) for key,i in ranked],reason='confirmed_heat' if done else 'result_review' if d['phase']=='review' else 'ongoing',evidence_required=['Official result confirmation.'] if d['phase']=='review' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
