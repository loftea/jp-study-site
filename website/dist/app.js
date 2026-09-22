import {annotatedText,japaneseText} from './annotated-text.js';
import {mountWorkflow,mountServiceStatus,mountLessonStatus} from './study-dashboard.js';
import {mountDailyPreparation} from './daily-preparation.js';
import {mountPractice,mountPreclassCard} from './practice.js';
import {mountReviewCalendar} from './review-calendar.js';
import {mountClassroom,classroomRecords,mountClassroomMemory} from './classroom.js';
import {mountReading,updateReadingPart} from './reading-library.js';
import {mountTextbookExercises} from './textbook-exercises.js';
import {mountAnkiReview} from './anki-review.js';
import {mergeAnkiVocabulary} from './anki-sync.js';
const $ = (s, root=document) => root.querySelector(s);
const app = $('#app');
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let db, audio, viewTab='basic_text', wordPage=0, localAPI=false, liveAnki=null;
let wordQuery='', wordVolume='all', wordStatus='all';
let sourceWords=[], syncPending=false, syncRevision=null, updateWordResults=null;
const normalize = s => s.normalize('NFKC').replace(/[\s。、，,.!?！？]/g,'');
const ruby = annotatedText;
const wordRuby = w => esc(w.ruby_source).replace(/([^\s\[\]]+)\[([^\]]+)\]/g,'<ruby>$1<rt>$2</rt></ruby>');
const sourceRuby = (line,segments) => segments ? segments.map(s => s.reading && s.reading !== s.text ? `<ruby>${esc(s.text)}<rt>${esc(s.reading)}</rt></ruby>` : esc(s.text)).join('') : japaneseText(line);
const statusLabel = w => w.assessment==='needs_review'?'待巩固':w.assessment==='correct_in_written_recall'?'曾回忆正确':'未测评';
const lessonLink = id => `#lesson/${id}`;
const heading = (label,title,description='') => `<div class="page-head"><div><span class="eyebrow">${label}</span><h1>${title}</h1>${description?`<p class="muted">${description}</p>`:''}</div></div>`;
function toast(text){$('#toast').textContent=text;$('#toast').classList.add('visible');setTimeout(()=>$('#toast').classList.remove('visible'),3500);}
function play(path,fallback){if(audio)audio.pause();audio=new Audio(path);audio.play().catch(()=>{if(fallback){toast('Anki 音频暂不可用，播放教材副本。');play(fallback);}else toast('音频未能播放，请重新点击。');});}
function ankiLabel(w){return ({due:'到期',suspended:'已暂停',reviewed_today:'今日已答',new:'新卡',scheduled:'已排期',missing_or_outside_jp:'已删除或移出JP'})[w.anki_status]||'尚未同步';}
function wordTable(words,{showLesson=true}={}){
 return `<div class="table-wrap"><table class="vocab-table"><thead><tr><th>词汇 / 读音</th><th>释义</th>${showLesson?'<th class="desktop-only">课次</th>':''}<th>音频</th><th class="desktop-only">学习证据</th></tr></thead><tbody>${words.map(w=>`<tr data-word-id="${esc(w.id)}"><td class="japanese" lang="ja">${wordRuby(w)}</td><td>${esc(w.meaning)}<div class="meta">${esc(w.part_of_speech)}</div></td>${showLesson?`<td class="desktop-only"><a class="text-link" href="${lessonLink(w.lesson_id)}">第 ${w.lesson_number} 课</a></td>`:''}<td>${w.audio?`<button class="play" data-audio="${esc(w.audio)}" data-fallback-audio="${esc(w.fallback_audio||'')}" aria-label="播放${esc(w.word)}的${w.anki_synced_at?'Anki':'共享牌组'}音频">▶</button>`:'<span class="meta">暂无</span>'}</td><td class="desktop-only"><span class="pill ${w.assessment==='needs_review'?'warn':''}">${statusLabel(w)}</span><div class="meta anki-word-state">Anki：${ankiLabel(w)}</div></td></tr>`).join('')}</tbody></table></div>`;
}
function today(){
 app.innerHTML=heading('YOUR STUDY DESK','今天，从这里继续','先复习到期卡，再学词汇与句型；最后听读、跟读和对话。')+
 `<div class="grid-two"><section class="panel continue" id="daily-preparation"><p class="muted">正在根据最新学习记录准备今日安排…</p></section><section class="panel"><span class="eyebrow">ANKI REVIEW</span><h2 style="margin-top:10px">先完成到期复习</h2><div id="anki-status"><p class="muted">正在自动连接本机 Anki…</p></div><div class="actions"><a class="button" href="#review">进入 Anki 复习 →</a><button class="button secondary" id="anki-refresh">立即同步</button></div><p class="meta" style="margin-top:12px">启用本机连接并打开 Anki 后，每约 30 秒同步一次。默认离线，配置方式见 README。</p></section></div>
 <section class="panel leisure-entry" id="preclass-card"></section>
 <section class="panel" id="daily-workflow"></section>
 <section class="panel"><h2>学习记录</h2><p class="muted">进度依据本机真实作答生成。演示材料不代表已经学习或掌握。</p><a class="text-link" href="#progress">查看记录 →</a></section>`;
 mountWorkflow($('#daily-workflow'));
 mountDailyPreparation($('#daily-preparation'),{esc,ruby});
 mountPreclassCard($('#preclass-card'),{esc});
 $('#anki-refresh').addEventListener('click',()=>refreshAnki(true));
 if(liveAnki)renderAnki();
}
async function refreshAnki(force=false){
 if(!localAPI||syncPending)return;
 syncPending=true;const b=$('#anki-refresh');if(b){b.disabled=true;b.textContent='同步中…';}
 try{
  const r=await fetch('/api/anki/sync'+(force?'?force=1':''),{cache:'no-store',signal:AbortSignal.timeout(60000)});
  if(!r.ok)throw Error('连接失败');const d=await r.json();liveAnki=d;
  if(d.has_snapshot&&d.revision!==syncRevision){
   const merged=mergeAnkiVocabulary(sourceWords,d);db.vocabulary=merged.words;syncRevision=d.revision;
   db.lessons.forEach(l=>l.vocabulary_ids=db.vocabulary.filter(w=>w.lesson_id===l.id).map(w=>w.id));
   liveAnki.matched_words=merged.matched;
   const hash=location.hash||'#today';
   if(hash.startsWith('#words')&&updateWordResults)updateWordResults();
   else{
    // Update only vocabulary tables. Never rerender a learner's answer form,
    // clear their search box, reset audio playback or jump their scroll position.
    document.querySelectorAll('tr[data-word-id]').forEach(row=>{
     const w=db.vocabulary.find(w=>w.id===row.dataset.wordId);if(!w)return;
     const host=document.createElement('div');host.innerHTML=wordTable([w],{showLesson:row.cells.length===5});
     row.replaceWith(host.querySelector('tbody tr'));
    });
   }
  }
 }catch(e){liveAnki={...(liveAnki||{}),connected:false,stale:true,error:'暂时无法连接同步服务，保留上次同步数据。'};}
 finally{syncPending=false;renderAnki();const button=$('#anki-refresh');if(button){button.disabled=false;button.textContent='立即同步';}}
}
function renderAnki(){
 let badge=$('#sync-badge');if(!badge){badge=document.createElement('span');badge.id='sync-badge';badge.className='sync-badge';badge.setAttribute('role','status');$('.topbar').append(badge);}
 const stamp=liveAnki?.captured_at?new Date(liveAnki.captured_at).toLocaleString('zh-CN'):null;
 const connected=liveAnki?.connected;
 if(liveAnki?.enabled===false){badge.textContent='Anki 连接未启用';badge.classList.add('offline');badge.title='默认不访问真实卡组';const el=$('#anki-status');if(el)el.innerHTML='<p class="notice">当前为离线模式。启用 Anki 连接后才读取你的 JP 牌组，配置方式见项目 README。</p>';return;}
 badge.textContent=connected?'Anki 自动同步 · '+new Date(liveAnki.captured_at).toLocaleTimeString('zh-CN'):'Anki 未连接'+(stamp?' · 旧快照':'');
 badge.classList.toggle('offline',!connected);badge.title=stamp?'上次成功同步：'+stamp+'；页面使用期间约每30秒同步。':'打开本机 Anki 后自动重试。';
 const el=$('#anki-status');if(!el)return;
 if(!liveAnki?.has_snapshot){el.innerHTML='<p class="muted">尚无当前同步数据。请打开电脑上的 Anki，网站会自动重试。</p>';return;}
 const current=connected?'当前到期卡':'上次同步时到期卡';
 el.innerHTML=`${!connected?'<p class="notice">Anki 暂未连接，以下为旧快照；重连后自动更新。</p>':''}<div class="metric-row" style="grid-template-columns:1fr 1fr;margin:12px 0"><div><strong style="font-size:30px">${liveAnki.due_count}</strong><div class="meta">${current}</div></div><div><strong style="font-size:30px">${liveAnki.reviewed_count}</strong><div class="meta">${connected?'Anki 学习日已答卡':'快照当日已答卡'}</div></div></div><p class="meta">同步于 ${esc(stamp)}<br>${liveAnki.note_count} 条 JP 笔记 · 包含词汇和错题</p>`;
}

