"""JP website review bridge. All scheduling/answering stays in Anki's reviewer.

AnkiConnect dispatches this method on Anki's GUI thread. Card verification and
the native answer call therefore run together without an intervening GUI event.
"""
import importlib
import secrets
import re
from html import escape
import time
from aqt import gui_hooks

class ReviewBridge:
    def __init__(self, ac):
        self.ac=ac;self.fingerprint=None;self.token=None;self.pending=None;self.receipts={}
    def current_key(self):
        if not self.ac.guiReviewActive():return None
        c=self.ac.reviewer().card
        # Profile switching invalidates all issued card tokens.
        return (id(self.ac.collection()),int(c.id),int(c.reps),int(c.mod))
    def latest_review(self,cid):
        return self.ac.collection().db.scalar('select max(id) from revlog where cid=?',cid) or 0
    def snapshot(self):
        if self.pending:
            p=self.pending
            latest=self.latest_review(p['card_id'])
            if latest>p['previous_review'] and self.current_key()!=p['fingerprint']:
                ease=self.ac.collection().db.scalar('select ease from revlog where id=?',latest)
                self.receipts[p['request_id']]={**p,'status':'saved' if ease==p['rating'] else 'uncertain','review_id':latest}
                self.pending=None
            else:
                return {'state':'saving','message':('评分结果尚未确认，请在 Anki 中核对；不会自动重发。' if time.time()-p['submitted_at']>20 else 'Anki 正在保存评分，请勿重复提交。'),'operation':p['request_id']}
        if not self.ac.guiReviewActive():
            self.fingerprint=None;self.token=None
            state=self.ac.window().state
            return {'state':'finished' if state=='overview' else 'idle','message':'点击下方按钮，接续 JP 的原生复习队列。'}
        c=self.ac.guiCurrentCard()
        if not (c['deckName']=='JP' or c['deckName'].startswith('JP::')):
            return {'state':'other_deck','message':'Anki 正在复习其他牌组。点击开始可切换到 JP。'}
        key=self.current_key()
        if key!=self.fingerprint:
            self.fingerprint=key;self.token=secrets.token_urlsafe(24)
        showing=self.ac.reviewer().state=='answer'
        # Resolve Anki's rendered AV references against the current card's AV tags.
        card=self.ac.reviewer().card
        html=c['answer'] if showing else c['question']
        def audio_reference(match):
            tags=card.question_av_tags() if match[1]=='q' else card.answer_av_tags()
            index=int(match[2]);name=getattr(tags[index],'filename',None) if index<len(tags) else None
            return '<audio src="'+escape(name,quote=True)+'"></audio>' if name else '（此音频格式请在 Anki 中播放）'
        html=re.sub(r'\[anki:play:([qa]):(\d+)\]',audio_reference,html)
        # Never return the answer or answer-bearing fields before reveal.
        return {'state':'answer' if showing else 'question','card_id':c['cardId'],'token':self.token,
                'deck':c['deckName'],'template':c['template'],'html':html,
                'css':c['css'],'buttons':c['buttons'] if showing else [],
                'intervals':c['nextReviews'] if showing else [],'connected':True}
    def handle(self,operation='status',token=None,card_id=None,rating=None,request_id=None):
        if operation=='status':
            state=self.snapshot()
            return {'current':state,'receipt':self.receipts.get(request_id)} if request_id else state
        if operation=='start':
            if self.pending:return self.snapshot()
            current=self.snapshot()
            if current['state'] in ('question','answer'):return current
            if not self.ac.guiDeckReview('JP'):raise ValueError('找不到 JP 牌组。')
            return self.snapshot()
        if operation=='grade' and request_id in self.receipts:
            state=self.snapshot()
            return {'receipt':self.receipts[request_id],'current':state}
        if self.pending:return self.snapshot()
        if operation not in ('reveal','grade'):raise ValueError('Unsupported review operation')
        # Refreshing the fingerprint catches desktop answers and same-card reappearance.
        current=self.snapshot()
        if current.get('card_id')!=card_id or not token or token!=self.token:
            raise ValueError('卡片已经变化，请重新读取当前卡，未提交评分。')
        if operation=='reveal':
            if current['state']=='question' and not self.ac.guiShowAnswer():raise ValueError('无法显示答案')
            return self.snapshot()
        if current['state']!='answer':raise ValueError('请先显示答案，再选择评分。')
        if type(rating) is not int or rating not in current['buttons']:raise ValueError('Invalid rating')
        if not isinstance(request_id,str) or not 8<=len(request_id)<=100:raise ValueError('Invalid request ID')
        previous=self.latest_review(card_id)
        pending={'request_id':request_id,'card_id':card_id,'rating':rating,'previous_review':previous,'submitted_at':time.time(),'status':'pending','fingerprint':self.current_key()}
        # Remember the request before invoking native asynchronous scheduling.
        self.pending=pending;self.receipts[request_id]=pending;self.token=None
        try:
            accepted=self.ac.guiAnswerCard(rating)
        except Exception:
            # Never automatically resubmit an ambiguous answer.
            self.receipts[request_id]={**pending,'status':'uncertain'}
            raise
        if not accepted:
            self.pending=None;self.fingerprint=None
            self.receipts[request_id]={**pending,'status':'rejected'}
        state=self.snapshot()
        return {'receipt':self.receipts[request_id],'current':state}

def install(*_args):
    module=importlib.import_module('2055492159')
    ac=module.ac
    if getattr(ac,'jp_web_bridge',None) is None:ac.jp_web_bridge=ReviewBridge(ac)
    @module.util.api()
    def jpWebReview(self,operation='status',token=None,card_id=None,rating=None,request_id=None):
        return self.jp_web_bridge.handle(operation,token,card_id,rating,request_id)
    module.AnkiConnect.jpWebReview=jpWebReview

gui_hooks.profile_did_open.append(install)
