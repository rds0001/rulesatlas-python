"""Sport Sambo score-sheet events, recorded after official technique decisions."""
from copy import deepcopy
from ..values import fields,fail
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
P=I(0,1)
def summary(d):
 tech=[sum(x['points'] for x in d['techniques'] if x['player']==t) for t in (0,1)]
 penalty=[0,0];warnings=[0,0];prohibited=[False,False];last_warning=None
 for e in d['warnings']:
  for t in e['players']:
   warnings[t]+=1;penalty[1-t]+=int(warnings[t]>1 or e['kind']=='prohibited')
   if e['kind']=='prohibited':prohibited[t]=True
  if len(e['players'])==1:last_warning=e['players'][0]
 scores=[tech[t]+penalty[t] for t in (0,1)]
 return tech,scores,warnings,prohibited,last_warning
def decision(d):
 tech,scores,warnings,_,last=summary(d)
 for values in (scores,tech,[sum(x['player']==t and x['points']==4 for x in d['techniques']) for t in (0,1)],[sum(x['player']==t and x['points']==2 for x in d['techniques']) for t in (0,1)]):
  if values[0]!=values[1]:return int(values[1]>values[0])
 if d['techniques']:return d['techniques'][-1]['player']
 if warnings[0]!=warnings[1]:return int(warnings[1]<warnings[0])
 return None if last is None else 1-last
def finish(d,w,reason):d.update(phase='finished',winner=w,reason=reason)
def superiority(d):
 scores=summary(d)[1]
 if abs(scores[0]-scores[1])>=8:finish(d,int(scores[1]>scores[0]),'superiority')
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 for t in (0,1):
  holds=[x['points'] for x in d['techniques'] if x['player']==t and x['kind']=='hold_down']
  if sum(holds)>4 or len(holds)>2 or any(x not in (2,4) for x in holds):bad('Scored hold-downs cannot exceed four points per athlete')
 tech,scores,warnings,prohibited,last=summary(d)
 if max(warnings)>3:bad('Fourth warning must be a terminal withdrawal, not a scored warning')
 for t in (0,1):
  if sum(t in e['players'] and e['kind']=='prohibited' for e in d['warnings'])>1:bad('Repeated prohibited technique requires withdrawal')
 for e in d['warnings']:
  if len(set(e['players']))!=len(e['players']):bad('Simultaneous warnings require distinct athletes')
 if d['phase']=='ready' and (d['remaining_ms']!=300000 or d['techniques'] or d['warnings'] or any(d['assistance_ms'])):bad('Ready bout has no prior activity')
 if d['phase'] in ('fighting','paused') and not d['remaining_ms']:bad('Expired bout requires score-sheet review')
 if d['phase']=='review' and d['remaining_ms']:bad('Review follows the final gong')
 if d['phase']=='finished':
  if d['reason'] is None or (d['winner'] is None)!=(d['reason']=='double_defeat'):bad('Finished bout requires a consistent result')
  if d['reason']=='points' and (d['remaining_ms'] or decision(d)!=d['winner']):bad('Final decision must follow the score-sheet tie-break')
  if d['reason']=='superiority' and (d['winner'] is None or scores[d['winner']]-scores[1-d['winner']]<8):bad('Superiority requires an eight-point lead')
 elif d['winner'] is not None or d['reason'] is not None or abs(scores[0]-scores[1])>=8:bad('An ongoing bout cannot retain a decided result')
