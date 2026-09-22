from pathlib import Path
from datetime import datetime
import tempfile,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'website'))
from anki_calendar import HK,aggregate,AnkiCalendar

def ms(date):return int(datetime.fromisoformat(date).replace(tzinfo=HK).timestamp()*1000)
a=ms('2025-02-14T23:59:59');b=ms('2025-02-15T00:00:01')
rows={'1':[{'id':a,'ease':1,'type':0,'time':1000},{'id':b,'ease':3,'type':1,'time':2000},{'id':b+1,'ease':3,'type':1,'time':3000}], '2':[{'id':b+2,'ease':4,'type':2,'time':4000},{'id':b+3,'ease':0,'type':4,'time':20000}]}
d=aggregate(rows)
assert d['2025-02-14']=={'cards':1,'reviews':1,'seconds':1}
assert d['2025-02-15']=={'cards':2,'reviews':3,'seconds':9}
rows['1'].append(rows['1'][0]);assert aggregate(rows)==d
state={'offline':False,'partial':False}
def caller(action,**params):
 if state['offline']:raise OSError('offline')
 if action=='findCards':assert params['query']=='deck:JP';return [1,2]
 assert action=='getReviewsOfCards'
 return {'1':rows['1']} if state['partial'] else rows
with tempfile.TemporaryDirectory() as temp:
 c=AnkiCalendar(directory=temp,caller=caller,ttl=0)
 first=c.get();assert first['connected'] and first['days']==d
 state['offline']=True
 cached=c.get();assert cached['stale'] and cached['days']==d and cached['captured_at']==first['captured_at']
 restored=AnkiCalendar(directory=temp,caller=caller,ttl=0);assert restored.get()['days']==d
 state.update(offline=False,partial=True);assert c.get()['stale'] and c.get()['days']==d
 state['partial']=False;assert c.get()['connected']
print('PASS: Hong Kong midnight, unique cards vs answer count, manual-entry exclusion, duplicate reviews, offline cache, partial rejection and recovery.')
