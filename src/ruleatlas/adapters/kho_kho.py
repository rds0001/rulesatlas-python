"""Traditional nine-minute Kho Kho: official outs and legal batch succession."""
from copy import deepcopy
from ..values import fields,fail
from .handball import outcome
I=lambda a,b:dict(type='integer',minimum=a,maximum=b)
E=lambda *x:dict(type='enum',values=list(x))
T=I(0,1);P=I(0,11);S=I(0,8);B=dict(type='boolean')
def finish(d,w,r='regulation'):d.update(phase='finished',winner=w,reason=r,break_ms=0)
def begin(d):
 d.update(phase='ready',clock_ms=540000,batch=0,defenders=[0,1,2],pending=[],handoffs=0,needs_kho=False,chaser=d['slots'][d['chasing']][8],contact_warned=[[False]*12 for _ in (0,1)])
 if any(d['red'][t][i] for t in (0,1) for i in d['slots'][t]):d['phase']='replacement'
def advance_batch(d):
 d['batch']=(d['batch']+1)%3;d['pending']=list(range(d['batch']*3,d['batch']*3+3));d.update(handoffs=0,needs_kho=True)
def point(d,n=1):
 d['score'][d['chasing']]+=n
 if d['turn']==4 and d['score'][d['chasing']]>d['score'][1-d['chasing']]:finish(d,d['chasing'])
def put_out(d,slot):
 d['defenders'].remove(slot);point(d)
 if not d['defenders'] and not d['pending'] and d['phase']!='finished':advance_batch(d)
