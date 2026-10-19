"""Classic eighteen-a-side Australian football with four unrestricted interchange players."""
from copy import deepcopy
from ..values import fields,fail
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
TEAM=I(0,1);SLOT=I(0,21)
SCHEMAS=dict(set_lineup=dict(team=TEAM,players=dict(type='array',minItems=18,maxItems=18,items=SLOT)),start_quarter={},score=dict(team=TEAM,player=dict(SLOT,nullable=True),kind=dict(type='string',enum=['goal','behind'])),interchange=dict(team=TEAM,out=SLOT,**{'in':SLOT}),sound_siren={},award_after_siren_kick=dict(team=TEAM,player=SLOT),resolve_after_siren_kick=dict(kind=dict(type='string',enum=['goal','behind','none'])),end_quarter={},concede=dict(team=TEAM),abandon={},official_result=dict(winner=dict(TEAM,nullable=True)))
def total(d):return [6*d['goals'][i]+d['behinds'][i] for i in (0,1)]
def finish(d,w,reason):d.update(phase='finished',winner=w,reason=reason,pending_kick=None)
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 if any(len(set(x))!=18 for x in d['lineups']):bad('Each side requires eighteen distinct active players')
 if d['phase']=='pre_match' and (d['quarter']!=1 or any(d['goals']) or any(d['behinds'])):bad('Unstarted match has no scoring history')
 if d['phase']=='interval' and d['quarter']>=4:bad('There is no interval after the fourth quarter')
 if d['pending_kick'] is not None and d['phase']!='siren':bad('After-siren kick requires a completed playing period')
 if d['pending_kick'] is not None and d['pending_kick']['player'] not in d['lineups'][d['pending_kick']['team']]:bad('Pending kicker must be active')
 if d['phase']=='finished':
  if d['reason'] is None or d['reason'] not in ('draw','official') and d['winner'] is None:bad('Finished match requires a result')
  scores=total(d)
  if d['reason']=='points' and (d['quarter']!=4 or scores[d['winner']]<=scores[1-d['winner']]):bad('Points victory requires completed regulation and a lead')
  if d['reason']=='draw' and (d['quarter']!=4 or scores[0]!=scores[1] or d['winner'] is not None):bad('Draw requires tied regulation totals')
 elif d['winner'] is not None or d['reason'] is not None:bad('Open match cannot retain a result')
 if d['expiry_decided'] and d['phase'] not in ('siren','finished','abandoned'):bad('Expiry decision belongs to a completed quarter')
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];phase=d['phase']
 if k not in SCHEMAS:fail('Unknown Australian football event')
 fields(p,SCHEMAS[k],'/params')
 if phase=='finished' or phase=='abandoned' and k!='official_result':fail('Match is not open')
 if k=='set_lineup':
  if phase!='pre_match' or len(set(p['players']))!=18:fail('Set eighteen distinct starters before the match')
  d['lineups'][p['team']]=p['players']
 elif k=='start_quarter':
  if phase not in ('pre_match','interval'):fail('No quarter is ready to begin')
  if phase=='interval':d['quarter']+=1
  d.update(phase='play',expiry_decided=False)
 elif k=='score':
  if phase!='play' or p['player'] is None and p['kind']=='goal' or p['player'] is not None and p['player'] not in d['lineups'][p['team']]:fail('Official score requires live play and an active player')
  d['goals' if p['kind']=='goal' else 'behinds'][p['team']]+=1
 elif k=='interchange':
  if phase not in ('play','interval'):fail('Interchange requires a playing quarter or interval')
  line=d['lineups'][p['team']]
  if p['out'] not in line or p['in'] in line:fail('Interchange pairs an active player and a bench player')
  line[line.index(p['out'])]=p['in']
 elif k=='sound_siren':
  if phase!='play':fail('Only an active quarter can reach its siren')
  d['phase']='siren'
 elif k=='award_after_siren_kick':
  if phase!='siren' or d['pending_kick'] is not None or d['expiry_decided'] or p['player'] not in d['lineups'][p['team']]:fail('Only one eligible unresolved after-siren kick may be awarded')
  d['pending_kick']=deepcopy(p);d['expiry_decided']=True
 elif k=='resolve_after_siren_kick':
  if d['pending_kick'] is None:fail('No after-siren kick is pending')
  if p['kind']!='none':d['goals' if p['kind']=='goal' else 'behinds'][d['pending_kick']['team']]+=1
  d['pending_kick']=None
 elif k=='end_quarter':
  if phase!='siren' or d['pending_kick'] is not None:fail('Sound the siren and resolve any after-siren kick before closing the quarter')
  if d['quarter']<4:d.update(phase='interval',expiry_decided=False)
  else:
   scores=total(d);finish(d,None if scores[0]==scores[1] else 0 if scores[0]>scores[1] else 1,'draw' if scores[0]==scores[1] else 'points')
 elif k=='concede':finish(d,1-p['team'],'concession')
 elif k=='abandon':d.update(phase='abandoned',pending_kick=None)
 elif k=='official_result':
  if phase!='abandoned':fail('External competition result requires abandonment')
  finish(d,p['winner'],'official')
 return d
def legal(state):
 d=state['data'];phase=d['phase'];names=dict(pre_match=['set_lineup','start_quarter'],play=['score','interchange','sound_siren'],interval=['interchange','start_quarter'],siren=['resolve_after_siren_kick'] if d['pending_kick'] is not None else ['end_quarter']+([] if d['expiry_decided'] else ['award_after_siren_kick']),abandoned=['official_result'],finished=[])[phase]
 if phase not in ('finished','abandoned'):names+=['concede','abandon']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=SCHEMAS[k],preconditions=['Quarter, active lineup and after-siren entitlement must permit the event.'],external_observations=['Official goals, behinds, completed quarter siren, awarded mark/free kick and its final score.']) for k in names],constraints=dict(phase=phase,quarter=d['quarter'],totals=total(d),active=d['lineups'],bench=[[i for i in range(22) if i not in line] for line in d['lineups']],pending_kick=d['pending_kick']),completeness=False,reason='official_classic_australian_football_events')
def outcome(state,pack):
 d=state['data'];done=d['phase']=='finished';w=d['winner'];abandoned=d['phase']=='abandoned'
 return dict(status='terminal' if done else 'awaiting_adjudication' if abandoned else 'ongoing',result_kind=('draw' if w is None else 'win') if done else 'none',winners=[state['players'][w]['id']] if done and w is not None else [],losers=[state['players'][1-w]['id']] if done and w is not None else [],placements=[],reason=d['reason'] if done else 'competition_result_required' if abandoned else 'ongoing',evidence_required=['Official competition result.'] if abandoned else [],rule_id=pack['ruleset_id']+'@'+pack['ruleset_version'] if done else None)
