"""Native rule API for accepted built-in profiles and user-defined rulepacks."""
from copy import deepcopy
import itertools
import json
from pathlib import Path
from .values import RuleError, fail, bounded, fields, expression
from .dsl import load, check_pack, predicate, transition
from .builtin import PACKS, ADAPTERS

_REGISTRY={}


def _result(error=None):
    return {'valid':error is None,'scope':'structural','issues':[] if error is None else [dict(code=error.code,path=error.path or '',message=error.message,severity='error')]}


def validate_rules(rules_or_path):
    """Validate a local rulepack without registration or side effects."""
    try: check_pack(load(rules_or_path)); return _result()
    except RuleError as e: return _result(e)
    except (ValueError,TypeError,KeyError,OSError,RecursionError) as e: return _result(RuleError('INVALID_RULEPACK',str(e)))


def register_rules(rules_or_path,overwrite=False):
    """Register a copied user-owned ruleset in this process only."""
    if type(overwrite) is not bool: fail('overwrite must be boolean')
    try: pack=check_pack(load(rules_or_path))
    except RuleError: raise
    except (ValueError,TypeError,KeyError,OSError,RecursionError) as e: fail(str(e))
    key=(pack['game_id'],pack['ruleset_id'],pack['ruleset_version'])
    if key in _REGISTRY:
        if _REGISTRY[key]==pack: return deepcopy(pack)
        # Even explicit overwrite must not change the meaning of pinned states.
        fail('Version is immutable; register a new version',code='RULESET_CONFLICT')
    _REGISTRY[key]=pack
    return deepcopy(pack)


def _select(game_id,ruleset_version=None,ruleset_id=None):
    choices=[p for k,p in _REGISTRY.items() if k[0]==game_id]+[p for p in PACKS.values() if p['game_id']==game_id]
    if not choices: fail('Unknown game',code='UNKNOWN_GAME')
    choices=[p for p in choices if (ruleset_version is None or p['ruleset_version']==ruleset_version) and (ruleset_id is None or p['ruleset_id']==ruleset_id)]
    if not choices: fail('Unknown ruleset',code='UNKNOWN_RULESET')
    if len(choices)!=1: fail('Ambiguous ruleset',code='RULESET_CONFLICT')
    return choices[0]


def unregister_rules(game_id,ruleset_version=None,ruleset_id=None):
    """Remove one unambiguously selected session ruleset."""
    if game_id in PACKS: fail('Built-in rulesets cannot be removed',code='RULESET_CONFLICT')
    try: p=_select(game_id,ruleset_version,ruleset_id)
    except RuleError as e:
        if e.code in ('UNKNOWN_GAME','UNKNOWN_RULESET'): return False
        raise
    del _REGISTRY[(p['game_id'],p['ruleset_id'],p['ruleset_version'])]
    return True


def list_games(include_candidates=False):
    """Return accepted built-ins and registered rules; optionally include candidates."""
    if type(include_candidates) is not bool: fail('include_candidates must be boolean')
    result=[dict(game_id=p['game_id'],name=p['name'],ruleset_id=p['ruleset_id'],ruleset_version=p['ruleset_version'],implementation_status='user_defined') for _,p in sorted(_REGISTRY.items())]
    accepted=[p for p in PACKS.values() if p['profile_record']['implementation_status']=='accepted']
    result.extend(deepcopy(p['profile_record']) | {'game_id':p['game_id']} for p in accepted)
    if include_candidates:
        path=Path(__file__).parent/'data/catalog/target_profiles.json'
        for p in json.loads(path.read_text())['entries']:
            if p['id'] in {g['game_id'] for g in accepted}: continue
            result.append(dict(game_id=p['id'],name=p['name_de'],implementation_status='candidate',supported_actions=[],data_requirements=[],source_status='needs_verification'))
    return result


def get_game(game_id,ruleset_version=None,variant=None,ruleset_id=None):
    """Return isolated metadata for one immutable ruleset."""
    if variant is not None and variant!={}: fail('Unknown variant',code='UNKNOWN_RULESET')
    pack=_select(game_id,ruleset_version,ruleset_id)
    return deepcopy(pack.get('profile_record',pack))


