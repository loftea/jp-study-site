#!/usr/bin/env python3
"""Start one background supervisor; safe to repeat (process lock prevents duplicates)."""
from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    logs=ROOT/'tmp';logs.mkdir(exist_ok=True)
    with (logs/'learning-site-supervisor.log').open('ab') as log:
        p=subprocess.Popen([sys.executable,'-u',str(ROOT/'website/supervise.py')],cwd=str(ROOT),stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
    print('Background supervisor requested:',p.pid)
