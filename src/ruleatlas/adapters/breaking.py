"""Nine-judge, best-of-three individual breaking battle administration."""
from copy import deepcopy
from ..values import fields,fail
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
VOTES=dict(type='array',minItems=9,maxItems=9,items=I(0,1))
SCHEMAS=dict(start_round=dict(first=I(0,1)),start_performance=dict(player=I(0,1)),complete_performance={},record_votes=dict(votes=VOTES),correct_vote=dict(judge=I(0,8),player=I(0,1)),confirm_round={},forfeit=dict(player=I(0,1)),disqualify=dict(player=I(0,1)))
def winner(v):return 1 if sum(v)>=5 else 0
def counts(d):return [sum(winner(v)==i for v in d['rounds']) for i in (0,1)]
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE');wins=counts(d);phase=d['phase']
 if max(wins)>2 or any(max([sum(winner(v)==j for v in d['rounds'][:i]) for j in (0,1)])>=2 for i in range(len(d['rounds']))):bad('No round may follow a second round win')
 if phase=='setup' and (d['first'] is not None or d['completed'] or d['votes'] is not None):bad('New round must await its first performer')
 if phase not in ('setup','finished'):
  if d['first'] is None or d['completed']!=([d['first'],1-d['first']][:len(d['completed'])]):bad('Performance order is inconsistent')
  if phase in ('ready','performing') and len(d['completed'])>=2 or phase in ('judging','round_review') and len(d['completed'])!=2:bad('Judging requires both completed performances')
  if (phase=='round_review')!=(d['votes'] is not None):bad('Votes require round review')
 if phase=='finished':
  if d['winner'] is None or d['reason'] is None:bad('Finished battle needs its result')
  if d['reason']=='two_rounds' and (wins[d['winner']]!=2 or d['first'] is not None or d['completed'] or d['votes'] is not None):bad('Match victory requires two confirmed round wins')
 elif max(wins)>=2 or d['winner'] is not None or d['reason'] is not None:bad('Winning battle must be terminal')
def available(d):
 s={'setup':['start_round'],'ready':['start_performance'],'performing':['complete_performance'],'judging':['record_votes'],'round_review':['correct_vote','confirm_round']}.get(d['phase'],[])
 return s+(['forfeit','disqualify'] if d['phase']!='finished' else [])
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params']
 if k not in available(d):fail('Action is not permitted in this battle phase')
 fields(p,SCHEMAS[k],'/params')
 if k=='start_round':d['first']=p['first'];d['phase']='ready'
 elif k=='start_performance':
  expected=d['first'] if not d['completed'] else 1-d['first']
  if p['player']!=expected:fail('Only the scheduled breaker may perform')
  d['phase']='performing'
 elif k=='complete_performance':
  d['completed'].append(d['first'] if not d['completed'] else 1-d['first']);d['phase']='judging' if len(d['completed'])==2 else 'ready'
 elif k=='record_votes':d['votes']=p['votes'][:];d['phase']='round_review'
 elif k=='correct_vote':d['votes'][p['judge']]=p['player']
 elif k=='confirm_round':
  d['rounds'].append(d['votes'][:]);d.update(first=None,completed=[],votes=None,phase='setup')
  w=winner(d['rounds'][-1])
  if counts(d)[w]==2:d.update(phase='finished',winner=w,reason='two_rounds')
 elif k in ('forfeit','disqualify'):d.update(phase='finished',winner=1-p['player'],reason=k)
 return d
def legal(state):
 d=state['data'];next_player=None if d['first'] is None or len(d['completed'])==2 else d['first'] if not d['completed'] else 1-d['first']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=SCHEMAS[k],preconditions=['Performance order, both completed performances and full jury review must permit the event.'],external_observations=['Official first-performer selection, performance completion and nine final comparative votes.']) for k in available(d)],constraints=dict(phase=d['phase'],round_number=len(d['rounds'])+1 if d['phase']!='finished' else len(d['rounds']),next_performer=next_player,round_wins=counts(d),provisional_round_winner=winner(d['votes']) if d['votes'] is not None else None),completeness=False,reason='official_comparative_breaking_judgments')
def outcome(state,pack):
 d=state['data'];t=d['phase']=='finished';w=d['winner']
 return dict(status='terminal' if t else 'awaiting_adjudication' if d['phase']=='round_review' else 'ongoing',result_kind=('forfeit' if d['reason']=='forfeit' else 'disqualification' if d['reason']=='disqualify' else 'win') if t else 'none',winners=[state['players'][w]['id']] if t else [],losers=[state['players'][1-w]['id']] if t else [],placements=[],reason=d['reason'] if t else 'round_review' if d['phase']=='round_review' else 'ongoing',evidence_required=['Official round confirmation.'] if d['phase']=='round_review' else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if t else None)