def get_capabilities(game_id,ruleset_version=None,ruleset_id=None):
    """Report implemented operations and limits without trusting pack claims."""
    pack=_select(game_id,ruleset_version,ruleset_id)
    if 'adapter' in pack: return deepcopy(pack['profile_record']['capabilities'])
    return dict(new_state=True,validate_state=True,legal_actions='bounded_enumeration_or_event_types',apply_action=True,outcome=True,validation_scope='structural',max_enumeration=512)


def new_state(game_id,players=None,variant=None,ruleset_version=None,ruleset_id=None):
    """Create a deterministic state with explicitly supplied participant IDs."""
    get_game(game_id,ruleset_version,variant,ruleset_id)
    pack=_select(game_id,ruleset_version,ruleset_id)
    if players is None: fail('Players required',code='MISSING_INFORMATION')
    state=dict(game_id=game_id,ruleset_id=pack['ruleset_id'],ruleset_version=pack['ruleset_version'],variant={},players=deepcopy(players),data=deepcopy(pack['state']['initial']))
    _require(state)
    return state


def _state(state):
    bounded(state)
    required={'game_id','ruleset_id','ruleset_version','variant','players','data'}
    if type(state) is not dict or required-set(state) or set(state)-required-{'metadata'}: fail('State envelope mismatch',code='INVALID_STATE')
    for k in ('game_id','ruleset_id','ruleset_version'):
        if type(state[k]) is not str or not state[k]: fail('Invalid state identity',code='INVALID_STATE')
    pack=_select(state['game_id'],state['ruleset_version'],state['ruleset_id'])
    if type(state['variant']) is not dict or state['variant']: fail('Unknown variant',code='UNKNOWN_RULESET')
    if 'metadata' in state and type(state['metadata']) is not dict: fail('Metadata must be object',code='INVALID_STATE')
    ps=state['players']
    if type(ps) is not list or not pack['participants']['min']<=len(ps)<=pack['participants']['max']: fail('Participant count',code='INVALID_STATE')
    if any(type(p) is not dict or type(p.get('id')) is not str or not p['id'] for p in ps): fail('Invalid participant',code='INVALID_STATE')
    if len({p['id'] for p in ps})!=len(ps): fail('Duplicate participant',code='INVALID_STATE')
    try: fields(state['data'],pack['state']['fields'],'/data')
    except RuleError as e: raise RuleError('INVALID_STATE',e.message,e.path) from e
    if 'adapter' in pack: ADAPTERS[pack['adapter']].validate(state['data'])
    return pack


def validate_state(state):
    """Check structure and custom typed fields; no historical reachability claim."""
    try:
        p=_state(state); _outcome(state,p,[50000]); result=_result()
        if 'adapter' in p: result['scope']=p['profile_record']['capabilities']['validation_scope']
        return result
    except RuleError as e: return _result(e)
    except (ValueError,TypeError,KeyError,RecursionError) as e: return _result(RuleError('INVALID_STATE',str(e)))


def _require(state,budget=None):
    if budget is None: budget=[50000]
    pack=_state(state)
    _outcome(state,pack,budget)
    return pack


def _outcome(state,pack,budget):
    if 'adapter' in pack: return ADAPTERS[pack['adapter']].outcome(state,pack)
    matches=[]
    for i,rule in enumerate(pack['outcomes']):
        if predicate(rule['when'],state['data'],{},budget):
            winners=[expression(e,state['data'],{},budget) for e in rule['winners']]
            if any(type(w) not in (int,float) or w!=int(w) or not 0<=w<len(state['players']) for w in winners) or len(set(winners))!=len(winners): fail('Invalid winners',code='INVALID_STATE')
            winners=[state['players'][int(w)]['id'] for w in winners]
            matches.append(dict(status='terminal',result_kind=rule['result_kind'],winners=winners,losers=[p['id'] for p in state['players'] if p['id'] not in winners] if winners else [],placements=[],reason=rule.get('reason','terminal'),evidence_required=[],rule_id=f"{pack['ruleset_id']}@{pack['ruleset_version']}#outcome/{i}"))
    if len(matches)>1: fail('Conflicting outcome conditions',code='INVALID_STATE')
    return matches[0] if matches else dict(status='ongoing',result_kind='none',winners=[],losers=[],placements=[],reason='ongoing',evidence_required=[],rule_id=None)


