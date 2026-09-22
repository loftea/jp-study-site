#!/usr/bin/env python3
"""Verified local study backups. Restore only into a new/empty directory."""
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone
import argparse, fcntl, hashlib, json, os, sys, tempfile, zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'website'))
from study_workflow import save
NAMES=('profile.json','state.json','sessions','classrooms','practice','daily-preparation','daily-words','daily-tasks','progress','plans','voice','reminders')

def inventory(root):
    files=[]
    for name in NAMES:
        base=root/'study'/name
        for p in ([base] if base.is_file() else base.rglob('*') if base.exists() else []):
            if p.is_file() and not p.is_symlink() and p.suffix not in ('.tmp','.lock') and not p.name.startswith('.'):
                files.append(p)
    files += list((root/'website/prompts').glob('*'))
    return {str(p.relative_to(root)):(p.stat().st_size,p.stat().st_mtime_ns) for p in sorted(set(files)) if p.is_file() and not p.is_symlink()}

def verify(path,restore_to=None):
    with zipfile.ZipFile(path) as z:
        bad=z.testzip()
        if bad:raise ValueError('备份压缩校验失败：'+bad)
        manifest=json.loads(z.read('manifest.json'))
        names=z.namelist()
        if len(names)!=len(set(names)) or set(names)!=set(manifest['files'])|{'manifest.json'}:raise ValueError('备份清单不匹配')
        for name,digest in manifest['files'].items():
            p=PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or '\\' in name:raise ValueError('备份路径无效')
            if hashlib.sha256(z.read(name)).hexdigest()!=digest:raise ValueError('备份内容校验失败：'+name)
        if restore_to is not None:
            target=Path(restore_to)
            if target.exists() and (not target.is_dir() or any(target.iterdir())):raise ValueError('恢复目录必须为空；不会覆盖现有学习数据')
            target.mkdir(parents=True,exist_ok=True)
            for name in manifest['files']:
                p=target/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(name))
        return manifest

def backup(root=ROOT):
    root=Path(root);destination=root/'backups/study';destination.mkdir(parents=True,exist_ok=True)
    state=root/'study/system/backup-status.json'
    with (destination/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        old=json.loads(state.read_text()) if state.exists() else {}
        try:
            # Retry an inconsistent read; never publish a partial JSON/journal or mixed snapshot.
            for attempt in range(3):
                before=inventory(root);contents={k:(root/k).read_bytes() for k in before}
                if before!=inventory(root):continue
                try:
                    for name,data in contents.items():
                        if name.endswith('.json'):json.loads(data)
                        elif name.endswith('.jsonl'):
                            for line in data.splitlines():
                                if line.strip():json.loads(line)
                except (ValueError,UnicodeError):continue
                break
            else:raise ValueError('学习数据正在变化或包含不完整记录，请稍后重试备份')
            stamp=datetime.now(timezone.utc);manifest={'schema_version':1,'created_at':stamp.isoformat(),'scope':'学习记录、课堂、记忆、音频及教师提示词；不含 Anki 数据库和教材原文件','files':{k:hashlib.sha256(v).hexdigest() for k,v in contents.items()}}
            with tempfile.NamedTemporaryFile(dir=destination,suffix='.tmp',delete=False) as f:temp=Path(f.name)
            try:
                with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as z:
                    for name,data in contents.items():z.writestr(name,data)
                    z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
                verify(temp)
                final=destination/('study-'+stamp.strftime('%Y%m%dT%H%M%S%fZ')+'.zip');os.replace(temp,final)
            finally:temp.unlink(missing_ok=True)
            result={'last_success':stamp.isoformat(),'file':str(final.relative_to(root)),'file_count':len(contents),'sha256':hashlib.sha256(final.read_bytes()).hexdigest(),'error':None}
            save(state,result);return result
        except Exception as e:
            save(state,{**old,'last_attempt':datetime.now(timezone.utc).isoformat(),'error':str(e)[:300]});raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--verify',type=Path);p.add_argument('--restore-to',type=Path);a=p.parse_args()
    if a.restore_to and not a.verify:p.error('--restore-to requires --verify')
    print(json.dumps(verify(a.verify,a.restore_to) if a.verify else backup(a.root),ensure_ascii=False,indent=2))
