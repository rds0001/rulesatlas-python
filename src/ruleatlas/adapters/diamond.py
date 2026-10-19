"""Completed-play inning rules; official outcomes replace pitch and ball physics."""
from copy import deepcopy
from ..values import fields,fail
from .pelota import outcome
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
E=lambda *x:dict(type='enum',values=list(x))
A=lambda x,n,m=None:dict(type='array',minItems=n,maxItems=n if m is None else m,items=x)
T=I(0,1);P=I(0,24);B=dict(type='boolean')
def due(d):return d['lineup'][d['batting']][d['next_slot'][d['batting']]]
def finish(d,w,r):d.update(phase='finished',winner=w,reason=r)
def clear_review(d):d.update(last_runs=[],last_participants=[],last_home_run=False,last_force=False,appealed=[])
def roster_ok(d):return all(d['status'][t][p]=='active' for t in (0,1) for p in d['lineup'][t])
def winning_limit(d):
 if d['inning']>=d['regulation_innings']:return 1
 if d['softball'] and d['inning']>=3:return 15 if d['inning']==3 else 10 if d['inning']==4 else 7
 return None
def next_half(d):
 if d['batting']==1:d['inning']+=1
 d['batting']=1-d['batting'];d.update(outs=0,bases=[None]*3,temporary=[None]*3,phase='play',half_runs=0)
 d['visits']=[0,0];d['pitcher_locked'][d['batting']]=False
 if d['softball'] and d['inning']>=8:d['bases'][1]=d['lineup'][d['batting']][(d['next_slot'][d['batting']]-1)%9]
 clear_review(d)
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 if d['regulation_innings']!=(7 if d['softball'] else 9):bad('Regulation length must match the selected discipline')
 for t in (0,1):
  line=d['lineup'][t]
  if len(set(line))!=9 or d['pitcher'][t] not in line or d['catcher'][t] not in line or d['pitcher'][t]==d['catcher'][t]:bad('Nine distinct batting slots require distinct active pitcher and catcher roles')
  if any(d['status'][t][i]=='active' and i not in line for i in range(25)):bad('Active player must occupy a batting slot')
  if any(n>(2 if d['softball'] and i<9 else 1) for i,n in enumerate(d['entries'][t])):bad('Player exceeds permitted entries')
  if d['pitcher_banned'][t][d['pitcher'][t]] and d['phase']=='play':bad('Removed pitcher cannot pitch again')
 runners=[x for x in d['bases'] if x is not None]
 if len(runners)!=len(set(runners)) or any(x not in d['lineup'][d['batting']] for x in runners):bad('Bases require distinct players in the current batting lineup')
 if d['phase']=='play' and (d['outs']>=3 or not roster_ok(d)):bad('Play requires fewer than three outs and complete eligible lineups')
 if d['phase']=='review' and not d['last_participants']:bad('Review requires a recorded completed play')
 if len(set(d['last_runs']))!=len(d['last_runs']) or any(x not in d['last_participants'] for x in d['last_runs']):bad('Scored runners must belong to the last play')
 if len(d['last_runs'])>d['score'][d['batting']] or d['half_runs']>d['score'][d['batting']]:bad('Run ledger cannot exceed team score')
 if d['last_force'] and d['outs']==3 and d['last_runs']:bad('A force third out cancels all runs on that play')
 if d['phase']=='finished':
  if d['reason'] is None or (d['reason']=='no_contest')!=(d['winner'] is None):bad('Result must specify winner or no contest')
  if d['reason'] in ('regulation','walkoff','run_ahead','forfeit') and d['score'][d['winner']]<=d['score'][1-d['winner']]:bad('Winning score must lead')
 else:
  if d['winner'] is not None or d['reason'] is not None:bad('Unfinished game cannot contain a result')
def schemas(d):
 ph=d['phase'];s={}
 if ph=='finished':return s
 if ph=='suspended':return dict(resume={},official_result=dict(winner=dict(T,nullable=True)))
 if ph=='play':
  s.update(play=dict(batter=dict(P,nullable=True),kind=E('hit','error','fielders_choice','out','dropped_third','infield_fly','home_run','runner_play'),destinations=A(I(-1,4),4),credited=A(P,0,4),third_out=E('none','tag','force','batter_first','preceding','left_early')),award_first=dict(batter=P,reason=E('walk','hit_by_pitch','interference')),mound_visit=dict(team=T),temporary_runner={})
 if ph=='review':s.update(confirm_play={},appeal=dict(runner=P,force=B,cancel_runs=A(P,0,4)))
 if ph=='change':s['resume_play']={}
 if ph in ('play','review','change'):
  s.update(substitute=dict(team=T,slot=I(0,8),player=P,exception=B),set_pitcher=dict(team=T,player=P,exception=B),set_catcher=dict(team=T,player=P),eject=dict(team=T,player=P),forfeit=dict(team=T),suspend={})
 return s
