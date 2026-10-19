"""Compact FIBA-style match bookkeeping from official scoring and foul events."""
from copy import deepcopy
from ..values import fields,fail
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
TEAM=I(0,1);SLOT=I(0,11);BOOL=dict(type='boolean')
SCHEMAS=dict(set_lineup=dict(team=TEAM,roster_size=I(5,12),active=dict(type='array',minItems=5,maxItems=5,items=SLOT)),start_match=dict(first_control=TEAM),pause={},resume={},elapse=dict(milliseconds=I(1,600000)),field_goal=dict(team=TEAM,player=SLOT,value=dict(type='integer',enum=[2,3]),at_buzzer=BOOL),foul=dict(team=TEAM,player=SLOT,kind=dict(type='string',enum=['personal','technical','unsporting','disqualifying']),shooter=SLOT,shooting_points=dict(type='integer',enum=[0,2,3]),basket_made=BOOL,team_control=BOOL,at_buzzer=BOOL),bench_technical=dict(team=TEAM,shooter=SLOT),free_throw=dict(made=BOOL,violation=dict(type='string',enum=['none','shooter','offense','defense','both'])),replace_shooter=dict(penalty_id=I(1,1000000),player=SLOT),cancel_equal_penalties=dict(first_id=I(1,1000000),second_id=I(1,1000000)),substitute=dict(team=TEAM,out=SLOT,**{'in':SLOT}),enter_player=dict(team=TEAM,player=SLOT),timeout=dict(team=TEAM),end_timeout={},held_ball={},resolve_arrow_throwin=dict(result=dict(type='string',enum=['completed','thrower_violation','defender_violation'])),end_period={},start_next_period={},forfeit=dict(loser=TEAM),no_contest={})
def active(t):return [i for i,s in enumerate(t['status']) if s=='active']
def timeouts_remaining(d,i):
 t=d['teams'][i]
 if d['period']<=2:return 2-t['timeouts_first']
 if d['period']>=5:return 1-t['timeouts_overtime']
 return min(3-t['timeouts_second'],2-t['timeouts_late_fourth']) if d['period']==4 and d['remaining_ms']<=120000 else 3-t['timeouts_second']
def finish(d,w,reason):d.update(phase='finished',winner=w,reason=reason,running=False,free_throws=[],timeout_team=None,pending_arrow=False,buzzer_pending=False)
def default_if_needed(d):
 for i,t in enumerate(d['teams']):
  if len(active(t))<2:
   w=1-i
   if d['scores'][w]<=d['scores'][i]:d['scores']=[2 if j==w else 0 for j in (0,1)]
   finish(d,w,'default');return

def queue(d,team,shooter,count,kind,restart):
 if count:
  r=dict(id=d['next_penalty_id'],team=team,shooter=shooter,total=count,remaining=count,kind=kind,restart=restart)
  d['free_throws'].insert(0,r) if kind in ('technical','bench') else d['free_throws'].append(r)
  d['next_penalty_id']+=1

def valid_player(d,team,player,playing=False):
 t=d['teams'][team]
 if player>=len(t['status']) or t['status'][player]=='excluded' or playing and t['status'][player]!='active':fail('Player is not eligible for this event')

def live_period(d):
 if d['phase']!='period' or d['timeout_team'] is not None:fail('Event requires an open playing period outside a timeout')
def buzzer(d,flag):
 if d['remaining_ms']==0:
  if not flag or not d['buzzer_pending']:fail('An expired clock permits only the unresolved official buzzer play')
  d['buzzer_pending']=False
 elif flag:fail('Buzzer ruling requires time expiry')

