"""Safe local rulepack loader, validation and atomic effects."""
from copy import deepcopy
import json
from pathlib import Path
import re
from .values import RuleError, fail, bounded, fields, typed, check_expr, expression, resolve


def load(value):
    if isinstance(value,(str,Path)):
        path=Path(value)
        if path.is_symlink() or not path.is_file(): fail('Expected regular local rulepack file')
        with path.open('rb') as stream: raw=stream.read(1048577)
        if len(raw)>1048576: fail('Rulepack size limit',code='RESOURCE_LIMIT')
        def pairs(items):
            result={}
            for k,v in items:
                if k in result: fail('Duplicate JSON key')
                result[k]=v
            return result
        value=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs)
    bounded(value)
    if len(json.dumps(value,ensure_ascii=False).encode('utf-8'))>1048576: fail('Rulepack size limit',code='RESOURCE_LIMIT')
    return deepcopy(value)


def keys(value, required, optional=()):
    if type(value) is not dict or set(required)-set(value) or set(value)-set(required)-set(optional): fail('Invalid object keys')


def field_spec(spec):
    keys(spec,['type'],['minimum','maximum','minLength','maxLength','minItems','maxItems','values','items','properties','required','nullable'])
    if spec['type'] not in ('integer','number','boolean','string','enum','array','object'): fail('Unknown field type')
    if 'nullable' in spec and type(spec['nullable']) is not bool: fail('Invalid nullable')
    for lo,hi in [('minimum','maximum'),('minLength','maxLength'),('minItems','maxItems')]:
        for k in (lo,hi):
            if k in spec and (type(spec[k]) not in (int,float) or (k not in ('minimum','maximum') and (spec[k]<0 or spec[k]!=int(spec[k])))): fail('Invalid field bound')
        if lo in spec and hi in spec and spec[lo]>spec[hi]: fail('Reversed field bounds')
    if spec['type']=='enum':
        if type(spec.get('values')) is not list or not spec['values']: fail('Empty enum')
    if spec['type']=='array': field_spec(spec.get('items',{}))
    if spec['type']=='object':
        if type(spec.get('properties')) is not dict: fail('Object properties required')
        for v in spec['properties'].values(): field_spec(v)
        if type(spec.get('required',[])) is not list or any(type(k) is not str or k not in spec['properties'] for k in spec.get('required',[])): fail('Invalid required fields')


def spec_path(parts, state_fields, params):
    spec={'type':'object','properties':state_fields}
    for part in parts:
        if spec['type']=='object':
            if part not in spec['properties']: fail('Unknown effect field')
            spec=spec['properties'][part]
        elif spec['type']=='array':
            match=re.fullmatch(r'\{([A-Za-z0-9_]+)\}',part)
            if match:
                p=params.get(match[1],{})
                if p.get('type')!='integer' or p.get('minimum',-1)<0: fail('Unsafe dynamic index')
            elif not re.fullmatch(r'0|[1-9][0-9]*',part): fail('Invalid array index')
            spec=spec['items']
        else: fail('Effect crosses scalar')
    return spec