function library(){
 if(db.demo){app.innerHTML=heading('LEARNING LIBRARY','演示学习库','仅含原创示例，不附带标日教材。导入自己的材料后可使用完整阅读和练习功能。')+db.lessons.map(l=>`<section class="panel"><h2>${esc(l.title_raw)}</h2><a class="button" href="#lesson/${l.id}">打开示例</a></section>`).join('');return;}
 app.innerHTML=heading('TEXTBOOK LIBRARY','教材书架','初级上下册，按 48 课组织。每课保留文本来源、词汇对应与校对状态。')+
 `<div class="book-grid">${[['初级上','01–24','b01'],['初级下','25–48','b25']].map(([name,range,id])=>`<a class="book" href="#lesson/${id}"><div class="book-spine">${name}</div><div class="book-info"><span class="eyebrow">STANDARD JAPANESE</span><h2>新版中日交流标准日本语</h2><p class="muted">第 ${range} 课 · 课文 / 对话 / 词汇</p><span class="pill">打开教材 →</span></div></a>`).join('')}</div>
 <section class="panel leisure-entry"><div><span class="eyebrow">VOCABULARY WORKBOOK</span><h2>标准日语初级词汇 · 刷词手册</h2><p class="muted">48 课词汇与练习 · 12 组单元测试 · N4 / N5 模拟题 · 参考答案与原书插图</p></div><a class="button" href="#reading/vocab-workbook">打开刷词手册 →</a></section><section class="panel leisure-entry"><div><span class="eyebrow">BEYOND THE TEXTBOOK</span><h2>读一点日本历史与文化</h2><p class="muted">《日本通史（全六册）》与《日本文化史（第2版）》已加入课外书架，可直接阅读。</p></div><a class="button secondary" href="#reading">打开课外书架 →</a></section><div class="section-heading"><h2>按课查找</h2></div><div class="toolbar"><input id="lesson-search" class="search" placeholder="搜索课号或课文标题" aria-label="搜索课次"><select id="lesson-volume" class="select" aria-label="选择册别"><option value="all">初级上下册</option><option>初级上</option><option>初级下</option></select></div><div id="lesson-results" class="panel"></div>
 <div class="section-heading"><h2>配套资料与来源</h2></div><div class="panel"><p>初级词汇牌组包含 <strong>${db.counts.vocabulary}</strong> 个词条和 <strong>${db.counts.audio}</strong> 段音频。词汇刷词手册现可按课阅读，并查阅原书参考答案。</p><div class="actions"><a href="#reference/ocr" class="button secondary">初级上扫描文本</a><a href="#reference/workbook" class="button secondary">词汇刷词手册</a></div><p class="notice">EPUB 转写有错字，且不含纸书全部讲解和练习；扫描识别也尚未逐页校对。原书 PDF 仍保留供核对。中级不在本次整理范围内。</p><details class="details"><summary>查看教材来源与处理状态</summary>${db.sources.map(s=>`<p><strong>${esc(s.title)}</strong><br><span class="meta">${esc(s.path)}<br>${esc((s.limitations||[]).join('；'))}</span></p>`).join('')}</details></div>`;
 function update(){const q=$('#lesson-search').value.trim().toLowerCase(),v=$('#lesson-volume').value;const list=db.lessons.filter(l=>(v==='all'||l.volume===v)&&(`${l.number} ${l.title_raw}`.toLowerCase().includes(q)));$('#lesson-results').innerHTML=list.length?list.map(l=>`<a href="#lesson/${l.id}" style="display:flex;justify-content:space-between;gap:12px;padding:14px 0;border-bottom:1px solid var(--line)"><span><span class="meta">${l.volume} · 第 ${l.number} 课</span><br><span lang="ja">${sourceRuby(l.title_raw,l.title_segments)}</span></span><span class="meta">${l.vocabulary_ids.length} 词　→</span></a>`).join(''):'<p class="empty">没有匹配的课次。</p>';}
 $('#lesson-search').oninput=update;$('#lesson-volume').onchange=update;update();
}
function lesson(id){
 const l=db.lessons.find(l=>l.id===id);if(!l){notFound();return;}
 $('#breadcrumb').textContent=`教材书架 / ${l.volume} / 第 ${l.number} 课`;
 app.innerHTML=`<div class="lesson-layout"><nav class="lesson-menu" aria-label="课次">${db.lessons.filter(x=>x.volume===l.volume).map(x=>`<a href="#lesson/${x.id}" class="${x.id===id?'active':''}">第 ${x.number} 课<small>${esc(x.title_raw)}</small></a>`).join('')}</nav><article><div class="page-head"><div><span class="eyebrow">${l.volume} · LESSON ${String(l.number).padStart(2,'0')}</span><h1 lang="ja" style="line-height:1.8">${sourceRuby(l.title_raw,l.title_segments)}</h1><span class="pill" id="lesson-status">正在核对进度</span></div></div><div class="panel"><div class="tabs" role="tablist" aria-label="教材内容">${[['basic_text','基本课文'],['dialogue','应用对话'],['vocabulary','本课词汇'],['grammar','句型讲解'],['exercises','配套练习']].map(([key,title])=>`<button role="tab" aria-selected="${viewTab===key}" class="tab ${viewTab===key?'active':''}" data-tab="${key}">${title}</button>`).join('')}</div><div id="lesson-content" role="tabpanel"></div></div><div class="page-nav">${l.number>1?`<a class="button secondary" href="#lesson/b${String(l.number-1).padStart(2,'0')}">← 上一课</a>`:'<span></span>'}${l.number<48?`<a class="button secondary" href="#lesson/b${String(l.number+1).padStart(2,'0')}">下一课 →</a>`:''}</div></article></div>`;
 document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{viewTab=b.dataset.tab;lesson(id)});
 mountLessonStatus($('#lesson-status'),id);
 const target=$('#lesson-content');
 if(viewTab==='vocabulary')target.innerHTML=`<div class="actions"><a class="button secondary" href="#reference/workbook?lesson=${l.number}">本课刷词手册 →</a></div><p class="meta">${l.vocabulary_ids.length} 个词项 · 读音及音频来自已导入共享牌组。</p>${wordTable(db.vocabulary.filter(w=>w.lesson_id===id),{showLesson:false})}`;
 else if(viewTab==='grammar')target.innerHTML=(l.grammar.length?l.grammar.map(gid=>grammarCard(db.grammar.find(g=>g.id===gid))).join(''):'<div class="source-note">这一课的语法讲解尚未校对整理。原书语法页另列为参考，不作为已审核讲义。</div>')+(l.scan_reference?`<div class="actions"><a class="button secondary" href="#reference/ocr?page=${l.scan_reference.grammar_pages[0]}">查看本课原书语法页（待校对）</a></div>`:'<p class="meta">本课暂无更多讲解。</p>');
 else if(viewTab==='exercises'){target.innerHTML='<div id="textbook-exercises"></div>'+`<details class="details"><summary>教练补充练习</summary>${l.exercises.length?exerciseList(db.exercises.filter(e=>l.exercises.includes(e.id))):'<p class="meta">本课尚未配置补充练习。</p>'}</details>`;mountTextbookExercises($('#textbook-exercises'),l,{esc,ruby,localAPI});bindExercises();}
 else if(db.demo){target.innerHTML='<p class="source-note">原创演示内容，非标日课文。</p>'+l.sections.filter(s=>s.kind===viewTab).flatMap(s=>s.paragraphs).map(p=>`<p class="prose">${japaneseText(p)}</p>`).join('');}
 else{const s=l.sections.filter(s=>s.kind===viewTab);target.innerHTML=(s.every(x=>x.reviewed_reading)?'<div class="source-note">来源：初级上第二版 PDF。已核对本页课文文字并补充注音；原 EPUB 转写保留在下方，便于追溯。</div>':'<div class="source-note">来源：初级上下册 EPUB 转写本。原文待校对；辅助注音匹配已有词表，未能确认的读音暂不添加。原文中的错字和原有注音仍待校对。</div>')+s.map(section=>`${section.reviewed_reading?`<p class="pill good">以下课文已按第二版原页核对 · 书本第 ${section.reviewed_reading.printed_page} 页</p>`:''}<div class="prose" lang="ja">${section.reviewed_reading?section.reviewed_reading.paragraphs.map(p=>`<p>${japaneseText(p)}</p>`).join(''):section.paragraphs.map((p,i)=>`<p>${sourceRuby(p,section.reading_segments?.[i])}</p>`).join('')}</div><details class="details"><summary>查看原始文字与出处</summary><p class="meta">${esc(section.source_member)}</p><pre>${esc(section.paragraphs.join('\n'))}</pre></details>`).join('');}
}
function grammarCard(g){return `<section class="exercise"><span class="pill">${g.source_type==='original_recovery_supplement'?'恢复训练 · 补充内容':'教练编写讲解'}</span><h2 style="margin-top:14px">${esc(g.title)}</h2><p>${ruby(g.explanation)}</p><div class="prose" lang="ja">${g.examples.map(x=>`<p>${ruby(x)}</p>`).join('')}</div>${g.note?`<p class="meta">${esc(g.note)}</p>`:''}</section>`;}
function words(mode){
 if(mode==='daily'){app.innerHTML=heading('DAILY VOCABULARY','今日词单','按香港日期保存，绑定真实 Anki 卡片。')+'<section class="panel" id="daily-words"></section>';mountWorkflow($('#daily-words'),'words');return;}
 app.innerHTML=heading('VOCABULARY INDEX','词汇索引','可以按词、读音、含义或课号检索；词条数量不代表掌握数量。')+
 `<div class="toolbar"><input class="search" id="word-search" value="${esc(wordQuery)}" placeholder="例如：てちょう、手帳、公司、第2课" aria-label="搜索词汇"><select id="word-volume" class="select" aria-label="词汇册别"><option value="all">初级上下册</option><option value="upper">初级上</option><option value="lower">初级下</option></select><select id="word-status" class="select" aria-label="词汇学习证据"><option value="all">全部学习状态</option><option value="needs_review">待巩固</option><option value="correct_in_written_recall">曾回忆正确</option><option value="not_assessed">未测评</option></select></div><section class="panel"><div id="word-count" class="meta"></div><div id="word-results"></div><div id="word-pagination" class="page-nav"></div></section>`;
 $('#word-volume').value=wordVolume;$('#word-status').value=wordStatus;
 function update(){wordQuery=$('#word-search').value;wordVolume=$('#word-volume').value;wordStatus=$('#word-status').value;const q=wordQuery.trim().toLowerCase();const lessonMatch=q.match(/^第?(\d+)课?$/);const filtered=db.vocabulary.filter(w=>(mode!=='daily'||db.study.daily_word_ids.includes(w.id))&&(wordVolume==='all'||(wordVolume==='upper'?w.lesson_number<=24:w.lesson_number>24))&&(wordStatus==='all'||w.assessment===wordStatus)&&(lessonMatch?w.lesson_number===Number(lessonMatch[1]):`${w.word} ${w.reading} ${w.meaning}`.toLowerCase().includes(q)));const total=Math.ceil(filtered.length/30);wordPage=Math.max(0,Math.min(wordPage,total-1));$('#word-count').textContent=`共 ${filtered.length} 个匹配词项${mode==='daily'?' · 不是今天的到期卡清单':''}`;$('#word-results').innerHTML=filtered.length?wordTable(filtered.slice(wordPage*30,(wordPage+1)*30)):'<p class="empty">没有找到匹配词项，试试假名或中文释义。</p>';$('#word-pagination').innerHTML=`<button id="words-prev" class="button secondary small" ${wordPage===0?'disabled':''}>上一页</button><span class="meta">${total?wordPage+1:0} / ${total}</span><button id="words-next" class="button secondary small" ${wordPage+1>=total?'disabled':''}>下一页</button>`;$('#words-prev').onclick=()=>{wordPage--;update();};$('#words-next').onclick=()=>{wordPage++;update();};}
 updateWordResults=update;$('#word-search').oninput=()=>{wordPage=0;update()};$('#word-volume').onchange=()=>{wordPage=0;update()};$('#word-status').onchange=()=>{wordPage=0;update()};update();
}
function exerciseList(items){return items.map((e,i)=>`<section class="exercise" data-exercise="${e.id}"><span class="eyebrow">${String(i+1).padStart(2,'0')} · ${e.group==='pending'?'上次未完成':'回忆与应用'}</span><p>${ruby(e.prompt)}</p><label for="answer-${e.id}" class="meta">你的回答</label><textarea rows="2" id="answer-${e.id}" class="answer-input" placeholder="先自己回忆，再核对答案。"></textarea><div class="actions"><button class="button small" data-submit="${e.id}">提交并核对</button><button class="button secondary small" data-reveal="${e.id}">先看提示答案</button></div><div id="feedback-${e.id}" aria-live="polite"></div></section>`).join('');}
const revealed = new Set();
function bindExercises(){document.querySelectorAll('[data-reveal]').forEach(b=>b.onclick=()=>{const e=db.exercises.find(x=>x.id===b.dataset.reveal);revealed.add(e.id);$(`#feedback-${e.id}`).innerHTML=`<div class="feedback">${ruby(e.target)}<br>${ruby(e.explanation)}<div class="meta">此题已看答案；之后作答会记为有提示。</div></div>`;});document.querySelectorAll('[data-submit]').forEach(b=>b.onclick=async()=>{const e=db.exercises.find(x=>x.id===b.dataset.submit);const response=$(`#answer-${e.id}`).value.trim();if(!response){toast('先写下你的回答，再提交。');return;}b.disabled=true;const exact=e.answers.some(a=>normalize(a)===normalize(response));const entry={exercise_id:e.id,prompt:e.prompt,response,target:e.target,result:exact?'matches_reference':'needs_teacher_review',support:revealed.has(e.id)?'answer_viewed':'no_answer_shown_in_this_attempt',answered_at:new Date().toISOString()};let saved=false;
 try{if(localAPI){const r=await fetch('/api/practice',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(entry)});if(!r.ok)throw Error('保存失败');saved=true;}else{const entries=JSON.parse(localStorage.getItem('jp-practice')||'[]');entries.push(entry);localStorage.setItem('jp-practice',JSON.stringify(entries));}}
 catch(err){toast('记录未能保存，请保留本次回答。');}
 $(`#feedback-${e.id}`).innerHTML=`<div class="feedback ${exact?'correct':''}"><strong>${exact?'与参考答案一致':'已保留回答，需进一步核对'}</strong><br>${ruby(e.target)}<br>${ruby(e.explanation)}${!exact?'<p class="meta">表达可能有其他正确形式，网站不会仅因写法不同就判错。</p>':''}<div class="meta">${saved?'已写入本机学习库':localAPI?'保存失败':'仅保存在当前浏览器'} · ${revealed.has(e.id)?'有答案提示':'本次未展示答案'} · 不自动判为掌握</div></div>`;b.disabled=false;
 });}
