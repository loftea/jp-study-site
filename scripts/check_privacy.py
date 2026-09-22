#!/usr/bin/env python3
"""Scan tracked content and reachable Git blobs without printing matched secrets.
Heuristic checks supplement, rather than replace, review of the release file list.
"""
from pathlib import Path
import argparse, re, subprocess
ROOT=Path(__file__).resolve().parents[1]
PATTERNS={
    'private_key':r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
    'service_token':r'\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{20,}|AKIA[A-Z0-9]{16})\b',
    'home_path':r'(?:/Users/|/home/)[A-Za-z0-9._-]+|[A-Z]:\\Users\\[^\\\s]+',
    'email':r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
    'jwt':r'\beyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\b',
    'credential_literal':r'''(?i)(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password)\s*[=:]\s*["'][A-Za-z0-9_+/=-]{16,}["']''',
}
FORBIDDEN=('study/','books/','backups/','tmp/','output/','website/dist/data/','website/dist/reading/','website/dist/audio/','website/dist/images/','.codex/')
ALLOWED_SUFFIXES={'.py','.js','.mjs','.md','.json','.html','.css','.svg','.example'}

def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def scan_text(label,payload,patterns,findings):
    try:text=payload.decode('utf8')
    except UnicodeDecodeError:findings.append((label,0,'binary_file'));return
    for kind,pattern in patterns.items():
        for m in re.finditer(pattern,text):findings.append((label,text.count('\n',0,m.start())+1,kind))

def scan(extra=()):
    findings=[];patterns=dict(PATTERNS)
    for n,s in enumerate(extra):patterns[f'private_marker_{n+1}']=re.escape(s)
    names=git('ls-files','-z').decode().split('\0');names=[n for n in names if n]
    for name in names:
        p=ROOT/name
        if name.startswith(FORBIDDEN) or (p.suffix not in ALLOWED_SUFFIXES and name not in ('.gitignore','LICENSE')):
            findings.append((name,0,'excluded_path'))
        if p.is_symlink():findings.append((name,0,'symlink'));continue
        if not p.exists():findings.append((name,0,'missing_file'));continue
        scan_text(name,p.read_bytes(),patterns,findings)
        # Scan staged blobs as well as the current file.
        scan_text('index:'+name,git('show',':'+name),patterns,findings)
    commits=git('rev-list','--all').decode().splitlines()
    blobs=set()
    for line in git('rev-list','--objects','--all').decode().splitlines():
        oid=line.split(' ',1)[0]
        if git('cat-file','-t',oid).strip()==b'blob':blobs.add(oid)
    for oid in blobs:scan_text('history:'+oid[:12],git('cat-file','blob',oid),patterns,findings)
    for name,line,kind in findings:print(f'{name}:{line}: {kind}')
    print(f'Privacy scan: {len(names)} tracked files, {len(commits)} commits, {len(blobs)} historical blobs, {len(findings)} findings; matched values suppressed.')
    return not findings
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--deny-file',type=Path,help='Private local list, one additional literal per line; do not commit it')
    a=p.parse_args();extra=[s.strip() for s in a.deny_file.read_text().splitlines() if s.strip()] if a.deny_file else []
    raise SystemExit(0 if scan(extra) else 1)
