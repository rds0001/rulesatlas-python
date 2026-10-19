"""Validator for the fixed, bundled RuleAtlas JSON Schema keyword subset."""
import json
from pathlib import Path
import re
from .values import equal,kind,fail,RuleError
PACK_SCHEMA=json.loads((Path(__file__).parent/'data/contracts/rulepack.schema.json').read_text())

def validate(value,schema,root=None,path=''):
    if root is None: root=schema
    def reject(): fail('Schema mismatch',path)
    if '$ref' in schema:
        ref=schema['$ref']
        if not ref.startswith('#/'): fail('External schema references forbidden')
        target=root
        for part in ref[2:].split('/'): target=target[part]
        return validate(value,target,root,path)
    if 'oneOf' in schema:
        matches=0
        for candidate in schema['oneOf']:
            try: validate(value,candidate,root,path); matches+=1
            except RuleError: pass
        if matches!=1: reject()
    if 'const' in schema and not equal(value,schema['const']): reject()
    if 'enum' in schema and not any(equal(value,x) for x in schema['enum']): reject()
    k=kind(value)
    if 'type' in schema:
        types=schema['type'] if type(schema['type']) is list else [schema['type']]
        if not any(t==k or (t=='integer' and k=='number' and value==int(value)) for t in types): reject()
    if k=='number':
        if ('minimum' in schema and value<schema['minimum']) or ('maximum' in schema and value>schema['maximum']): reject()
    if k=='string':
        if len(value)<schema.get('minLength',0) or len(value)>schema.get('maxLength',1048576): reject()
        if 'pattern' in schema and not re.search(schema['pattern'],value): reject()
    if k=='array':
        if len(value)<schema.get('minItems',0) or len(value)>schema.get('maxItems',50000): reject()
        if 'items' in schema:
            for i,v in enumerate(value): validate(v,schema['items'],root,f'{path}/{i}')
    if k=='object':
        if len(value)<schema.get('minProperties',0) or set(schema.get('required',[]))-set(value): reject()
        props=schema.get('properties',{})
        for key,v in value.items():
            if key in props: validate(v,props[key],root,path+'/'+key)
            elif schema.get('additionalProperties') is False: reject()
            elif type(schema.get('additionalProperties')) is dict: validate(v,schema['additionalProperties'],root,path+'/'+key)
