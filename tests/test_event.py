import json
from pathlib import Path
import pytest
import ruleatlas as r
ROOT=Path(__file__).resolve().parents[1]
PACK=ROOT/'common/rulepacks/timed_duel.json'
CASES=json.loads((ROOT/'common/golden/timed_duel.json').read_text())
@pytest.mark.parametrize('case',CASES['cases'],ids=lambda c:c['id'])
def test_event_pilot(case):
    r.register_rules(PACK)
    s=r.new_state('user.timed_duel',players=CASES['players']); s['data']=case['initial_data']
    assert r.validate_state(s)['valid']
    out=r.outcome(s)
    for expected,actual in [('expected_status','status'),('expected_winners','winners'),('expected_kind','result_kind')]:
        if expected in case: assert out[actual]==case[expected]
    if 'expected_mode' in case: assert r.legal_actions(s)['mode']==case['expected_mode']
    if 'action' in case:
        if 'expected_error' in case:
            with pytest.raises(r.RuleError) as e: r.apply_action(s,case['action'])
            assert e.value.code==case['expected_error']
        else: assert r.apply_action(s,case['action'])['data']==case['expected_data']
