"""Single-dance final tabulated by strict majority skating rules 5 to 8."""
from copy import deepcopy
from ..values import fields,fail
COUPLE=dict(type='integer',minimum=0,maximum=5)
JUDGE=dict(type='integer',minimum=0,maximum=4)
ORDER=dict(type='array',minItems=1,maxItems=6,items=COUPLE)
def eligible(d):return [i for i,s in enumerate(d['status']) if s=='eligible']
def settle(d):
 d['phase']='review' if not eligible(d) or all(b is not None for b in d['ballots']) else 'judging'
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE');ids=eligible(d)
 for ballot in d['ballots']:
  if ballot is not None and sorted(ballot)!=ids:bad('Each judge must rank every eligible couple exactly once')
 if d['phase'] in ('setup','dancing') and any(b is not None for b in d['ballots']):bad('Judging follows the completed dance')
 complete=not ids or all(b is not None for b in d['ballots'])
 if d['phase']=='judging' and complete or d['phase'] in ('review','finished') and not complete:bad('Judging phase and available ballots disagree')
 if d['phase']=='dancing' and not ids:bad('A dance needs an eligible couple')
def schemas(d):
 phase=d['phase'];s={}
 if phase=='setup':s['start_dance']={};s['withdraw']=dict(couple=COUPLE)
 if phase=='dancing':s.update(complete_dance={},authorized_restart={},withdraw=dict(couple=COUPLE))
 if phase=='judging':s['record_ballot']=dict(judge=JUDGE,order=ORDER)
 if phase=='review':
  s['confirm_result']={}
  if eligible(d):s['correct_ballot']=dict(judge=JUDGE,order=ORDER)
 if phase!='finished':s['disqualify']=dict(couple=COUPLE)
 return s
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];s=schemas(d)
 if k not in s:fail('Action is not permitted in this phase')
 fields(p,s[k],'/params')
 if k=='start_dance':
  d['phase']='dancing' if eligible(d) else 'review'
 elif k=='complete_dance':settle(d)
 elif k=='authorized_restart':d['phase']='setup'
 elif k in ('withdraw','disqualify'):
  i=p['couple']
  if d['status'][i]!='eligible':fail('Only an eligible couple can receive this status')
  d['status'][i]='dq' if k=='disqualify' else 'dns' if d['phase']=='setup' else 'dnf'
  if d['phase'] in ('judging','review'):
   d['ballots']=[None]*5;settle(d)
  elif d['phase']=='dancing' and not eligible(d):d['phase']='review'
 elif k in ('record_ballot','correct_ballot'):
  j=p['judge']
  if k=='record_ballot' and d['ballots'][j] is not None:fail('Judge already submitted a ballot')
  if sorted(p['order'])!=eligible(d):fail('Rank each eligible couple once, without ties or omissions')
  d['ballots'][j]=p['order'][:];settle(d)
 elif k=='confirm_result':d['phase']='finished'
 return d
def ranking(d):
 ids=eligible(d)
 if not ids:return []
 ranks={i:[b.index(i)+1 for b in d['ballots']] for i in ids};remaining=ids[:];column=1;place=1;result=[]
 while remaining:
  group=[i for i in remaining if sum(r<=column for r in ranks[i])>=3]
  if group:
   # All majorities in this column precede couples requiring a later column.
   def key(i):return tuple(x for c in range(column,len(ids)+1) for x in (-sum(r<=c for r in ranks[i]),sum(r for r in ranks[i] if r<=c)))
   group.sort(key=lambda i:(key(i),i))
   while group:
    tied=[i for i in group if key(i)==key(group[0])];mean_twice=2*place+len(tied)-1
    for i in tied:result.append(dict(couple=i,place=place,placement_numerator=mean_twice,placement_denominator=2));remaining.remove(i);group.remove(i)
    place+=len(tied)
  column+=1
 return result
def legal(state):
 d=state['data']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=s,preconditions=['Dance completion, eligibility and ballot status must permit the event.'],external_observations=['Official strict judge rankings and participation decisions.']) for k,s in schemas(d).items()],constraints=dict(phase=d['phase'],eligible_couples=eligible(d),judges_remaining=[i for i,b in enumerate(d['ballots']) if b is None],majority=3),completeness=False,reason='official_dance_rankings')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';rows=ranking(d) if done else [];w=[state['players'][r['couple']]['id'] for r in rows if r['place']==1]
 return dict(status='terminal' if done else 'awaiting_adjudication' if d['phase']=='review' else 'ongoing',result_kind=('ranking' if rows else 'no_contest') if done else 'none',winners=w,losers=[p['id'] for p in state['players'] if p['id'] not in w] if w else [],placements=[dict(player_id=state['players'][r['couple']]['id'],**{k:v for k,v in r.items() if k!='couple'}) for r in rows],reason='confirmed_skating_result' if done else 'result_review' if d['phase']=='review' else 'ongoing',evidence_required=['Official result confirmation.'] if d['phase']=='review' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