def schemas(d):
 ph=d['phase'];s={}
 if ph=='finished':return s
 if ph=='ready':s['start']={}
 if ph=='fighting':s.update(pause={},elapse=dict(milliseconds=I(1,300000)))
 if ph=='paused':s.update(resume={},assistance=dict(player=P,milliseconds=I(1,120001)))
 if ph in ('fighting','paused','review'):
  s.update(throw=dict(player=P,points=dict(type='enum',values=[1,2,4])),hold_down=dict(player=P,duration_ms=I(0,20000)),warning=dict(players=dict(type='array',minItems=1,maxItems=2,items=P),kind=dict(type='enum',values=['ordinary','prohibited'])),total_victory=dict(player=P,method=dict(type='enum',values=['perfect_throw','submission'])))
 if ph=='review':s['confirm_result']={}
 s.update(withdraw=dict(player=P),disqualify=dict(player=P),double_defeat={})
 return s
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];s=schemas(d)
 if k not in s:fail('Action is not permitted in this phase')
 fields(p,s[k],'/params')
 if k=='start':d['phase']='fighting'
 elif k=='pause':d['phase']='paused'
 elif k=='resume':d['phase']='fighting'
 elif k=='elapse':
  if p['milliseconds']>d['remaining_ms']:fail('Elapsed time exceeds the bout clock')
  d['remaining_ms']-=p['milliseconds']
  if not d['remaining_ms']:d['phase']='review'
 elif k=='assistance':
  t=p['player'];d['assistance_ms'][t]+=p['milliseconds']
  if d['assistance_ms'][t]>120000:finish(d,1-t,'assistance_limit')
 elif k=='throw':d['techniques'].append(dict(player=p['player'],kind='throw',points=p['points']));superiority(d)
 elif k=='hold_down':
  t=p['player'];duration=p['duration_ms']
  if duration>300000-d['remaining_ms']:fail('Recorded hold duration cannot exceed elapsed bout time')
  holds=[x for x in d['techniques'] if x['player']==t and x['kind']=='hold_down']
  if sum(x['points'] for x in holds)>=4:fail('The athlete has exhausted scored hold-down entitlement')
  value=4 if duration==20000 else 2 if duration>=10000 else 0
  if value:
   if value==4:d['techniques']=[x for x in d['techniques'] if not(x['player']==t and x['kind']=='hold_down')]
   d['techniques'].append(dict(player=t,kind='hold_down',points=value));superiority(d)
 elif k=='warning':
  players=p['players'];kind=p['kind'];_,_,counts,prohibited,_=summary(d)
  if len(set(players))!=len(players):fail('Warning recipients must be distinct')
  excluded=[t for t in players if counts[t]==3 or kind=='prohibited' and prohibited[t]]
  if excluded:finish(d,None if len(excluded)==2 else 1-excluded[0],'double_defeat' if len(excluded)==2 else 'warnings')
  else:d['warnings'].append(dict(players=players[:],kind=kind));superiority(d)
 elif k=='total_victory':finish(d,p['player'],p['method'])
 elif k=='confirm_result':
  w=decision(d)
  if w is None:fail('Official activity warning is required to resolve an unscored indistinguishable bout')
  finish(d,w,'points')
 elif k in ('withdraw','disqualify'):finish(d,1-p['player'],'withdrawal' if k=='withdraw' else 'disqualification')
 elif k=='double_defeat':finish(d,None,'double_defeat')
 return d
def legal(state):
 d=state['data'];tech,scores,warnings,prohibited,last=summary(d)
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=s,preconditions=['Bout phase, score-sheet limits and official adjudication must permit the event.'],external_observations=['Official evaluated techniques, completed hold durations and warning decisions; late entries concern actions before the gong.']) for k,s in schemas(d).items()],constraints=dict(phase=d['phase'],remaining_ms=d['remaining_ms'],scores=scores,technical_points=tech,warnings=warnings,hold_points_remaining=[4-sum(x['points'] for x in d['techniques'] if x['player']==t and x['kind']=='hold_down') for t in (0,1)],activity_decision_required=d['remaining_ms']<=150000 and decision(d) is None),completeness=False,reason='official_sport_sambo_score_sheet')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';w=d['winner']
 return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='review' else 'ongoing',result_kind=('disqualification' if d['reason']=='double_defeat' else 'win') if done else 'none',winners=[state['players'][w]['id']] if w is not None else [],losers=[state['players'][t]['id'] for t in (0,1) if t!=w] if done else [],placements=[],reason=d['reason'] if done else 'score_sheet_review_required' if d['phase']=='review' else 'ongoing',evidence_required=['Official final score-sheet and any unresolved activity warning.'] if d['phase']=='review' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
