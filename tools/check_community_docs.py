"""Offline documentation checks: local links, example YAML/Jinja and bounded setpoints.

Examples are checked without creating HA automations or invoking any device action.
The template checks are a focused offline model, not HA's full configuration schema.
"""
import json
import re
from pathlib import Path
from urllib.parse import unquote,urlsplit
import yaml
from jinja2.nativetypes import NativeEnvironment

ROOT=Path(__file__).resolve().parents[1]


def walk_templates(value,environment):
    if isinstance(value,dict):
        for child in value.values():walk_templates(child,environment)
    elif isinstance(value,list):
        for child in value:walk_templates(child,environment)
    elif isinstance(value,str) and ('{{' in value or '{%' in value):
        environment.parse(value)


def main():
    paths=[ROOT/name for name in ('README.md','SELF_SERVICE_COMMANDES.md','CONTRIBUTING.md','THIRD_PARTY_NOTICES.md','SECURITY.md')]
    paths+=sorted((ROOT/'docs').glob('*.md'))+[ROOT/'examples/README.md']
    env=NativeEnvironment()
    examples=[]
    links=0
    for path in paths:
        text=path.read_text(encoding='utf-8')
        if text.count('```')%2:raise ValueError('Unclosed fence: '+path.name)
        for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',text):
            parsed=urlsplit(target)
            if parsed.scheme or not parsed.path:continue
            destination=(path.parent/unquote(parsed.path)).resolve()
            if not destination.exists():raise ValueError(f'{path.name}: missing {target}')
            links+=1
        for language,block in re.findall(r'```(\w+)\n(.*?)```',text,re.S):
            if language=='yaml':
                data=yaml.safe_load(block)
                walk_templates(data,env)
                if path.name=='USE_CASES.md':examples.append(data)
            elif language=='json':json.loads(block)
    if len(examples)!=2:raise ValueError('Expected the two documented automation examples')
    # Check the exact setpoint expression from the document against both directions,
    # both bounds and a missing current target. No HA service is executed here.
    climate=examples[1]
    condition=climate['actions'][1]['value_template']
    request=climate['actions'][2]['variables']['requested']
    clamp=climate['actions'][3]['data']['temperature']
    vectors=[(20.,'increase',20.5),(20.,'decrease',19.5),(5.,'decrease',5.),(30.,'increase',30.)]
    for current,direction,expected in vectors:
        context=dict(current=current,minimum=5.,maximum=30.,step=.5,trigger={'id':direction})
        assert env.from_string(condition).render(**context) is True
        context['requested']=env.from_string(request).render(**context)
        assert env.from_string(clamp).render(**context)==expected
    assert env.from_string(condition).render(current=None,minimum=5.,maximum=30.) is False
    for data,name in zip(examples,('automation-laundry.yaml','automation-thermostat.yaml')):
        target=ROOT/'examples'/name
        target.write_text('# Replace all IDs/entities before using this example. Generated from docs/USE_CASES.md.\n'+yaml.safe_dump(data,sort_keys=False,allow_unicode=True),encoding='utf-8')
    report=dict(passed=True,documents=len(paths),local_links=links,automation_examples=2,
                setpoint_vectors=len(vectors),missing_setpoint_rejected=True,ha_calls=0)
    (ROOT/'docs/assets/documentation-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':
    main()
