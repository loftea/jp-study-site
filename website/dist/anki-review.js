// A view of Anki's native reviewer; no local queue, grading or scheduling.
const labels={1:'重来',2:'困难',3:'良好',4:'简单'};
const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let current=null,busy=false,host=null,onSaved=()=>{},lastDocument='',lastControls='',lastEmpty='',pending=null,inFlight=null,disconnected=false;
try{pending=JSON.parse(sessionStorage.getItem('jp-anki-pending')||'null');}catch{}
function remember(value){pending=value;try{if(value)sessionStorage.setItem('jp-anki-pending',JSON.stringify(value));else sessionStorage.removeItem('jp-anki-pending');}catch{}}
function active(){return host?.isConnected;}
function setText(node,text){if(node.textContent!==text)node.textContent=text;}
function message(text){if(active())setText(host.querySelector('#review-message'),text);}
function lock(value){
 busy=value;if(!active())return;
 const disabled=busy||Boolean(pending)||disconnected;
 host.querySelectorAll('button[data-review]').forEach(b=>{if(b.disabled!==disabled)b.disabled=disabled;});
}
function paint(state){
 current=state;if(!active())return;
 const panel=host.querySelector('#native-card'),actions=host.querySelector('#review-actions');
 setText(host.querySelector('#review-deck'),state.deck||'JP · 原生复习');
 if(state.document){
  lastEmpty='';
  if(state.document!==lastDocument){panel.innerHTML='<iframe class="anki-card-frame" title="Anki 当前复习卡" sandbox="allow-same-origin"></iframe>';panel.firstElementChild.srcdoc=state.document;lastDocument=state.document;}
 }else{const empty=`<div class="review-empty"><span class="seal">記</span><h2>${state.state==='finished'?'这一轮暂时没有待呈现的卡片':state.state==='saving'?'正在确认评分':'在这里完成今天的 Anki'}</h2><p class="muted">${escape(state.message||'保持本机 Anki 打开，网站会接续 JP 牌组的真实复习队列。')}</p></div>`;if(empty!==lastEmpty){panel.innerHTML=empty;lastEmpty=empty;}lastDocument='';}
 let controls='';
 if(state.state==='question')controls='<button class="button" data-review="reveal">显示答案 <small>空格</small></button>';
 else if(state.state==='answer')controls=state.buttons.map((n,i)=>`<button class="button rating rating-${n}" data-review="grade" data-rating="${n}"><span>${escape(labels[n])} <small>${n}</small></span><strong>${escape(state.intervals[i])}</strong></button>`).join('');
 else if(state.state!=='saving')controls=`<button class="button" data-review="start">${state.state==='finished'?'重新读取复习队列':'开始 / 接续复习'}</button>`;
 if(controls!==lastControls){actions.innerHTML=controls;lastControls=controls;}
 lock(busy);
}
async function request(operation,extra={}){
 const action=operation!=='status';
 if(!active()||busy||(pending&&action)||(!action&&inFlight))return;
 const owner=host;
 // Only user actions lock/dim controls. Background reads stay visually silent.
 if(action)lock(true);
 try{
  // A click during polling waits for that read; it must not be silently dropped.
  if(inFlight)await inFlight;
  if(host!==owner||!owner.isConnected)return;
  inFlight=performRequest(operation,extra,owner);
  await inFlight;
 }finally{inFlight=null;if(action)lock(false);}
}
async function performRequest(operation,extra,owner){
 const body={operation,...extra};
 if(operation==='grade'){
  body.request_id=crypto.randomUUID();remember({request_id:body.request_id,card_id:body.card_id});
  message('正在提交你的评分…');
 }
 if(operation==='status'&&pending)body.request_id=pending.request_id;
 try{
  const response=await fetch('/api/anki/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(25000)});
  const result=await response.json();if(!response.ok)throw Error(result.error||'读取失败');
  if(host!==owner||!owner.isConnected)return;
  const recovered=disconnected;disconnected=false;
  const state=result.current||result;
  if(pending&&result.receipt?.status==='saved'){remember(null);message('评分已保存到 Anki。');onSaved();}
  else if(pending&&result.receipt?.status==='rejected'){remember(null);message('Anki 未接受这次评分；请重新查看当前卡。');}
  else if(pending&&result.receipt?.status==='uncertain')message('评分结果不确定，请在 Anki 中核对。不会自动重发评分。');
  else if(pending&&operation==='status'&&!result.receipt&&state.state!=='saving'){
   // Restart lost the bridge receipt. Do not replay a possibly saved grade.
   remember(null);message('Anki 已重新连接，但上次评分回执不可用。请核对当前卡与 Anki 记录；没有重发评分。');
  }else if(!pending&&(recovered||operation!=='status'||host?.querySelector('#review-message')?.textContent==='正在读取当前状态…'))message(state.state==='answer'?'根据自己的回忆情况选择评分。':'与本机 Anki 同步。');
  paint(state);
 }catch(error){
  if(host!==owner||!owner.isConnected)return;
  current=null;disconnected=true;lock(busy);
  message((pending?'评分是否成功尚未确认，不会自动重试。':'')+error.message+' 点击“重新读取”恢复。');
 }
}
export function mountAnkiReview(container,saved){
 host=container;onSaved=saved;lastDocument='';lastControls='';lastEmpty='';current=null;disconnected=false;
 host.innerHTML=`<div class="page-head"><div><span class="eyebrow">ANKI · LIVE REVIEW</span><h1>Anki 复习</h1><p class="muted">同一张卡、同一份记录，由 Anki 安排下次复习。</p></div></div><section class="panel native-review"><div class="review-top"><span class="pill" id="review-deck">JP · 原生复习</span><button class="button secondary small" id="review-refresh">重新读取</button></div><div id="native-card"><p class="loading">正在连接本机 Anki…</p></div><div class="rating-row" id="review-actions"></div><p id="review-message" class="meta review-message" role="status">正在读取当前状态…</p></section><p class="meta review-help">请保持电脑上的 Anki 运行。网页使用 Anki 的出题顺序、每日限额与评分间隔；评分立即写入 Anki。空格显示答案，数字 1–4 选择评分。卡片音频点击播放。</p>`;
 host.querySelector('#review-refresh').onclick=()=>request('status');
 host.onclick=e=>{const b=e.target.closest('[data-review]');if(!b||b.disabled)return;request(b.dataset.review,{...(current?.token?{token:current.token,card_id:current.card_id}:{}),...(b.dataset.rating?{rating:Number(b.dataset.rating)}:{})});};
 request('status');
}
setInterval(()=>{if(active()&&!document.hidden)request('status');},2000);
window.addEventListener('focus',()=>{if(active())request('status');});
document.addEventListener('keydown',e=>{
 if(!active()||busy||pending||e.repeat||e.altKey||e.ctrlKey||e.metaKey||e.target.closest('input,textarea,select,button,[contenteditable]'))return;
 if(e.code==='Space'&&current?.state==='question'){e.preventDefault();request('reveal',{token:current.token,card_id:current.card_id});}
 else if(current?.state==='answer'&&current.buttons.includes(Number(e.key))){e.preventDefault();request('grade',{token:current.token,card_id:current.card_id,rating:Number(e.key)});}
});