function practice(id){app.innerHTML='<div id="practice-root"></div>';mountPractice($('#practice-root'),id,{esc,ruby});}
async function progress(){
 app.innerHTML=heading('LEARNING EVIDENCE','学习记录','回忆正确、提示后正确、未测评，分别记录。')+`<div class="metric-row"><div class="metric"><strong id="class-session-count">${db.study.sessions_completed}</strong><span>已结束的教学会话</span></div><div class="metric"><strong id="lesson-completed-count">正在核对</strong><span>已确认完成的初级课次</span></div><div class="metric"><strong>30 词项</strong><span>每日学习预算，含恢复与巩固</span></div></div><section class="panel" id="lesson-progress"></section><div class="grid-two"><section class="panel"><div class="section-heading" style="margin-top:0"><h2>课堂学习记录</h2><a class="text-link" href="#classroom">开始或继续课堂 →</a></div><div id="classroom-history"><p class="muted">正在读取课堂记录…</p></div><h2>网站练习记录</h2><div id="practice-history"><p class="muted">正在读取…</p></div><button class="button secondary small" id="export-records">导出网站练习记录</button></section><aside><section class="panel" id="review-calendar"></section><section class="panel" id="classroom-memory"></section><section class="panel"><h2>数据更新时间</h2><p class="muted">教材整理：${db.built_on}<br>历史课堂：${db.study.last_session_date||'尚无记录'}<br>网站课堂：实时读取本机记录<br>Anki：页面打开时自动同步</p><p class="meta">使用页面时约每30秒从 Anki 更新词条与状态；关闭页面后停止轮询。普通练习不改变 Anki 排期。</p></section></aside></div>`;
 mountWorkflow($('#lesson-progress'),'progress');
 mountReviewCalendar($('#review-calendar'),{esc});
 mountClassroomMemory($('#classroom-memory'),{esc});
 classroomRecords($('#classroom-history'),{esc}).then(rows=>{const counter=$('#class-session-count');if(counter&&rows)counter.textContent=db.study.sessions_completed+rows.filter(s=>s.status==='ended').length;});
 let entries=[];try{entries=localAPI?await (await fetch('/api/practice')).json():JSON.parse(localStorage.getItem('jp-practice')||'[]');}catch{}
 if(!$('#practice-history'))return;
 $('#practice-history').innerHTML=entries.length?entries.slice().reverse().slice(0,20).map(e=>`<div class="exercise"><span class="meta">${esc(new Date(e.answered_at).toLocaleString('zh-CN'))}</span><p>${ruby(e.prompt)}</p><p>你的回答：${esc(e.response)}</p><span class="pill">${e.result==='matches_reference'?'与参考一致':'待教练核对'} · ${['answer_viewed','transcript_viewed'].includes(e.support)?'有提示':'本次未看答案'}</span></div>`).join(''):'<p class="muted">还没有网站练习记录。提交答案后会出现在这里。</p>';
 $('#export-records').onclick=()=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(entries,null,2)],{type:'application/json'}));a.download='日语网站练习记录.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);};
}
async function reference(kind){
 const [type,query='']=kind.split('?');kind=type;if(kind==='workbook'){$('#breadcrumb').textContent='教材书架 / 词汇刷词手册';app.innerHTML='<div id="reading-root"></div>';const lessonNumber=Number(new URLSearchParams(query).get('lesson'));mountReading($('#reading-root'),'vocab-workbook',lessonNumber?`lesson-${lessonNumber}`:null,{esc});return;}const requestedPage=Number(new URLSearchParams(query).get('page')||1);
 app.innerHTML=heading('SOURCE REFERENCE',kind==='ocr'?'初级上 · 扫描文本':'初级词汇 · 刷词手册','来源文本仅供核对；未经逐页校对的内容不直接用作评分答案。')+'<div id="reference-body" class="panel"><p class="loading">正在读取…</p></div>';
 try{const d=await (await fetch(`data/${kind==='ocr'?'ocr':'workbook'}.json`)).json();if(kind==='ocr'){const pages=d.pages;let index=Math.max(0,pages.findIndex(p=>p.page===requestedPage));function render(){const p=pages[index];$('#reference-body').innerHTML=pages.length?`<div class="toolbar"><label for="source-page">扫描页</label><select id="source-page" class="select">${pages.map((p,i)=>`<option value="${i}" ${i===index?'selected':''}>第 ${p.page} 页</option>`).join('')}</select><span class="meta">已识别 ${pages.length} / 419 页</span></div><div class="source-note">本机 OCR 识别，含汉字和版面识别错误。原书 PDF 已保留，尚不能把此文本当作原书的完整替代。</div>${(()=>{const lesson=db.lessons.find(l=>l.scan_reference?.exercise_pages.includes(p.page));return lesson?`<div class="actions"><a class="button" href="#textbook/${lesson.id}">去第 ${lesson.number} 课做教材练习 →</a></div><p class="meta">这里是供检索的扫描转写，原题和作答入口已放回课内。</p>`:'';})()}<div class="prose">${p.lines.map(x=>`<p>${esc(x.text)}</p>`).join('')}</div>`:'<p class="empty">扫描识别还未完成，请稍后重新整理数据。</p>';if(pages.length)$('#source-page').onchange=e=>{index=+e.target.value;render();};}render();}}
 catch(e){$('#reference-body').innerHTML='<p class="notice">这份资料暂时无法读取，请刷新重试。</p>';}
}
function notFound(){app.innerHTML=heading('NOT FOUND','没有找到这一页')+'<a class="button" href="#today">返回今日学习</a>';}
function route(){if(!db)return;const [route='today',id,part]=(location.hash.slice(1)||'today').split('/');if(route==='reading'&&updateReadingPart($('#reading-root'),id,part))return;document.querySelectorAll('[data-nav]').forEach(a=>a.classList.toggle('active',a.dataset.nav===((['lesson','reference','textbook'].includes(route)||(route==='reading'&&id==='vocab-workbook'))?'library':route)));$('#breadcrumb').textContent=({today:'学习工作台',classroom:'文字课堂',library:'教材书架',words:'词汇索引',practice:'重点练习',progress:'学习记录',review:'Anki 复习',reading:'课外阅读',reference:'原始资料'})[route]||'教材阅读';if(route==='today')today();else if(route==='classroom'){app.innerHTML='<div id="classroom-root"></div>';mountClassroom($('#classroom-root'),id,{esc,ruby,lessons:db.lessons});}else if(route==='library')library();else if(route==='reading'){if(id==='vocab-workbook')$('#breadcrumb').textContent='教材书架 / 词汇刷词手册';app.innerHTML='<div id="reading-root"></div>';mountReading($('#reading-root'),id,part,{esc});}else if(route==='textbook'){viewTab='exercises';lesson(id);}else if(route==='lesson'){if(part)viewTab=['basic_text','dialogue','vocabulary','grammar','exercises'].includes(part)?part:'basic_text';lesson(id);}else if(route==='words')words(id);else if(route==='review'){app.innerHTML='<div id="anki-review-root"></div>';mountAnkiReview($('#anki-review-root'),()=>refreshAnki(true));}else if(route==='practice')practice(id);else if(route==='progress')progress();else if(route==='reference')reference(id);else notFound();window.scrollTo(0,0);}
document.addEventListener('click',e=>{const b=e.target.closest('[data-audio]');if(b)play(b.dataset.audio,b.dataset.fallbackAudio);});window.addEventListener('hashchange',route);
try{const r=await fetch('data/library.json');if(!r.ok)throw Error('教材数据未就绪');db=await r.json();sourceWords=db.vocabulary.map(w=>({...w}));try{const h=await fetch('/api/health');localAPI=h.ok&&(await h.json()).service==='jp-study-local';}catch{}route();if(localAPI){refreshAnki();setInterval(()=>{if(!document.hidden)refreshAnki();},30000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)refreshAnki();});window.addEventListener('focus',()=>refreshAnki());}}catch(e){app.innerHTML='<h1>学习库暂时无法读取</h1><p>请通过网站地址打开，或重新启动学习网站。</p>';}

mountServiceStatus(document.querySelector('#service-status'));
