#!/usr/bin/env python3
"""User-invoked launcher: reuse the exact local site or start it."""
from pathlib import Path
import json,subprocess,sys,time,urllib.request,webbrowser
url='http://127.0.0.1:8766'
running=False
try:
    with urllib.request.urlopen(url+'/api/health',timeout=2) as response:
        running=json.load(response).get('service')=='jp-study-local'
except Exception:pass
if not running:
    subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'scripts/start_site_background.py')],check=True)
    for _ in range(20):
        try:
            with urllib.request.urlopen(url+'/api/health',timeout=1) as response:
                if json.load(response).get('service')=='jp-study-local':break
        except Exception:time.sleep(.5)
webbrowser.open(url)
