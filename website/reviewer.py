"""HTTP facade for the native Anki reviewer. No scheduling algorithms here."""
from config import ANKI_URL, require_anki
import base64, json, re, threading, urllib.request
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlencode

def call_review(**params):
    require_anki()
    req=urllib.request.Request(ANKI_URL,data=json.dumps({'action':'jpWebReview','version':6,'params':params}).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=20) as response:data=json.load(response)
    if data.get('error'):raise ValueError(data['error'])
    return data['result']

class SafeCard(HTMLParser):
    """Retain card layout/ruby, but never run scripts or load remote resources."""
    allowed={'div','span','p','br','hr','b','i','em','strong','u','small','sub','sup','ruby','rt','rp','table','tbody','thead','tr','td','th','ul','ol','li','h1','h2','h3','h4','audio','source','img'}
    def __init__(self,token):super().__init__();self.token=token;self.output=[];self.hidden=0;self.media=set()
    def url(self,name):
        if not name or '/' in name or '\\' in name or ':' in name:return None
        self.media.add(name);return '/api/anki/review/media?'+urlencode({'token':self.token,'name':name})
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','iframe','object'):self.hidden+=1;return
        if self.hidden or tag not in self.allowed:return
        clean=[]
        for k,v in attrs:
            if k in ('class','id','colspan','rowspan','lang','title','alt'):clean.append((k,v or ''))
            elif k=='src' and tag in ('img','audio','source'):
                url=self.url(v)
                if url:clean.append(('src',url))
        if tag=='audio':clean.extend([('controls',''),('preload','none')])
        self.output.append('<'+tag+''.join(' '+k+'="'+escape(v,quote=True)+'"' for k,v in clean)+'>')
    def handle_endtag(self,tag):
        if tag in ('script','style','iframe','object'):self.hidden=max(0,self.hidden-1);return
        if not self.hidden and tag in self.allowed:self.output.append('</'+tag+'>')
    def handle_data(self,data):
        if self.hidden:return
        pos=0
        for match in re.finditer(r'\[sound:([^\]]+)\]',data):
            self.output.append(escape(data[pos:match.start()]));url=self.url(match[1])
            if url:self.output.append('<audio controls preload="none" src="'+escape(url,quote=True)+'"></audio>')
            pos=match.end()
        self.output.append(escape(data[pos:]))

class Reviewer:
    def __init__(self,caller=call_review):self.caller=caller;self.lock=threading.Lock();self.media={}
    def request(self,params):
        with self.lock:
            raw=self.caller(**params)
            state=raw.get('current',raw)
            if state.get('html'):
                parser=SafeCard(state['token']);parser.feed(state.pop('html'));parser.close()
                self.media={state['token']:parser.media}
                # CSS runs only in a sandboxed iframe under restrictive CSP.
                css=state.pop('css','').replace('</','<\\/')
                state['document']='<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src http://127.0.0.1:8766 http://localhost:8766; media-src http://127.0.0.1:8766 http://localhost:8766"><style>'+css+'\nbody{margin:0;padding:30px 18px;background:white!important;color:#182d49!important;font-size:24px;line-height:1.8;font-family:-apple-system,\"Hiragino Sans\",sans-serif}img{max-width:100%;height:auto}audio{display:block;width:100%;max-width:360px;margin:18px auto}rt{font-size:.55em}</style></head><body class="card">'+''.join(parser.output)+'</body></html>'
            return raw
    def media_file(self,token,name):
        with self.lock:
            if name not in self.media.get(token,set()):raise ValueError('Unknown card media')
        require_anki()
        req=urllib.request.Request(ANKI_URL,data=json.dumps({'action':'retrieveMediaFile','version':6,'params':{'filename':name}}).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=8) as response:data=json.load(response)
        if data.get('error') or not data.get('result'):raise ValueError('Media unavailable')
        return base64.b64decode(data['result'],validate=True)

REVIEWER=Reviewer()