def validate(d):
 bad=lambda m:fail(m,code='INVALID_STATE')
 for t in (0,1):
  if len(set(d['slots'][t]))!=9:bad('Nine playing places require distinct registered players')
 if len(set(d['defenders']))!=len(d['defenders']) or len(set(d['pending']))!=len(d['pending']) or set(d['defenders'])&set(d['pending']):bad('Active and pending defending places must be distinct')
 if any(i//3!=d['batch'] for i in d['defenders']+d['pending']):bad('Defenders must belong to the current batch')
 if d['phase']=='ready':
  if d['chaser'] not in d['slots'][d['chasing']] or any(d['red'][t][i] for t in (0,1) for i in d['slots'][t]):bad('Playing teams need an eligible chaser and nine eligible places')
  if not d['clock_ms']:bad('Expired turn must await closure')
  if not d['defenders'] and not d['pending']:bad('Live defense requires a current or entering batch')
 if (d['phase']=='interval')!=(d['break_ms']>0):bad('Interval timer must agree with phase')
 if d['phase']=='finished':
  if d['reason']=='regulation':
   w=None if d['score'][0]==d['score'][1] else int(d['score'][1]>d['score'][0])
   if d['winner']!=w:bad('Result must agree with points')
  elif d['reason']=='innings':
   if d['winner']!=d['first_chaser'] or d['score'][d['winner']]<=d['score'][1-d['winner']]:bad('Innings win requires the first chaser to retain the lead')
 elif d['winner'] is not None or d['reason']!='ongoing':bad('Unfinished match cannot have a result')
def schemas(d):
 ph=d['phase'];s={}
 if ph=='finished':return s
 if ph=='abandoned':return dict(official_result=dict(winner=dict(T,nullable=True)))
 if ph=='pre':s['start_match']=dict(first_chaser=T)
 if ph in ('pre','interval'):s['set_order']=dict(team=T,players=dict(type='array',minItems=9,maxItems=9,items=P))
 if ph=='ready':
  s.update(elapse=dict(ms=I(1,540000)),defender_out=dict(slot=S,kind=E('touch','self_out')),defender_contact=dict(slot=S),correct_kho=dict(player=P),enter_batch=dict(slots=dict(type='array',minItems=1,maxItems=3,items=S)),close_early={},official_stop={})
 if ph=='stopped':s['resume']={}
 if ph in ('ready','stopped','pre','replacement'):
  s.update(substitute=dict(team=T,slot=S,incoming=P),card=dict(team=T,player=P,kind=E('yellow','red')))
 if ph=='replacement':s['resume']={}
 if ph=='turn_end':s['close_turn']={}
 if ph=='follow_choice':s['follow_on']=dict(require=B)
 if ph=='interval':s['elapse_break']=dict(ms=I(1,540000))
 s.update(concede=dict(team=T),abandon={});return s
def apply(state,action):
 d=deepcopy(state['data']);k=action['type'];p=action['params'];ss=schemas(d)
 if k not in ss:fail('Action is not permitted in this phase')
 fields(p,ss[k],'/params');t=d['chasing'];other=1-t
 if k=='start_match':
  if any(d['red'][j][i] for j in (0,1) for i in d['slots'][j]):fail('Replace excluded starters before the match')
  d.update(first_chaser=p['first_chaser'],chasing=p['first_chaser']);begin(d)
 elif k=='set_order':
  if len(set(p['players']))!=9 or set(p['players'])!=set(d['slots'][p['team']]):fail('Batch order must permute the nine current playing places')
  d['slots'][p['team']]=p['players']
 elif k=='elapse':
  if p['ms']>d['clock_ms']:fail('Elapsed time cannot cross turn expiry')
  d['clock_ms']-=p['ms']
  if not d['clock_ms']:d['phase']='turn_end'
 elif k in ('defender_out','defender_contact'):
  slot=p['slot']
  if slot not in d['defenders']:fail('Only a current defender can be put out or warned')
  if k=='defender_out' and p['kind']=='touch' and d['needs_kho']:fail('A correct kho is required before chasing the next batch')
  i=d['slots'][other][slot]
  if k=='defender_contact' and not d['contact_warned'][other][i]:d['contact_warned'][other][i]=True
  else:put_out(d,slot)
 elif k=='correct_kho':
  i=p['player']
  if i==d['chaser'] or i not in d['slots'][t] or d['red'][t][i]:fail('A correct kho passes to another eligible chaser')
  d['chaser']=i;d['needs_kho']=False
  if d['pending']:
   d['handoffs']+=1
   if d['handoffs']==2:
    point(d,len(d['pending']));d['pending']=[]
    if not d['defenders'] and d['phase']!='finished':advance_batch(d)
 elif k=='enter_batch':
  slots=p['slots']
  if len(set(slots))!=len(slots) or any(i not in d['pending'] for i in slots):fail('Only distinct pending places of the prescribed batch may enter')
  d['defenders']=sorted(d['defenders']+slots);d['pending']=[i for i in d['pending'] if i not in slots]
 elif k=='substitute':
  team=p['team'];slot=p['slot'];i=p['incoming'];old=d['slots'][team][slot]
  if i in d['slots'][team] or d['red'][team][i]:fail('Replacement must be an eligible reserve')
  if d['phase']!='pre' and team==other and slot in d['defenders']:fail('A live defender cannot be substituted before being out')
  d['slots'][team][slot]=i
  if d['phase']!='pre' and team==t and old==d['chaser']:d.update(chaser=i,needs_kho=True)
 elif k=='card':
  team=p['team'];i=p['player']
  if d['red'][team][i]:fail('Player is already excluded')
  if p['kind']=='yellow':d['yellow'][team][i]=True
  else:
   d['red'][team][i]=True
   if i in d['slots'][team] and d['phase']!='pre':
    slot=d['slots'][team].index(i)
    if team==other and slot in d['defenders']:put_out(d,slot)
    if d['phase']!='finished':d['phase']='replacement'
 elif k=='resume':
  if any(d['red'][j][i] for j in (0,1) for i in d['slots'][j]):fail('All excluded playing places must be replaced')
  d['phase']='ready'
 elif k=='official_stop':d['phase']='stopped'
 elif k=='close_early':d['phase']='turn_end'
 elif k=='close_turn':
  turn=d['turn']
  if turn==4:finish(d,None if d['score'][0]==d['score'][1] else int(d['score'][1]>d['score'][0]))
  elif turn==3 and d['followed_on'] and d['score'][d['first_chaser']]>d['score'][1-d['first_chaser']]:finish(d,d['first_chaser'],'innings')
  elif turn==2:
   lead=d['score'][d['first_chaser']]-d['score'][1-d['first_chaser']]
   d['phase']='follow_choice'
   if lead!=9:
    d['followed_on']=lead>9;d['chasing']=1-d['first_chaser'] if lead>9 else d['first_chaser'];d.update(turn=3,phase='interval',break_ms=540000)
  else:d.update(turn=turn+1,chasing=1-t,phase='interval',break_ms=300000)
 elif k=='follow_on':d.update(followed_on=p['require'],chasing=1-d['first_chaser'] if p['require'] else d['first_chaser'],turn=3,phase='interval',break_ms=540000)
 elif k=='elapse_break':
  if p['ms']>d['break_ms']:fail('Elapsed time exceeds the interval')
  d['break_ms']-=p['ms']
  if not d['break_ms']:begin(d)
 elif k=='concede':finish(d,1-p['team'],'concession')
 elif k=='abandon':d.update(phase='abandoned',break_ms=0)
 elif k=='official_result':finish(d,p['winner'],'no_contest' if p['winner'] is None else 'official')
 return d
def legal(state):
 d=state['data']
 return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['Current phase, eligibility and prescribed batch order must permit the event.'],external_observations=['Official legal outs, correct kho handovers, sanctions and elapsed time.']) for k,v in schemas(d).items()],constraints={k:d[k] for k in ('phase','turn','clock_ms','score','chasing','batch','defenders','pending','chaser','needs_kho','followed_on')},completeness=False,reason='traditional_kho_kho_league_protocol')
