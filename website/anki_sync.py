"""A read-only, cached mirror of JP cards. Anki remains the sole scheduler."""
from config import ANKI_URL, ANKI_ENABLED, require_anki
from pathlib import Path
from datetime import datetime, timezone
from html import unescape
import base64, hashlib, json, re, threading, time, urllib.request

ROOT=Path(__file__).resolve().parents[1]
READ_ACTIONS={'findCards','cardsInfo','retrieveMediaFile','getReviewsOfCards'}

def call_anki(action, **params):
    require_anki()
    if action not in READ_ACTIONS:raise ValueError('Only read-only Anki actions are permitted')
    req=urllib.request.Request(ANKI_URL,data=json.dumps({'action':action,'version':6,'params':params}).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=8) as response:data=json.load(response)
    if data.get('error'):raise RuntimeError(data['error'])
    return data['result']

def plain(value):
    return unescape(re.sub('<[^>]+>','',re.sub(r'<br\s*/?>',' ',value or '',flags=re.I))).strip()

class AnkiMirror:
    def __init__(self, directory=None, caller=call_anki, ttl=25):
        self.directory=Path(directory) if directory else ROOT/'study/anki/website-sync'
        self.caller=caller;self.ttl=ttl;self.lock=threading.Lock();self.last_attempt=None
        self.snapshot=None;self.connected=False
        try:self.snapshot=json.loads((self.directory/'latest.json').read_text())
        except (OSError,ValueError):pass

    def get(self, force=False):
        with self.lock:
            now=time.monotonic()
            if self.last_attempt is not None and now-self.last_attempt<(3 if force else self.ttl):return self.response()
            self.last_attempt=now
            try:
                ids=self.caller('findCards',query='deck:JP')
                cards=[]
                for start in range(0,len(ids),250):cards.extend(self.caller('cardsInfo',cards=ids[start:start+250]))
                # Reject partial results instead of marking unread cards as removed.
                if set(ids)!={c['cardId'] for c in cards}:raise ValueError('Incomplete card read')
                due=self.caller('findCards',query='deck:JP is:due -is:suspended')
                reviewed=self.caller('findCards',query='deck:JP rated:1')
                # If the collection changed midway, retry on the next poll.
                if not set(due+reviewed)<=set(ids):raise ValueError('Collection changed during sync')
                due_set=set(due);reviewed_set=set(reviewed);notes={}
                for c in cards:
                    nid=str(c['note'])
                    if nid not in notes:
                        fields={k:v.get('value','') for k,v in c.get('fields',{}).items()}
                        notes[nid]={'note_id':c['note'],'model':c.get('modelName'),'fields':fields,'cards':[]}
                        if all(k in fields for k in ['日文','释义','课号']):
                            raw=plain(fields['日文']);lesson=plain(fields['课号'])
                            audio=re.search(r'\[sound:([^\]]+)\]',fields.get('音频',''))
                            notes[nid]['vocabulary']={
                                'ruby_source':raw,'word':re.sub(r'\[[^\]]*\]','',raw).replace(' ',''),
                                'reading':re.sub(r'([^\s\[\]]+)\[([^\]]+)\]',lambda m:m[2],raw).replace(' ',''),
                                'meaning':plain(fields['释义']),'part_of_speech':plain(fields.get('词性','')),
                                'lesson_number':int(lesson) if re.fullmatch(r'\d{1,2}',lesson) and 1<=int(lesson)<=48 else None,
                                'audio_filename':audio[1] if audio else None}
                    card={k:c.get(k) for k in ['cardId','deckName','queue','type','due','interval','reps','lapses']}
                    card.update({'is_due':c['cardId'] in due_set,'reviewed_today':c['cardId'] in reviewed_set})
                    notes[nid]['cards'].append(card)
                content={'notes':notes,'due_card_ids':due,'reviewed_card_ids':reviewed}
                revision=hashlib.sha256(json.dumps(content,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                snapshot={**content,'revision':revision,'schema_version':1,'captured_at':datetime.now(timezone.utc).isoformat(),
                          'due_count':len(due),'reviewed_count':len(reviewed),'card_count':len(cards),'note_count':len(notes)}
                self.directory.mkdir(parents=True,exist_ok=True)
                pending=self.directory/'latest.tmp'
                pending.write_text(json.dumps(snapshot,ensure_ascii=False)+'\n',encoding='utf-8')
                pending.replace(self.directory/'latest.json')
                self.snapshot=snapshot;self.connected=True
            except Exception:
                self.connected=False
            return self.response()

    def response(self):
        return {**(self.snapshot or {}),'ok':self.connected,'connected':self.connected,'stale':not self.connected,
                'enabled':ANKI_ENABLED,'has_snapshot':self.snapshot is not None,'poll_seconds':30,'scope':'JP','direction':'anki_to_website',
                'error':None if self.connected else 'Anki 暂未连接；显示上次同步数据，重连后会自动更新。'}

    def audio(self, note_id):
        # Only filenames referenced by a card actually read from the JP scope.
        with self.lock:
            note=(self.snapshot or {}).get('notes',{}).get(str(note_id))
            filename=(note or {}).get('vocabulary',{}).get('audio_filename')
        if not filename or '/' in filename or '\\' in filename:raise ValueError('No safe referenced audio')
        ext=Path(filename).suffix.lower()
        if ext not in {'.mp3','.wav','.ogg','.m4a','.flac'}:raise ValueError('Unsupported audio')
        cache=self.directory/'media'/(hashlib.sha256(filename.encode()).hexdigest()+ext)
        try:
            encoded=self.caller('retrieveMediaFile',filename=filename)
            if not encoded:raise ValueError('Missing audio')
            payload=base64.b64decode(encoded,validate=True)
            cache.parent.mkdir(parents=True,exist_ok=True)
            cache.write_bytes(payload)
            return payload,ext
        except Exception:
            if cache.exists():return cache.read_bytes(),ext
            raise

MIRROR=AnkiMirror()
