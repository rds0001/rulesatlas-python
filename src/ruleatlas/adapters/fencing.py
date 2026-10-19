"""Five-touch individual epee pool bout with priority and grouped sanctions."""
from copy import deepcopy
from ..values import fields,fail
I=lambda a,b,**kw:dict(type='integer',minimum=a,maximum=b,**kw)
TEAM=I(0,1)
SCHEMAS=dict(start={},exchange=dict(touches=dict(type='array',minItems=2,maxItems=2,items=dict(type='boolean')),elapsed_ms=I(0,180000)),elapse=dict(milliseconds=I(1,180000)),start_priority=dict(priority=TEAM),infringement=dict(team=TEAM,group=I(1,4)),withdraw=dict(team=TEAM),confirm_result={},confirm_no_contest={})
def award(d,t):
 d['scores'][t]+=1
 if d['scores'][t]==5 or d['phase'] in ('priority','priority_setup'):d.update(phase='review',winner=t)
def end_clock(d):
 if d['phase']=='fencing' and d['remaining_ms']==0:
  if d['scores'][0]==d['scores'][1]:d['phase']='priority_setup'
  else:d.update(phase='review',winner=0 if d['scores'][0]>d['scores'][1] else 1)
 elif d['phase']=='priority' and d['remaining_ms']==0:d.update(phase='review',winner=d['priority'])
def exclude(d,t):
 d['excluded'][t]=True;d.update(phase='review',winner=None if all(d['excluded']) else 1-t)
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE');phase=d['phase']
 for t in (0,1):
  if d['red_count'][t]>d['scores'][1-t] or d['group_three_red'][t] and d['red_count'][t]==0:bad('Penalty record and awarded touches disagree')
 if d['priority'] is not None and phase not in ('priority','review','finished'):bad('Priority exists outside the extra minute')
 if phase=='priority' and (d['priority'] is None or d['remaining_ms']>60000):bad('A priority holder and one-minute clock are required')
 if phase in ('fencing','priority') and (d['remaining_ms']==0 or max(d['scores'])==5 or any(d['excluded'])):bad('Resolved bout cannot remain active')
 if phase in ('priority_setup','priority') and d['scores'][0]!=d['scores'][1]:bad('Extra time requires equal scores')
 if phase=='priority_setup' and d['remaining_ms']!=0:bad('Regulation time must expire before priority selection')
 if phase=='ready' and (d['remaining_ms']!=180000 or d['priority'] is not None or any(d['excluded']) or max(d['scores'])==5):bad('Invalid pre-bout state')
 if phase not in ('review','finished') and d['winner'] is not None:bad('Winner is premature')
 if phase in ('review','finished'):
  if all(d['excluded']):
   if d['winner'] is not None:bad('Double exclusion has no winner')
  elif any(d['excluded']):
   if d['winner']!=int(d['excluded'][0]):bad('The non-excluded fencer wins')
  elif d['winner'] is None:bad('Bout winner is unresolved')
  elif d['scores'][0]!=d['scores'][1]:
   if d['winner']!=(0 if d['scores'][0]>d['scores'][1] else 1):bad('Score and winner disagree')
   if max(d['scores'])<5 and d['remaining_ms']>0 and d['priority'] is None:bad('Regulation bout ended before score or time limit')
  elif d['priority']!=d['winner'] or d['remaining_ms']!=0:bad('A tied bout is decided by expired priority time')
 if d['no_contest'] and (phase!='finished' or not all(d['excluded'])):bad('No contest requires an official double-exclusion resolution')
 if phase=='finished' and all(d['excluded']) and not d['no_contest']:bad('Resolve both exclusions explicitly')
def apply(state,action):
 d=deepcopy(state['data']);p=action['params'];k=action['type'];phase=d['phase']
 if k not in SCHEMAS:fail('Unknown fencing event')
 fields(p,SCHEMAS[k],'/params')
 if k=='start':
  if phase!='ready':fail('Bout has already started')
  d['phase']='fencing'
 elif k in ('exchange','elapse'):
  if phase not in ('fencing','priority'):fail('An active fencing interval is required')
  elapsed=p['elapsed_ms'] if k=='exchange' else p['milliseconds']
  if elapsed>d['remaining_ms']:fail('Elapsed fencing time exceeds the remaining interval')
  d['remaining_ms']-=elapsed
  if k=='exchange':
   touches=p['touches']
   if all(touches):
    if phase=='fencing' and d['scores']!=[4,4]:
     d['scores']=[v+1 for v in d['scores']]
     if max(d['scores'])==5:d.update(phase='review',winner=d['scores'].index(5))
   elif any(touches):award(d,0 if touches[0] else 1)
  end_clock(d)
 elif k=='start_priority':
  if phase!='priority_setup':fail('No tied regulation result awaits priority')
  d.update(phase='priority',priority=p['priority'],remaining_ms=60000)
 elif k=='infringement':
  t=p['team'];group=p['group']
  if d['excluded'][t] or phase=='review' and group!=4:fail('This sanction cannot be issued in the current bout phase')
  black=group==4 or group==3 and d['group_three_red'][t]
  if black:exclude(d,t)
  elif group==1 and not d['yellow'][t] and d['red_count'][t]==0:d['yellow'][t]=True
  else:
   if group==3:d['group_three_red'][t]=True
   d['red_count'][t]+=1;award(d,1-t)
 elif k=='withdraw':
  if d['excluded'][p['team']]:fail('Fencer is already excluded')
  exclude(d,p['team'])
 elif k=='confirm_result':
  if phase!='review' or all(d['excluded']):fail('Resolve the bout winner before confirmation')
  d['phase']='finished'
 elif k=='confirm_no_contest':
  if phase!='review' or not all(d['excluded']):fail('Official no-contest decision requires both exclusions')
  d.update(phase='finished',no_contest=True)
 return d
def legal(state):
 d=state['data'];phase=d['phase'];names={'ready':['start'],'fencing':['exchange','elapse'],'priority_setup':['start_priority'],'priority':['exchange','elapse'],'review':['confirm_no_contest'] if all(d['excluded']) else ['confirm_result']}.get(phase,[])
 if phase!='finished':names+=['infringement','withdraw']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=SCHEMAS[k],preconditions=['Bout phase, score limit, elapsed time and penalty group must permit the event.'],external_observations=['Official valid touch signals, penalty classification or drawn priority.']) for k in names],constraints=dict(phase=phase,remaining_ms=d['remaining_ms'],scores=d['scores'],priority=d['priority']),completeness=False,reason='official_epee_bout_events')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';w=d['winner']
 return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='review' else 'ongoing',result_kind=('no_contest' if d['no_contest'] else 'win') if done else 'none',winners=[state['players'][w]['id']] if done and w is not None else [],losers=[state['players'][1-w]['id']] if done and w is not None else [],placements=[],reason='epee_bout_confirmed' if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