def outcome(state):
    """Return stable participant IDs for a uniquely determined terminal result."""
    budget=[50000]; pack=_require(state,budget)
    return _outcome(state,pack,budget)


def apply_action(state,action):
    """Validate and atomically apply one action, leaving all inputs unchanged."""
    return _apply(state,action,[50000])


def _apply(state,action,budget):
    pack=_require(state,budget)
    if _outcome(state,pack,budget)['status']=='terminal': fail('Terminal state',code='ILLEGAL_ACTION')
    try:
        bounded(action)
        if type(action) is not dict or not {'type','params'}<=set(action) or set(action)-{'type','params','actor','metadata'}: fail('Action envelope mismatch')
        if 'metadata' in action and type(action['metadata']) is not dict: fail('Invalid metadata')
        if action.get('actor') is not None and action['actor'] not in [p['id'] for p in state['players']]: fail('Unknown actor')
        if 'adapter' in pack:
            result=deepcopy(state); result['data']=ADAPTERS[pack['adapter']].apply(state,action)
            _require(result,budget)
            return result
        rules=[r for r in pack['actions'] if r['type']==action['type']]
        if not rules: fail('Unknown action')
        rule=rules[0]; params=action['params']; fields(params,rule['params'],'/params')
        if not predicate(rule['when'],state['data'],params,budget): fail('Guard rejected')
        result=deepcopy(state); result['data']=transition(state['data'],rule,params,budget)
        _require(result,budget)
        return result
    except RuleError as e:
        if e.code=='RESOURCE_LIMIT': raise
        raise RuleError('ILLEGAL_ACTION',e.message,e.path) from e


def _domain(spec):
    if spec.get('nullable'): return None
    if spec['type']=='boolean': return [False,True]
    if spec['type']=='enum': return spec['values']
    if spec['type']=='integer' and 'minimum' in spec and 'maximum' in spec:
        import math
        lo,hi=math.ceil(spec['minimum']),math.floor(spec['maximum'])
        if hi-lo<512: return list(range(lo,hi+1))
    return None


def legal_actions(state):
    """Enumerate complete finite domains or expose guarded typed event inputs."""
    budget=[50000]; pack=_require(state,budget)
    result=dict(mode='enumerated',actions=[],action_types=[],constraints={},completeness=True,reason='complete')
    if _outcome(state,pack,budget)['status']=='terminal': result['reason']='terminal'; return result
    if 'adapter' in pack:
        legal=ADAPTERS[pack['adapter']].legal(state)
        if type(legal) is dict: return legal
        result['actions']=legal
        return result
    total=0; domains=[]
    for rule in pack['actions']:
        ds=[_domain(s) for s in rule['params'].values()]
        size=1
        for d in ds: size*=len(d) if d is not None else 513
        total+=size; domains.append(ds)
    if total>512 or any(d is None for ds in domains for d in ds):
        result.update(mode='event_types',completeness=False,reason='parameter_domain_not_enumerable',action_types=[dict(type=r['type'],params_schema=deepcopy(r['params']),preconditions=[json.dumps(r['when'],sort_keys=True,separators=(',',':'))]) for r in pack['actions']])
        return result
    for rule,ds in zip(pack['actions'],domains):
        for values in itertools.product(*ds):
            action=dict(type=rule['type'],params=dict(zip(rule['params'],values)))
            try: _apply(state,action,budget)
            except RuleError as e:
                if e.code=='ILLEGAL_ACTION': continue
                raise
            result['actions'].append(action)
    result['actions'].sort(key=lambda a:json.dumps(a,sort_keys=True,separators=(',',':')))
    return result
