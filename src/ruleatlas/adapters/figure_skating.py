"""Seven-judge men's short-program final from official technical-panel sheets."""
from .gymnastics import Gymnastics
from ..values import fail
SLOTS=['axel','solo_jump','combination','flying_spin','single_position_spin','combination_spin','step_sequence']
class FigureSkating(Gymnastics):
 def __init__(self):super().__init__(dict(judges=7))
 def schema(self):
  integer=lambda a,b:dict(type='integer',minimum=a,maximum=b)
  array=lambda x,n:dict(type='array',minItems=n,maxItems=n,items=x)
  props=dict(slot=dict(type='enum',values=SLOTS),base_units=integer(0,10000),bonus=dict(type='boolean'),goe_units=array(integer(-5000,5000),7))
  return dict(elements=dict(type='array',minItems=0,maxItems=7,items=dict(type='object',properties=props,required=list(props))),components=array(array(integer(0,40),7),5),deductions_units=integer(0,10000))
 def validate(self,d):
  super().validate(d)
  for r in d['entrants']:
   m=r['marks']
   if m is None:continue
   es=m['elements'];slots=[e['slot'] for e in es]
   if len(set(slots))!=len(slots):fail('Each short-program element slot may be credited once',code='INVALID_STATE')
   jumps=[e for e in es if e['slot'] in SLOTS[:3]]
   for e in es:
    if min(e['goe_units']) < -e['base_units'] or e['base_units']==0 and any(e['goe_units']):fail('Invalidated elements have zero GOE; no individual negative GOE may exceed base value',code='INVALID_STATE')
    if e['bonus'] and (not jumps or e is not jumps[-1]):fail('Only the final jump element may receive the approved second-half bonus',code='INVALID_STATE')
 def components(self,m):
  tes=sum(((e['base_units']*11+5)//10 if e['bonus'] else e['base_units'])+(sum(sorted(e['goe_units'])[1:-1])+2)//5 for e in m['elements'])
  pcs=sum(sum(sorted(row)[1:-1])*5 for row in m['components'])
  return [tes+pcs-m['deductions_units'],tes]
 def legal(self,state):
  d=state['data']
  return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['Start order, routine completion and review phase must permit the event.'],external_observations=['Official technical-panel base values, converted GOE values, bonus eligibility, component marks and deductions.']) for k,v in self.available(d).items()],constraints=dict(phase=d['phase'],current_participant=self.current(d),score_unit_denominator=100,component_order=['skating_skills','transitions','performance','composition','interpretation']),completeness=False,reason='official_short_program_sheet')
 def outcome(self,state,pack):
  result=super().outcome(state,pack)
  for row in result['placements']:row['score_unit_denominator']=100
  return result
_ENGINE=FigureSkating()
validate=_ENGINE.validate
apply=_ENGINE.apply
legal=_ENGINE.legal
outcome=_ENGINE.outcome