def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 if d['remaining_ms']>(600000 if d['period']<=4 else 300000):bad('Clock exceeds the current period duration')
 for t in d['teams']:
  n=len(t['status'])
  if any(len(t[k])!=n for k in ('fouls','technical','unsporting','disqualified')):bad('Player eligibility and foul vectors must have matching lengths')
  if len(active(t))>5 or d['phase'] not in ('pre_game','finished') and len(active(t))<2:bad('Active player count conflicts with match eligibility')
  for i in range(n):
   dq=t['technical'][i]>=2 or t['unsporting'][i]>=2 or t['technical'][i]+t['unsporting'][i]>=2
   if t['technical'][i]+t['unsporting'][i]>t['fouls'][i] or dq and not t['disqualified'][i]:bad('Disciplinary foul totals require consistent player disqualification')
   if (t['status'][i]=='excluded')!=(t['fouls'][i]>=5 or t['disqualified'][i]):bad('Excluded status must follow five fouls or disqualification')
  if t['timeouts_late_fourth']>t['timeouts_second']:bad('Late-fourth timeouts are part of the second-half allowance')
 if d['phase']=='pre_game' and (d['period']!=1 or d['remaining_ms']!=600000 or d['scores']!=[0,0] or any(any(t['fouls']) or t['team_fouls'] for t in d['teams'])):bad('Unstarted match must have no score or foul activity')
 if d['running'] and (d['phase']!='period' or not d['remaining_ms'] or d['free_throws'] or d['timeout_team'] is not None or d['pending_arrow']):bad('Running clock conflicts with a stoppage or time expiry')
 if d['phase'] in ('pre_game','interval','finished') and (d['running'] or d['free_throws'] or d['timeout_team'] is not None or d['pending_arrow'] or d['buzzer_pending']):bad('Dead interval cannot retain an unresolved playing sequence')
 if d['phase']=='interval' and d['remaining_ms']!=0:bad('The previous period must expire before its interval')
 if d['buzzer_pending'] and (d['phase']!='period' or d['remaining_ms']):bad('Buzzer review exists only at period expiry')
 ids=[r['id'] for r in d['free_throws']]
 if len(ids)!=len(set(ids)) or any(i>=d['next_penalty_id'] for i in ids):bad('Free-throw penalty identifiers must be distinct and already issued')
 for r in d['free_throws']:
  if r['remaining']>r['total'] or r['shooter']>=len(d['teams'][r['team']]['status']):bad('Free-throw queue has an invalid attempt count or shooter')
 if d['phase']=='finished':
  if d['reason'] is None or (d['reason']=='no_contest')!=(d['winner'] is None):bad('Finished match requires a consistent result')
  if d['reason']!='no_contest' and d['scores'][d['winner']]<=d['scores'][1-d['winner']]:bad('The winner must lead the final score')
  if d['reason']=='points' and (d['period']<4 or d['remaining_ms']):bad('Ordinary victory requires completed regulation or overtime')
 else:
  if d['winner'] is not None or d['reason'] is not None:bad('An open match cannot retain a winner')
  if d['phase']=='interval' and d['period']>=4 and d['scores'][0]!=d['scores'][1]:bad('Overtime requires tied scores')

