"""Isolated synchronization tests. Never edits or grades actual Anki cards."""
from pathlib import Path
import copy, json, sys, tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'website'))
from anki_sync import AnkiMirror

card={'cardId':1,'note':10,'modelName':'Words','deckName':'JP::标日::初级','queue':2,'type':2,'reps':3,'lapses':1,
      'due':12,'interval':4,'fields':{k:{'value':v} for k,v in {'日文':'手帳[てちょう]','释义':'记事本','课号':'02','词性':'名','音频':'[sound:techo.mp3]'}.items()}}
cards=[card];due=[1];reviewed=[];calls=[];offline=False;partial=False
def fake(action,**params):
    calls.append(action)
    if offline:raise ConnectionError('offline')
    if action=='findCards':
        if 'is:due' in params['query']:return list(due)
        if 'rated:1' in params['query']:return list(reviewed)
        return [c['cardId'] for c in cards]
    if action=='cardsInfo':return [] if partial else copy.deepcopy(cards)
    if action=='retrieveMediaFile':return 'SUQzVGVzdA=='
    raise AssertionError('Unexpected write or API action')
with tempfile.TemporaryDirectory(prefix='jp-sync-test-') as temp:
    mirror=AnkiMirror(temp,caller=fake,ttl=0)
    one=mirror.get();assert one['connected'] and one['due_count']==1
    assert one['notes']['10']['vocabulary']['word']=='手帳'
    original_revision=one['revision']
    card['fields']['释义']['value']='随身记事本';card['queue']=-1;due=[];reviewed=[1]
    two=mirror.get();assert two['revision']!=original_revision and two['reviewed_count']==1
    assert two['notes']['10']['vocabulary']['meaning']=='随身记事本'
    assert mirror.audio(10)[0]==b'ID3Test'
    offline=True;old=mirror.get();assert old['stale'] and old['captured_at']==two['captured_at'] and old['reviewed_count']==1
    assert mirror.audio(10)[0]==b'ID3Test'
    restarted=AnkiMirror(temp,caller=fake,ttl=0);assert restarted.get()['stale']
    offline=False;partial=True;assert mirror.get()['stale']
    partial=False;cards=[];reviewed=[];empty=mirror.get();assert empty['connected'] and empty['note_count']==0
    assert json.loads((Path(temp)/'latest.json').read_text())['notes']=={}
    assert not set(calls)-{'findCards','cardsInfo','retrieveMediaFile'}
print('PASS: changed fields, suspended/reviewed cards, offline cache, recovery, removed cards, partial-read rejection, audio and read-only action boundary.')
