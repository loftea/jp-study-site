#!/usr/bin/env python3
"""Verify a clean tracked-files-only copy. No personal data or live integrations."""
from pathlib import Path
import ast, json, os, shutil, subprocess, sys, tempfile, threading, time, urllib.request, urllib.error
ROOT=Path(__file__).resolve().parents[1]

def run(args,cwd,env):
    print('CHECK', ' '.join(args),flush=True)
    subprocess.run(args,cwd=cwd,env=env,check=True,timeout=90)

def main():
    env=os.environ.copy();env.update(JP_ANKI_ENABLED='0',JP_CODEX_ENABLED='0',PYTHONDONTWRITEBYTECODE='1')
    env.pop('JP_ANKI_URL',None);env.pop('JP_CODEX_BIN',None)
    run([sys.executable,'scripts/check_privacy.py'],ROOT,env)
    names=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    with tempfile.TemporaryDirectory(prefix='jp-release-test-') as tmp:
        root=Path(tmp)/'site';root.mkdir()
        for name in filter(None,names):
            p=ROOT/name;q=root/name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
        for p in root.rglob('*.py'):ast.parse(p.read_text(),filename=str(p.relative_to(root)))
        for p in root.rglob('*.json'):json.loads(p.read_text())
        run([sys.executable,'scripts/build_learning_library.py'],root,env)
        for name in ('check_imports.py','check_anki_sync.py','check_anki_calendar.py','check_anki_review.py','check_classroom.py','check_classroom_memory.py','check_supplementary.py','check_study_workflow.py','check_daily_preparation.py'):
            run([sys.executable,'scripts/'+name],root,env)
        node=shutil.which('node')
        if not node:raise RuntimeError('Node is required for release verification')
        for p in sorted((root/'website/dist').glob('*.js')):run([node,'--check',str(p)],root,env)
        for p in sorted((root/'scripts').glob('check_*.mjs')):run([node,'--experimental-vm-modules',str(p)],root,env)
        # Ephemeral loopback HTTP port; child imports only the temporary copy.
        code="import sys;sys.path.insert(0,'website');from serve import Handler,ThreadingHTTPServer;s=ThreadingHTTPServer(('127.0.0.1',0),Handler);print(s.server_port,flush=True);s.serve_forever()"
        with tempfile.TemporaryFile(mode='w+') as log:
            proc=subprocess.Popen([sys.executable,'-u','-c',code],cwd=root,env=env,stdout=subprocess.PIPE,stderr=log,text=True)
            try:
                port=int(proc.stdout.readline().strip());base=f'http://127.0.0.1:{port}'
                for path in ('/','/app.js','/data/library.json','/data/reading-library.json','/data/legacy-classrooms.json','/api/health','/api/classrooms','/api/learning-plan','/api/lesson-progress','/api/daily-preparation','/api/study-workflow','/api/system/status','/api/anki/sync'):
                    with urllib.request.urlopen(base+path,timeout=5) as r:
                        payload=r.read();assert r.status==200,(path,r.status)
                    if path=='/data/legacy-classrooms.json':assert json.loads(payload)==[]
                    if path=='/api/classrooms':assert json.loads(payload)=={'sessions':[],'cli_available':False}
                    if path=='/api/anki/sync':assert not json.loads(payload)['has_snapshot']
                try:urllib.request.urlopen(urllib.request.Request(base+'/api/health',headers={'Host':'example.invalid'}),timeout=5)
                except urllib.error.HTTPError as e:assert e.code==403
                else:raise AssertionError('Foreign Host accepted')
            finally:
                proc.terminate();proc.wait(timeout=5)
        print('PASS: tracked-only rebuild, isolated regressions, JS/Python checks, HTTP startup, disabled live connections, empty learner history.')
if __name__=='__main__':main()
