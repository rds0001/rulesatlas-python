"""Weighted five-judge category finals with official marks and neutral penalties."""
from .gymnastics import Gymnastics
class PanelFinal(Gymnastics):
 def schema(self):
  mark=dict(type='array',minItems=5,maxItems=5,items=dict(type='integer',minimum=0,maximum=10000))
  return dict({name:mark for name in self.c['weights']},penalty=dict(type='integer',minimum=0,maximum=100000))
 def components(self,m):
  total=sum(weight*sum(sorted(m[name])[1:-1]) for name,weight in self.c['weights'].items())
  return [max(0,total-m['penalty']*30)]
 def legal(self,state):
  d=state['data']
  return dict(mode='event_types',actions=[],action_types=[dict(type=k,params_schema=v,preconditions=['Start order, routine completion and review phase must permit the event.'],external_observations=['Five official marks per category and official neutral deductions in thousandths.']) for k,v in self.available(d).items()],constraints=dict(phase=d['phase'],current_participant=self.current(d),score_unit_denominator=30000,category_weights=self.c['weights']),completeness=False,reason='official_weighted_panel_judgments')
 def outcome(self,state,pack):
  result=super().outcome(state,pack)
  for row in result['placements']:row['score_unit_denominator']=30000
  return result
