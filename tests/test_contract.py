"""Contract oracles established independently of the interpreter."""
import json
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def test_all_schemas_are_valid():
    for path in (ROOT/'contracts').glob('*.schema.json'):
        Draft202012Validator.check_schema(json.loads(path.read_text()))


def test_contract_inventory_and_errors():
    api = json.loads((ROOT/'contracts/api_contract.json').read_text())
    assert len(api['functions']) == 11
    assert api == json.loads((ROOT/'common/api_inventory.json').read_text())
    error = json.loads((ROOT/'contracts/error.schema.json').read_text())
    assert api['error_codes'] == error['properties']['code']['enum']


def test_public_winners_are_ids():
    schema = json.loads((ROOT/'contracts/outcome.schema.json').read_text())
    result = dict(status='terminal',result_kind='win',winners=['p0'],losers=['p1'],placements=[],reason='score_threshold')
    validator=Draft202012Validator(schema)
    validator.validate(result)
    result['winners']=[0]
    assert not validator.is_valid(result)


def test_examples_match_rulepack_contract():
    schema=json.loads((ROOT/'contracts/rulepack.schema.json').read_text())
    for path in (ROOT/'examples/rulepacks').glob('*.json'):
        Draft202012Validator(schema).validate(json.loads(path.read_text()))


@pytest.mark.parametrize('schema_name,payload',[
 ('state',dict(game_id='user.test',ruleset_id='user.test.standard',ruleset_version='1',variant={},players=[{'id':'ä'}],data={'turn':0})),
 ('action',dict(type='score',params={'player':0})),
 ('validation',dict(valid=False,scope='structural',issues=[dict(code='INVALID_STATE',path='/data',message='Invalid data',severity='error')])),
 ('legal_actions',dict(mode='enumerated',actions=[],action_types=[],constraints={},completeness=True,reason='terminal')),
 ('error',dict(code='ILLEGAL_ACTION',message='Guard rejected',path=None)),
])
def test_payload_oracles(schema_name,payload):
    schema=json.loads((ROOT/'contracts'/f'{schema_name}.schema.json').read_text())
    Draft202012Validator(schema).validate(payload)
    assert json.loads(json.dumps(payload,ensure_ascii=False)) == payload


def test_installed_builtin_profile_metadata_matches_contract():
    import rulesatlas
    schema=json.loads((ROOT/'contracts/profile_record.schema.json').read_text())
    validator=Draft202012Validator(schema)
    for game in rulesatlas.list_games():
        if game['implementation_status']=='accepted':
            validator.validate(rulesatlas.get_game(game['game_id']))


def test_profile_id_namespaces():
    import re
    pattern=json.loads((ROOT/'contracts/profile_record.schema.json').read_text())['properties']['profile_id']['pattern']
    for game_id in ['S001','G105','user.example']:
        assert re.fullmatch(pattern,game_id)
    assert not re.fullmatch(pattern,'userXexample')