def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params']
 if k not in SCHEMAS:fail('Unknown basketball event')
 fields(p,SCHEMAS[k],'/params')
 if d['phase']=='finished':fail('Match is finished')
 if k=='set_lineup':
  if d['phase']!='pre_game':fail('Rosters are fixed after the match starts')
  n=p['roster_size'];a=p['active']
  if len(set(a))!=5 or max(a)>=n:fail('A starting lineup requires five distinct roster players')
  t=d['teams'][p['team']];t.update(status=['active' if i in a else 'bench' for i in range(n)],fouls=[0]*n,technical=[0]*n,unsporting=[0]*n,disqualified=[False]*n)
 elif k=='start_match':
  if d['phase']!='pre_game' or any(len(active(t))!=5 for t in d['teams']):fail('Start with five eligible players per team')
  d.update(phase='period',running=True,arrow=1-p['first_control'])
 elif k=='pause':
  live_period(d)
  if not d['running']:fail('Clock is already stopped')
  d['running']=False
 elif k=='resume':
  live_period(d)
  if d['running'] or not d['remaining_ms'] or d['free_throws'] or d['pending_arrow']:fail('Resolve the stoppage before starting the game clock')
  d['running']=True
 elif k=='elapse':
  live_period(d)
  if not d['running'] or p['milliseconds']>d['remaining_ms']:fail('Advance only running time within the period')
  d['remaining_ms']-=p['milliseconds']
  if not d['remaining_ms']:d['running']=False;d['buzzer_pending']=True
 elif k=='field_goal':
  live_period(d)
  if d['free_throws'] or d['pending_arrow']:fail('Resolve the pending penalty or throw-in first')
  valid_player(d,p['team'],p['player'],True);buzzer(d,p['at_buzzer']);d['scores'][p['team']]+=p['value']
  if d['period']>=4 and d['remaining_ms']<=120000:d['running']=False
 elif k=='foul':
  live_period(d);team=p['team'];i=p['player'];kind=p['kind'];value=p['shooting_points'];made=p['basket_made'];other=1-team
  valid_player(d,team,i,kind=='personal');valid_player(d,other,p['shooter'],True)
  if made and value==0 or p['team_control'] and (kind!='personal' or value or made) or kind=='technical' and (value or made or p['team_control']):fail('Foul context and shooting outcome are inconsistent')
  if d['remaining_ms']==0 and d['free_throws']:
   if p['at_buzzer']:fail('The buzzer play is already resolved')
  else:buzzer(d,p['at_buzzer'])
  t=d['teams'][team];t['fouls'][i]+=1;t['team_fouls']+=1
  if kind in ('technical','unsporting'):t[kind][i]+=1
  if kind=='disqualifying' or t['technical'][i]+t['unsporting'][i]>=2:t['disqualified'][i]=True
  if t['fouls'][i]>=5 or t['disqualified'][i]:t['status'][i]='excluded'
  if made:d['scores'][other]+=value
  count=1 if kind=='technical' or made else value if value else 2 if kind in ('unsporting','disqualifying') or not p['team_control'] and t['team_fouls']>=5 else 0
  queue(d,other,p['shooter'],count,kind,'retained' if kind in ('unsporting','disqualifying') else 'status_quo' if kind=='technical' else 'normal')
  if p['team_control'] and d['pending_arrow'] and team==d['arrow']:d['arrow']=1-d['arrow'];d['pending_arrow']=False
  d['running']=False;default_if_needed(d)
 elif k=='bench_technical':
  live_period(d);valid_player(d,1-p['team'],p['shooter'],True);queue(d,1-p['team'],p['shooter'],1,'bench','status_quo');d['running']=False
 elif k=='free_throw':
  live_period(d)
  if not d['free_throws']:fail('No free throw is pending')
  r=d['free_throws'][0];valid_player(d,r['team'],r['shooter'],True);violation=p['violation'];made=p['made'] and violation!='shooter'
  if made:d['scores'][r['team']]+=1
  if not made and violation=='defense':return d
  r['remaining']-=1
  if r['remaining']==0:
   last=d['free_throws'].pop(0)
   if not d['free_throws'] and not made and violation=='both' and last['restart']=='normal' and d['remaining_ms']>0:d['pending_arrow']=True
 elif k=='replace_shooter':
  live_period(d);r=next((r for r in d['free_throws'] if r['id']==p['penalty_id']),None)
  if r is None or r['shooter'] in active(d['teams'][r['team']]):fail('Only an unavailable pending shooter needs replacement')
  valid_player(d,r['team'],p['player'],True);r['shooter']=p['player']
 elif k=='cancel_equal_penalties':
  live_period(d);a=next((r for r in d['free_throws'] if r['id']==p['first_id']),None);b=next((r for r in d['free_throws'] if r['id']==p['second_id']),None)
  if a is None or b is None or a['team']==b['team'] or a['remaining']!=a['total'] or b['remaining']!=b['total'] or (a['total'],a['restart'])!=(b['total'],b['restart']):fail('Only unadministered equal opposite penalties may cancel')
  d['free_throws']=[r for r in d['free_throws'] if r['id'] not in (a['id'],b['id'])]
 elif k in ('substitute','enter_player'):
  if d['phase'] not in ('pre_game','interval'):live_period(d)
  if d['running']:fail('Player changes require a stopped-clock opportunity')
  t=d['teams'][p['team']];inc=p['in'] if k=='substitute' else p['player'];valid_player(d,p['team'],inc)
  if t['status'][inc]!='bench':fail('Only an eligible bench player may enter')
  if k=='substitute':
   if d['free_throws'] and d['free_throws'][0]['remaining']<d['free_throws'][0]['total']:fail('Ordinary substitution cannot interrupt a free-throw series')
   out=p['out']
   if out not in active(t) or any(r['team']==p['team'] and r['shooter']==out for r in d['free_throws']):fail('Outgoing player must be active and cannot be a pending free-throw shooter')
   t['status'][out]='bench'
  elif len(active(t))>=5:fail('No active-player vacancy is available')
  t['status'][inc]='active'
 elif k=='timeout':
  live_period(d)
  if d['running'] or timeouts_remaining(d,p['team'])<=0 or d['free_throws'] and d['free_throws'][0]['remaining']<d['free_throws'][0]['total']:fail('No timeout is available at this stoppage')
  t=d['teams'][p['team']]
  if d['period']<=2:t['timeouts_first']+=1
  elif d['period']>=5:t['timeouts_overtime']+=1
  else:
   t['timeouts_second']+=1
   if d['period']==4 and d['remaining_ms']<=120000:t['timeouts_late_fourth']+=1
  d['timeout_team']=p['team']
 elif k=='end_timeout':
  if d['timeout_team'] is None:fail('No timeout is active')
  d['timeout_team']=None
 elif k=='held_ball':
  live_period(d)
  if d['running'] or d['free_throws'] or d['pending_arrow'] or not d['remaining_ms']:fail('Alternating possession requires an available stopped-clock restart')
  d['pending_arrow']=True
 elif k=='resolve_arrow_throwin':
  live_period(d)
  if not d['pending_arrow'] or d['free_throws']:fail('No unblocked alternating-possession throw-in is pending')
  if p['result']!='defender_violation':d['arrow']=1-d['arrow'];d['pending_arrow']=False
 elif k=='end_period':
  live_period(d)
  if d['remaining_ms'] or d['free_throws'] or d['pending_arrow']:fail('Time and all pending penalties must resolve before the period ends')
  d['buzzer_pending']=False
  if d['period']>=4 and d['scores'][0]!=d['scores'][1]:finish(d,0 if d['scores'][0]>d['scores'][1] else 1,'points')
  else:d['phase']='interval'
 elif k=='start_next_period':
  if d['phase']!='interval':fail('No period interval is active')
  d['period']+=1;d['remaining_ms']=600000 if d['period']<=4 else 300000;d.update(phase='period',pending_arrow=True)
  for t in d['teams']:
   if d['period']<=4:t['team_fouls']=0
   else:t['timeouts_overtime']=0
 elif k=='forfeit':
  w=1-p['loser'];d['scores']=[20 if i==w else 0 for i in (0,1)];finish(d,w,'forfeit')
 elif k=='no_contest':finish(d,None,'no_contest')
 return d