def apply(state,action):
 d=deepcopy(state['data']);p=action['params'];k=action['type'];s=schemas(d);t=d['batting'];defense=1-t
 if k not in s:fail('Action is not permitted in this phase')
 fields(p,s[k],'/params')
 if k in ('play','award_first'):
  if d['pitcher_banned'][defense][d['pitcher'][defense]]:fail('A required pitching change must be completed')
  batter=due(d);before=d['bases'][:];participants=[batter]+before;clear_review(d)
  if batter in before:fail('Next batter cannot already occupy a base')
  if k=='award_first':
   if p['batter']!=batter:fail('Use the next batter in the registered order')
   runs=[]
   if before[0] is not None:
    if before[1] is not None:
     if before[2] is not None:runs.append(before[2])
     d['bases'][2]=before[1];d['temporary'][2]=d['temporary'][1]
    d['bases'][1]=before[0];d['temporary'][1]=d['temporary'][0]
   d['bases'][0]=batter;d['temporary'][0]=None;complete=True
  else:
   kind=p['kind'];dest=p['destinations'];complete=kind!='runner_play'
   if p['batter']!=(batter if complete else None):fail('Batter must match the next slot, or be null for a runner-only play')
   if not complete:participants[0]=None
   for j,x in enumerate(participants):
    if (x is None)!=(dest[j]==-1):fail('Destinations must correspond exactly to participating players')
    if x is not None and dest[j] not in (0,4) and dest[j]<j:fail('A completed play cannot leave a runner behind the occupied starting base')
   remaining=[x for x in dest if 1<=x<=3]
   if len(remaining)!=len(set(remaining)):fail('Two runners cannot finish on the same base')
   if remaining!=sorted(remaining):fail('Surviving runners cannot pass a preceding runner')
   if complete and kind in ('hit','error') and dest[0]<1:fail('A safe batter must reach a base or home')
   if kind in ('out','infield_fly') and dest[0]!=0:fail('The declared batter out must retire the batter')
   if kind=='infield_fly' and (d['outs']>=2 or before[0] is None or before[1] is None):fail('Infield fly requires fewer than two outs and occupied first and second bases')
   if kind=='dropped_third' and before[0] is not None and d['outs']<2:fail('Uncaught third strike cannot permit this batter to run')
   if kind=='home_run' and any(dest[j]!=4 for j,x in enumerate(participants) if x is not None):fail('Over-fence home run must bring every participating runner home')
   new_outs=dest.count(0)
   if d['outs']+new_outs>3:fail('Record only the outs needed to retire the side; later appeals are separate')
   d['outs']+=new_outs;third=p['third_out']
   if (d['outs']==3)!=(third!='none'):fail('Third-out classification must match the out total')
   if third=='left_early' and not d['softball']:fail('Leaving early is a softball third-out classification')
   candidates=[x for j,x in enumerate(participants) if x is not None and dest[j]==4]
   runs=p['credited']
   if len(runs)!=len(set(runs)) or any(x not in candidates for x in runs):fail('Credited runs must be distinct runners who reached home')
   if d['outs']<3 and set(runs)!=set(candidates):fail('Every completed home crossing scores before a third out')
   force=third in ('force','batter_first','left_early')
   if force and runs:fail('This third out cancels every run on the play')
   if kind=='home_run' and set(runs)!=set(candidates):fail('Every home-run crossing must be credited')
   d['last_force']=force;d['last_home_run']=kind=='home_run';d['bases']=[None]*3;d['temporary']=[None]*3
   for j,x in enumerate(participants):
    if x is not None and 1<=dest[j]<=3:d['bases'][dest[j]-1]=x
  d['last_participants']=[x for x in participants if x is not None];d['last_runs']=runs[:];d['score'][t]+=len(runs);d['half_runs']+=len(runs);d['phase']='review'
  if complete:d['next_slot'][t]=(d['next_slot'][t]+1)%9;d['pitcher_locked'][defense]=False
 elif k=='appeal':
  i=p['runner'];cancel=p['cancel_runs']
  if i in d['appealed'] or i not in d['last_participants'] or len(cancel)!=len(set(cancel)) or any(x not in d['last_runs'] for x in cancel):fail('Appeal must refer to the last play and its credited runs')
  if i in d['bases']:j=d['bases'].index(i);d['bases'][j]=None;d['temporary'][j]=None
  d['outs']=min(3,d['outs']+1)
  if d['outs']==3 and p['force']:cancel=d['last_runs'][:];d['last_force']=True
  if i in d['last_runs'] and i not in cancel:fail('A scored runner retired on appeal must lose that run')
  for x in cancel:d['last_runs'].remove(x)
  d['score'][t]-=len(cancel);d['half_runs']-=len(cancel);d['appealed'].append(i)
 elif k=='confirm_play':
  limit=winning_limit(d);lead=d['score'][1]-d['score'][0]
  if t==1 and limit is not None and lead>=limit:
   if not d['last_home_run'] and lead>limit:
    excess=lead-limit
    if excess>len(d['last_runs']):fail('Winning threshold was already passed before the last play')
    d['score'][1]-=excess;d['half_runs']-=excess;d['last_runs']=d['last_runs'][:-excess]
   finish(d,1,'walkoff' if d['inning']>=d['regulation_innings'] else 'run_ahead')
  elif d['outs']==3:
   if t==0 and limit is not None and lead>=limit:finish(d,1,'regulation' if d['inning']>=d['regulation_innings'] else 'run_ahead')
   elif t==1 and limit is not None and abs(lead)>=limit:finish(d,int(lead>0),'regulation' if d['inning']>=d['regulation_innings'] else 'run_ahead')
   else:next_half(d)
  else:d['phase']='play';clear_review(d)
  if d['phase']=='play' and not roster_ok(d):fail('Replace ejected players or declare a forfeit before continuing')
 elif k=='substitute':
  a=p['team'];slot=p['slot'];i=p['player'];old=d['lineup'][a][slot];st=d['status'][a][i]
  reentry=d['softball'] and i<9 and i==slot and d['entries'][a][i]==1 and st=='bench'
  if st!='unused' and not reentry:fail('Incoming player is not eligible for this batting slot')
  if i in d['lineup'][a]:fail('Player already occupies a batting slot')
  if old==d['pitcher'][a] and d['pitcher_locked'][a] and not p['exception']:fail('Pitcher must complete the required batter before replacement')
  if d['status'][a][old]!='ejected':d['status'][a][old]='bench' if d['softball'] and old<9 and d['entries'][a][old]==1 else 'retired'
  d['status'][a][i]='active';d['entries'][a][i]+=1;d['lineup'][a][slot]=i
  if old==d['pitcher'][a]:d['pitcher'][a]=i;d['pitcher_locked'][a]=True;d['visits'][a]=0
  if old==d['catcher'][a]:d['catcher'][a]=i
  if a==t:
   for j,x in enumerate(d['bases']):
    if x==old:d['bases'][j]=i
 elif k=='set_pitcher':
  a=p['team'];i=p['player']
  if i not in d['lineup'][a] or d['status'][a][i]!='active' or d['pitcher_banned'][a][i] or i==d['catcher'][a] or i==d['pitcher'][a]:fail('Choose a different eligible active pitcher')
  if d['pitcher_locked'][a] and not p['exception']:fail('Pitcher must face the required batter')
  d['pitcher_banned'][a][d['pitcher'][a]]=True;d['pitcher'][a]=i;d['pitcher_locked'][a]=True;d['visits'][a]=0
 elif k=='set_catcher':
  a=p['team'];i=p['player']
  if i not in d['lineup'][a] or d['status'][a][i]!='active' or i==d['pitcher'][a]:fail('Catcher must be an active non-pitcher')
  d['catcher'][a]=i
 elif k=='mound_visit':
  a=p['team']
  if a!=defense:fail('Only the fielding team can request a defensive conference')
  d['visits'][a]+=1;d['conferences'][a]+=1
  remove=(d['visits'][a]>=2) if not d['softball'] else (d['conferences'][a]>3 if d['inning']<=7 else d['visits'][a]>1)
  if remove:d['pitcher_banned'][a][d['pitcher'][a]]=True;d['phase']='change'
 elif k=='temporary_runner':
  if not d['softball'] or d['outs']!=2 or d['catcher'][t] not in d['bases']:fail('Temporary runner is available only for a catcher on base with two outs')
  i=d['lineup'][t][(d['next_slot'][t]-1)%9]
  for offset in range(1,10):
   i=d['lineup'][t][(d['next_slot'][t]-offset)%9]
   if i not in d['bases']:break
  j=d['bases'].index(d['catcher'][t]);d['temporary'][j]=d['catcher'][t];d['bases'][j]=i
 elif k=='eject':
  a=p['team'];i=p['player']
  if d['status'][a][i]=='ejected':fail('Player is already ejected')
  d['status'][a][i]='ejected'
  if i in d['lineup'][a] and d['phase']=='play':d['phase']='change'
 elif k=='resume_play':
  if not roster_ok(d) or any(d['pitcher_banned'][a][d['pitcher'][a]] for a in (0,1)):fail('Complete the required lineup and pitching changes')
  d['phase']='play'
 elif k=='forfeit':
  w=1-p['team'];d['score']=[0,0];d['score'][w]=d['regulation_innings'];d['half_runs']=0;clear_review(d);finish(d,w,'forfeit')
 elif k=='suspend':d['saved_phase']=d['phase'];d['phase']='suspended'
 elif k=='resume':d['phase']=d['saved_phase']
 elif k=='official_result':finish(d,p['winner'],'no_contest' if p['winner'] is None else 'official_result')
 return d
def legal(state):
 d=state['data'];s=schemas(d)
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['Inning, batting order, runner destinations and eligibility must permit the event.'],external_observations=['Official completed plays, run timing, appeals, substitutions and pitching exceptions.']) for k,v in s.items()],constraints=dict(phase=d['phase'],inning=d['inning'],batting=d['batting'],outs=d['outs'],bases=d['bases'],batter=due(d),score=d['score'],next_slot=d['next_slot'],pitcher_locked=d['pitcher_locked']),completeness=False,reason='official_completed_diamond_plays')
