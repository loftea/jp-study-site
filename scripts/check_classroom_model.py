"""Check fresh/resumed CLI options without importing the live classroom singleton."""
import ast
import json
import os
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace

root = Path(__file__).resolve().parents[1]
source = root / 'website/classroom.py'
tree = ast.parse(source.read_text())
function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'cli_reply')
calls = []
sid = '00000000-0000-4000-8000-000000000001'

def run(args, **kwargs):
    calls.append(args)
    assert kwargs['timeout'] == 600
    assert json.loads(kwargs['input'])['kind'] == 'message'
    configs = [args[i+1] for i, arg in enumerate(args[:-1]) if arg == '-c']
    assert 'model="gpt-6.1-sol"' in configs
    assert 'model_reasoning_effort="medium"' in configs
    assert 'approval_policy="never"' in configs
    assert args[args.index('--sandbox')+1] == 'read-only'
    assert '--ignore-user-config' in args and '--output-schema' in args
    events = [{'type':'thread.started', 'thread_id':sid},
              {'type':'item.completed', 'item':{'type':'agent_message', 'text':'{"reply":"ok"}'}},
              {'type':'turn.completed', 'usage':{}}]
    return SimpleNamespace(returncode=0, stdout='\n'.join(map(json.dumps, events)))

env = dict(cli_path=lambda:'/test/codex', tempfile=tempfile, json=json, os=os,
           PROMPTS=root/'website/prompts', UUID=re.compile(r'^[0-9a-f-]{36}$'),
           subprocess=SimpleNamespace(run=run, PIPE=-1, TimeoutExpired=TimeoutError))
exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), env)
for session in ({'lesson_id':'b01', 'messages':[]}, {'lesson_id':'b01', 'cli_thread_id':sid}):
    result = env['cli_reply'](session, {'kind':'message','id':'test','text':'test'}, {})
    assert result[0]['reply'] == 'ok'
assert 'resume' not in calls[0]
assert calls[1][calls[1].index('resume')+1] == sid
print('PASS: pinned model/effort on new and resumed classes; safeguards preserved; no live classroom touched.')
