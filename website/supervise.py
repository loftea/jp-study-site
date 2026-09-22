#!/usr/bin/env python3
"""Local detached supervisor. Restarts the site, never replays interrupted classroom turns."""
from pathlib import Path
from datetime import datetime,timezone
import fcntl,json,os,signal,subprocess,sys,time,urllib.request
ROOT=Path(__file__).resolve().parents[1]
def healthy():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8766/api/health',timeout=2) as r:return json.load(r).get('service')=='jp-study-local'
    except Exception:return False

def main():
    logs=ROOT/'tmp';logs.mkdir(exist_ok=True)
    with (logs/'learning-site-supervisor.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return
        lock.seek(0);lock.truncate();lock.write(str(os.getpid()));lock.flush()
        stopping=False;child=None
        def stop(*_):
            nonlocal stopping
            stopping=True
            if child and child.poll() is None:child.terminate()
        signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
        with (logs/'learning-site.log').open('ab') as out:
            while not stopping:
                if healthy():time.sleep(5);continue
                env={**os.environ,'JP_SITE_MANAGED':'1','JP_SITE_MANAGER':'supervisor','PYTHONPYCACHEPREFIX':'/private/tmp/jp-site-pycache'}
                child=subprocess.Popen([sys.executable,'-u',str(ROOT/'website/serve.py')],cwd=str(ROOT),env=env,stdout=out,stderr=out)
                started=time.monotonic();code=child.wait()
                print(datetime.now(timezone.utc).isoformat(),'site exited',code,flush=True)
                if not stopping:time.sleep(3 if time.monotonic()-started>30 else 10)
if __name__=='__main__':main()
