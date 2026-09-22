"""Read-only daily review calendar for cards currently in JP, Hong Kong civil days."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json, threading, time
from anki_sync import call_anki, ROOT

HK=timezone(timedelta(hours=8))

def aggregate(reviews):
    days={}; seen=set()
    for cid,rows in reviews.items():
        for row in rows:
            # Manual scheduling/rescheduling entries are not actual answer events.
            if row.get('ease') not in (1,2,3,4) or row.get('type') not in (0,1,2,3):continue
            rid=int(row['id'])
            if rid in seen:continue
            seen.add(rid)
            day=datetime.fromtimestamp(rid/1000,HK).date().isoformat()
            d=days.setdefault(day,{'cards':set(),'reviews':0,'time_ms':0})
            d['cards'].add(str(cid));d['reviews']+=1;d['time_ms']+=max(0,int(row.get('time',0)))
    return {day:{'cards':len(d['cards']),'reviews':d['reviews'],'seconds':round(d['time_ms']/1000)} for day,d in sorted(days.items())}

class AnkiCalendar:
    def __init__(self,directory=None,caller=call_anki,ttl=30):
        self.directory=Path(directory) if directory else ROOT/'study/anki/calendar'
        self.caller=caller;self.ttl=ttl;self.lock=threading.Lock();self.last_attempt=None;self.snapshot=None;self.connected=False
        try:self.snapshot=json.loads((self.directory/'latest.json').read_text())
        except (OSError,ValueError):pass
    def get(self):
        with self.lock:
            tick=time.monotonic()
            if self.last_attempt is None or tick-self.last_attempt>=self.ttl:
                self.last_attempt=tick
                try:
                    ids=self.caller('findCards',query='deck:JP');reviews={}
                    for start in range(0,len(ids),500):
                        batch=ids[start:start+500];part=self.caller('getReviewsOfCards',cards=batch)
                        if set(map(str,batch))!=set(part):raise ValueError('Partial history')
                        reviews.update(part)
                    snap={'days':aggregate(reviews),'captured_at':datetime.now(timezone.utc).isoformat(),'scope':'JP','timezone':'Asia/Hong_Kong'}
                    self.directory.mkdir(parents=True,exist_ok=True)
                    tmp=self.directory/'latest.tmp';tmp.write_text(json.dumps(snap,ensure_ascii=False)+'\n');tmp.replace(self.directory/'latest.json')
                    self.snapshot=snap;self.connected=True
                except Exception:self.connected=False
            return {**(self.snapshot or {}),'connected':self.connected,'has_snapshot':self.snapshot is not None,
                    'stale':not self.connected,'today':datetime.now(HK).date().isoformat()}

CALENDAR=AnkiCalendar()