def legal(state):
 d=state['data'];phase=d['phase'];names=[]
 if phase=='pre_game':names=['set_lineup','substitute','start_match']
 elif phase=='interval':names=['start_next_period','substitute','enter_player']
 elif phase=='period':
  if d['timeout_team'] is not None:names=['end_timeout']
  else:
   names=['foul','bench_technical']
   if d['running']:names+=['pause','elapse']
   else:names+=['substitute','enter_player','timeout']
   if d['free_throws']:names+=['free_throw','replace_shooter','cancel_equal_penalties']
   elif d['pending_arrow']:names+=['resolve_arrow_throwin']
   else:
    if d['remaining_ms']>0:names+=['field_goal']+(['resume','held_ball'] if not d['running'] else [])
    else:names+=['end_period']+(['field_goal'] if d['buzzer_pending'] else [])
 if phase!='finished':names+=['forfeit','no_contest']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=SCHEMAS[k],preconditions=['Period, stopped-clock opportunity, player eligibility and pending penalties must permit the event.'],external_observations=['Official valid baskets, foul context, completed buzzer play and restart rulings.']) for k in names],constraints=dict(phase=phase,period=d['period'],remaining_ms=d['remaining_ms'],running=d['running'],arrow=d['arrow'],active=[active(t) for t in d['teams']],timeouts_remaining=[timeouts_remaining(d,i) for i in (0,1)],next_free_throw=d['free_throws'][0] if d['free_throws'] else None),completeness=False,reason='official_basketball_events')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';w=d['winner']
 return dict(status='terminal' if done else 'ongoing',result_kind=('no_contest' if w is None else 'forfeit' if d['reason'] in ('forfeit','default') else 'win') if done else 'none',winners=[state['players'][w]['id']] if done and w is not None else [],losers=[state['players'][1-w]['id']] if done and w is not None else [],placements=[],reason=d['reason'] if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