def check_pack(pack):
    from .schema import validate, PACK_SCHEMA
    validate(pack,PACK_SCHEMA)
    keys(pack,['schema_version','game_id','name','ruleset_id','ruleset_version','family','participants','state','actions','outcomes','provenance'],['variants','capabilities','description'])
    if pack['schema_version']!='1.0': fail('Unknown schema version')
    if type(pack['game_id']) is not str or not re.fullmatch(r'user\.[a-z0-9_.-]{1,74}',pack['game_id']): fail('Reserved or invalid game namespace')
    for k in ('name','ruleset_id','ruleset_version'):
        if type(pack[k]) is not str or not pack[k]: fail('Missing identifier')
    if not pack['ruleset_id'].startswith(pack['game_id']+'.'): fail('Ruleset owner mismatch')
    if pack['family'] not in ('finite_turn','event_scoring','measured_rank','adjudicated','custom'): fail('Unknown family')
    keys(pack['participants'],['min','max'])
    lo,hi=pack['participants']['min'],pack['participants']['max']
    if type(lo) not in (int,float) or type(hi) not in (int,float) or lo!=int(lo) or hi!=int(hi) or not 1<=lo<=hi<=512: fail('Invalid participant bounds')
    if pack.get('variants',{}): fail('Variants not supported by DSL 1.0 runtime')
    keys(pack['state'],['fields','initial'])
    sf=pack['state']['fields']
    if type(sf) is not dict or not sf: fail('State fields required')
    for k,spec in sf.items():
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',k): fail('Invalid field name')
        field_spec(spec)
    fields(pack['state']['initial'],sf,'/state/initial')
    if type(pack['actions']) is not list or not 1<=len(pack['actions'])<=512: fail('Invalid actions')
    names=set(); budget=[2000]
    for action in pack['actions']:
        keys(action,['type','params','when','effects'])
        if type(action['type']) is not str or not action['type'] or action['type'] in names: fail('Duplicate or invalid action type')
        names.add(action['type'])
        if type(action['params']) is not dict: fail('Invalid parameters')
        for k,spec in action['params'].items():
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',k): fail('Invalid parameter name')
            field_spec(spec)
        check_expr(action['when'],budget=budget)
        check_references(action['when'],sf,action['params'])
        if expression_types(action['when'],sf,action['params'])!={'boolean'}: fail('Guard must produce boolean')
        if type(action['effects']) is not list or not 1<=len(action['effects'])<=100: fail('Invalid effects')
        paths=[]
        for effect in action['effects']:
            op=effect.get('op')
            field='by' if op=='inc' else 'index' if op=='remove_at' else 'value'
            keys(effect,['op','path',field])
            if op not in ('set','inc','append','remove_at'): fail('Unknown effect')
            path=effect['path']
            if type(path) is not str or not path.startswith('/') or any(c in path for c in ('..','~','\\')): fail('Unsafe effect path')
            parts=path[1:].split('/'); target=spec_path(parts,sf,action['params'])
            if op=='inc' and target['type'] not in ('integer','number'): fail('Increment requires numeric field')
            if op in ('append','remove_at') and target['type']!='array': fail('Array effect requires array')
            if any(parts[:len(p)]==p or p[:len(parts)]==parts for p in paths): fail('Overlapping effects')
            paths.append(parts); check_expr(effect[field],budget=budget)
            check_references(effect[field],sf,action['params'])
            expression_types(effect[field],sf,action['params'])
    if type(pack['outcomes']) is not list or len(pack['outcomes'])>512: fail('Invalid outcomes')
    for out in pack['outcomes']:
        keys(out,['when','result_kind','winners'],['reason'])
        if out['result_kind'] not in ('win','draw','tie','ranking','disqualification','forfeit','no_contest','technical','other'): fail('Invalid outcome kind')
        if type(out['winners']) is not list: fail('Invalid winners')
        constants=[w for w in out['winners'] if type(w) is not dict]
        if any(type(w) not in (int,float) or w!=int(w) or not 0<=w<hi for w in constants) or len(set(constants))!=len(constants): fail('Invalid winners')
        check_expr(out['when'],budget=budget)
        check_references(out['when'],sf,{})
        if expression_types(out['when'],sf,{})!={'boolean'}: fail('Guard must produce boolean')
        for expr in out['winners']:
            check_expr(expr,budget=budget)
            check_references(expr,sf,{})
            if expression_types(expr,sf,{})!={'number'}: fail('Invalid winners')
    if type(pack['provenance']) is not dict or not all(type(pack['provenance'].get(k)) is str for k in ('basis','verification_status')): fail('Missing provenance')
    return pack


def predicate(expr,state,params,budget):
    result=expression(expr,state,params,budget)
    if type(result) is not bool: fail('Guard must produce boolean')
    return result


def transition(data,action,params,budget):
    result=deepcopy(data); plan=[]
    for effect in action['effects']:
        parts=[]
        for part in effect['path'][1:].split('/'):
            if part.startswith('{'):
                v=params[part[1:-1]]
                if type(v) not in (int,float) or v!=int(v) or v<0: fail('Invalid index')
                part=str(int(v))
            parts.append(part)
        if any(parts[:len(p)]==p or p[:len(parts)]==parts for p,_ in plan): fail('Overlapping resolved effects')
        old=resolve(data,parts); op=effect['op']
        value=expression(effect['by' if op=='inc' else 'index' if op=='remove_at' else 'value'],data,params,budget)
        if op=='inc': value=expression({'op':'add','args':[old,value]}, {},{},budget)
        elif op=='append': value=deepcopy(old)+[value]
        elif op=='remove_at':
            if type(value) not in (int,float) or value!=int(value) or not 0<=value<len(old): fail('Invalid remove index')
            old=deepcopy(old); del old[int(value)]; value=old
        plan.append((parts,value))
    for parts,value in plan:
        parent=resolve(result,parts[:-1]); key=int(parts[-1]) if type(parent) is list else parts[-1]
        parent[key]=deepcopy(value)
    return result


def check_references(expr,state_fields,params):
    """Reject unresolved references when registering, before any action executes."""
    if type(expr) is not dict: return
    if 'ref' in expr:
        scope,*parts=expr['ref'].split('.')
        spec_path(parts,state_fields if scope=='state' else params,{})
    else:
        for arg in expr['args']: check_references(arg,state_fields,params)


def expression_types(expr,state_fields,params):
    from .values import kind
    if type(expr) is not dict: return {kind(expr)}
    if 'ref' in expr:
        scope,*parts=expr['ref'].split('.')
        spec=spec_path(parts,state_fields if scope=='state' else params,{})
        types={kind(v) for v in spec['values']} if spec['type']=='enum' else {'number' if spec['type']=='integer' else spec['type']}
        if spec.get('nullable'): types.add('null')
        return types
    args=[expression_types(a,state_fields,params) for a in expr['args']]; op=expr['op']
    def need(index,allowed):
        if not args[index] or not args[index]<=set(allowed): fail('Expression operand type mismatch')
    if op in ('and','or','not'):
        for i in range(len(args)): need(i,{'boolean'})
        return {'boolean'}
    if op in ('eq','ne'):
        if not args[0]&args[1]: fail('Expression operand type mismatch')
        return {'boolean'}
    if op=='in': need(1,{'array'}); return {'boolean'}
    if op=='len': need(0,{'array','object','string'}); return {'number'}
    need(0,{'number'}); need(1,{'number'})
    return {'boolean'} if op in ('lt','lte','gt','gte') else {'number'}
