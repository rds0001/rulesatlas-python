"""Best-of-three right-arm match with bounded officiating events."""
from copy import deepcopy
from ..values import fields,fail
PLAYER=dict(type='integer',minimum=0,maximum=1)
def wins(d):return [d['bouts'].count(p) for p in (0,1)]
def end_bout(d,w,reason):
 d['bouts'].append(w);d['last_reason']=reason
 if wins(d)[w]==2:d.update(phase='finished',winner=w,break_ms=0)
 else:d.update(phase='break',break_ms=60000)
 return d
def foul(d,p,losing=False):
 d['fouls'][p]+=1
 if losing or d['fouls'][p]>=2:return end_bout(d,1-p,'losing_position_foul' if losing else 'two_fouls')
 d.update(phase='setup',grip='referee',setup_ms=60000);return d
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE');counts=wins(d)
 if len(d['bouts'])>3 or any(n>2 for n in counts) or len(d['bouts'])==3 and d['bouts'][0]==d['bouts'][1]:bad('The first two bout wins decide the match')
 if d['grip']=='free' and d['setup_ms']==60000 or d['grip']=='referee' and d['setup_ms']!=60000:bad('Referee grip follows the expired free-setup minute or a restart')
 if d['phase']=='finished':
  if d['winner'] is None or counts[d['winner']]!=2 or d['break_ms']:bad('Match winner must have two bout wins')
 elif d['winner'] is not None or max(counts)>=2:bad('Ongoing match cannot already have a winner')
 if d['phase']=='break':
  if not d['bouts'] or not d['break_ms']:bad('A completed nonfinal bout requires its remaining break')
 elif d['break_ms']:bad('Break time exists only between bouts')
 if d['phase'] in ('setup','ready','pull'):
  if d['last_reason'] is not None or any(f>=2 for f in d['fouls']):bad('An ongoing bout cannot retain a completed-bout reason or two fouls')
 else:
  if d['last_reason'] is None or not d['bouts']:bad('Completed bout requires a result reason')
  if d['last_reason']=='two_fouls' and d['fouls'][1-d['bouts'][-1]]!=2:bad('Two-foul loss requires two fouls by the losing athlete')
  if d['last_reason']=='losing_position_foul' and not d['fouls'][1-d['bouts'][-1]]:bad('Losing-position foul requires a foul by the losing athlete')
def apply(state,action):
 d=deepcopy(state['data']);p=action['params'];k=action['type']
 if k=='advance_setup':
  fields(p,dict(milliseconds=dict(type='integer',minimum=1,maximum=60000)),'/params')
  if d['phase']!='setup' or d['grip']!='free' or d['setup_ms']+p['milliseconds']>60000:fail('Advance only the remaining free-setup minute')
  d['setup_ms']+=p['milliseconds']
  if d['setup_ms']==60000:d['grip']='referee'
  return d
 if k=='confirm_grip':
  fields(p,{},'/params')
  if d['phase']!='setup':fail('Confirm the adjudicated legal grip only during setup')
  d['phase']='ready';return d
 if k=='go':
  fields(p,{},'/params')
  if d['phase']!='ready':fail('The referee start command requires a confirmed grip')
  d['phase']='pull';return d
 if k in ('warning','foul','early_start','grip_movement'):
  schema=dict(player=PLAYER)
  if k=='foul':schema['losing_position']=dict(type='boolean')
  fields(p,schema,'/params');who=p['player']
  if d['phase'] not in ('setup','ready','pull'):fail('Sanctions require an active bout')
  if k=='early_start' and d['phase']!='ready':fail('An early start occurs after grip confirmation and before the go command')
  if k=='grip_movement' and (d['grip']!='referee' or d['phase'] not in ('setup','ready')):fail('Movement in referee grip is penalized before the go command')
  if k=='warning':
   d['warnings'][who]+=1
   if d['warnings'][who]==2:d['warnings'][who]=0;return foul(d,who)
   return d
  if k=='foul' and p['losing_position'] and d['phase']!='pull':fail('A losing-position foul requires an active pull')
  return foul(d,who,p.get('losing_position',False))
 if k=='slip':
  fields(p,{},'/params')
  if d['phase']!='pull' or d['strapped']:fail('An unpenalized hand slip requires an unstrapped active pull')
  d.update(phase='setup',grip='referee',setup_ms=60000,strapped=True);return d
 if k=='pin':
  fields(p,dict(winner=PLAYER),'/params')
  if d['phase']!='pull':fail('An official pin requires an active pull')
  return end_bout(d,p['winner'],'pin')
 if k=='advance_break':
  fields(p,dict(milliseconds=dict(type='integer',minimum=1,maximum=60000)),'/params')
  if d['phase']!='break' or p['milliseconds']>d['break_ms']:fail('Advance only the remaining between-bout minute')
  d['break_ms']-=p['milliseconds']
  if not d['break_ms']:d.update(phase='setup',grip='free',setup_ms=0,warnings=[0,0],fouls=[0,0],strapped=False,last_reason=None)
  return d
 if k=='withdraw':
  fields(p,dict(player=PLAYER),'/params');w=1-p['player']
  while wins(d)[w]<2:d['bouts'].append(w)
  d.update(phase='finished',winner=w,last_reason='withdrawal',break_ms=0);return d
 fail('Unknown action')
def legal(state):
 d=state['data'];schemas={};ph=d['phase']
 if ph=='setup':
  schemas['confirm_grip']={}
  if d['grip']=='free':schemas['advance_setup']=dict(milliseconds=dict(type='integer',minimum=1,maximum=60000-d['setup_ms']))
 if ph=='ready':schemas.update(go={},early_start=dict(player=PLAYER))
 if ph in ('setup','ready','pull'):
  schemas.update(warning=dict(player=PLAYER),foul=dict(player=PLAYER,losing_position=dict(type='boolean')))
  if d['grip']=='referee' and ph in ('setup','ready'):schemas['grip_movement']=dict(player=PLAYER)
 if ph=='pull':
  schemas['pin']=dict(winner=PLAYER)
  if not d['strapped']:schemas['slip']={}
 if ph=='break':schemas['advance_break']=dict(milliseconds=dict(type='integer',minimum=1,maximum=d['break_ms']))
 schemas['withdraw']=dict(player=PLAYER)
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=s,preconditions=['Bout phase, grip and foul status must permit the event.'],external_observations=['Official grip, start, slip, warning, foul, pin or withdrawal decision.']) for k,s in schemas.items()],constraints=dict(grip=d['grip'],strapped=d['strapped'],warnings=d['warnings'],fouls=d['fouls'],bout_wins=wins(d)),completeness=False,reason='adjudicated_armwrestling_events')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';w=d['winner'];counts=wins(d)
 return dict(status='terminal' if done else 'ongoing',result_kind='win' if done else 'none',winners=[state['players'][w]['id']] if done else [],losers=[state['players'][1-w]['id']] if done else [],placements=[dict(player_id=state['players'][p]['id'],place=1 if p==w else 2,bouts=counts[p]) for p in (0,1)] if done else [],reason='withdrawal' if done and d['last_reason']=='withdrawal' else 'two_bout_wins' if done else 'ongoing',evidence_required=[],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
