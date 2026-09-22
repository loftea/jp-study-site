export async function mountWorkbook(root, book, part, {esc, position, remember}) {
 const chapters=book.chapters||[];
 if(!chapters.length){root.innerHTML='<p class="notice">尚未导入词汇手册。请使用本机导入脚本添加自己的 EPUB。</p>';return;}
 if(part?.startsWith('lesson-'))part=chapters.find(c=>c.lesson===Number(part.slice(7)))?.id;
 const wanted=(part||position(book.id)?.part||book.default_part).split('~')[0];
 const meta=chapters.find(c=>c.id===wanted)||chapters.find(c=>c.id===book.default_part);
 const response=await fetch(`reading/vocab-workbook/${meta.id}.json`);
 if(!response.ok)throw Error('本课内容暂时无法读取');
 const chapter=await response.json();if(!root.isConnected)return;
 const study=chapter.study, lessons=chapters.filter(c=>c.lesson), lessonIndex=lessons.indexOf(meta);
 let active=study?'words':'content', query='', meaningsVisible=true;
 const link=c=>`#reading/vocab-workbook/${c.id}`;
 const groups=['初级上','初级下','单元测试','模拟题','参考答案','其他原书内容'];
 root.innerHTML=`<div class="workbook-reader"><a class="text-link" href="#library">← 教材书架</a>
 <div class="page-head"><div><span class="eyebrow">词汇刷词 · ${esc(meta.volume)}</span><h1>${esc(meta.title)}</h1><p class="muted">标准日语初级词汇 · 刷词手册${study?` · ${study.words.length} 个词项 · ${study.exercise_groups.length} 组练习`:''}</p></div></div>
 <div class="panel workbook-controls"><div class="toolbar"><label for="workbook-chapter">选择课次</label><select id="workbook-chapter" class="select">${groups.map(group=>`<optgroup label="${group}">${chapters.filter(c=>c.volume===group).map(c=>`<option value="${c.id}" ${c===meta?'selected':''}>${esc(c.title)}</option>`).join('')}</optgroup>`).join('')}</select>${study?`<div class="workbook-lesson-nav">${lessonIndex>0?`<a class="text-link" href="${link(lessons[lessonIndex-1])}">← 上一课</a>`:''}${lessonIndex<47?`<a class="text-link" href="${link(lessons[lessonIndex+1])}">下一课 →</a>`:''}</div>`:''}</div>
 <div class="tabs" role="tablist" aria-label="刷词内容">${(study?[['words','词汇'],['exercises','练习'],['answers','参考答案']]:[['content','正文'],...(chapter.answers?.length?[['answers','参考答案']]:[])]).map(([id,label])=>`<button class="tab ${active===id?'active':''}" role="tab" id="workbook-tab-${id}" aria-controls="workbook-body" aria-selected="${active===id}" data-workbook-tab="${id}">${label}</button>`).join('')}</div></div>
 <section id="workbook-body" role="tabpanel" aria-labelledby="workbook-tab-${active}"></section>
 <details class="panel workbook-source"><summary>音频与原书资料</summary><p class="meta">${esc(book.author)} · 原 EPUB 内容，尚未逐题校对。此处按网页重新排版，可自行作答后查阅参考答案。</p>${study?.audio_images?.length?`<p class="meta">原书音频需扫码访问，EPUB 没有附带可直接播放的音频文件。</p><div class="workbook-audio">${study.audio_images.map((src,i)=>`<figure><img src="${esc(src)}" alt="${i===0?'词汇音频':'听写音频'}二维码" loading="lazy"><figcaption>${i===0?'词汇音频':'听写音频'}</figcaption></figure>`).join('')}</div>`:''}<div class="actions">${meta.lesson?`<a class="button secondary small" href="#lesson/b${String(meta.lesson).padStart(2,'0')}">返回本课教材</a>`:''}<a class="button secondary small" href="#review">Anki 复习</a></div><details class="workbook-original"><summary>查看原书内容</summary><div class="workbook-source-content">${chapter.html}</div></details></details>
 <p class="meta">已记住本次打开的${meta.lesson?'课次':'章节'} · 本浏览器</p></div>`;
 root.querySelector('#workbook-chapter').onchange=e=>location.hash=`#reading/vocab-workbook/${e.target.value}`;
 const body=root.querySelector('#workbook-body');
 const answerGroups=()=>{
  const blocks=[];let current;
  for(const line of chapter.answers||[]){
   if(/^[一二三四五六七八九十]+、|^もんだい\d/.test(line)){current={title:line,lines:[]};blocks.push(current);}
   else{if(!current){current={title:'原书参考答案',lines:[]};blocks.push(current);}current.lines.push(line);}
  }
  return blocks.map(b=>`<details class="panel workbook-answer-group"><summary>${esc(b.title)}</summary><div class="workbook-answer-lines">${b.lines.map(line=>`<p>${esc(line)}</p>`).join('')}</div></details>`).join('');
 };
 function renderCards(){
  const words=study.words.filter(w=>`${w.word} ${w.reading} ${w.meaning}`.toLowerCase().includes(query.toLowerCase()));
  root.querySelector('#workbook-count').textContent=`${words.length} / ${study.words.length} 个词项`;
  root.querySelector('#workbook-word-grid').innerHTML=words.map(w=>`<article class="workbook-word"><div class="workbook-word-top"><span class="meta">${String(w.number).padStart(2,'0')}</span>${w.accent?`<span class="workbook-accent" title="原书声调标记">${esc(w.accent)}</span>`:''}</div><div class="workbook-word-label" lang="ja">${esc(w.word)}</div>${w.reading?`<div class="workbook-reading" lang="ja">${esc(w.reading)}</div>`:''}<details class="workbook-meaning" ${meaningsVisible?'open':''}><summary>释义</summary><p>${w.part_of_speech?`<span class="workbook-pos">${esc(w.part_of_speech)}</span>`:''}${esc(w.meaning)}</p></details></article>`).join('')||'<p class="empty">本课没有匹配的词汇。</p>';
 }
 function render(){
  for(const button of root.querySelectorAll('[data-workbook-tab]')){const selected=button.dataset.workbookTab===active;button.classList.toggle('active',selected);button.setAttribute('aria-selected',String(selected));}
  body.setAttribute('aria-labelledby','workbook-tab-'+active);
  if(active==='words'){
   body.innerHTML=`<div class="toolbar workbook-word-tools"><input id="workbook-search" class="search" placeholder="查找本课的词、读音或释义" aria-label="搜索本课词汇" value="${esc(query)}"><button class="button secondary small" id="workbook-meaning-toggle">${meaningsVisible?'隐藏释义，试着回忆':'显示全部释义'}</button><span class="meta" id="workbook-count"></span></div><div class="workbook-word-grid" id="workbook-word-grid"></div><p class="meta">圆圈数字沿用原书声调标记。隐藏释义后，可逐词展开核对。</p>`;
   root.querySelector('#workbook-search').oninput=e=>{query=e.target.value.trim();renderCards();};
   root.querySelector('#workbook-meaning-toggle').onclick=e=>{meaningsVisible=!meaningsVisible;e.currentTarget.textContent=meaningsVisible?'隐藏释义，试着回忆':'显示全部释义';root.querySelectorAll('.workbook-meaning').forEach(d=>d.open=meaningsVisible);};renderCards();
  }else if(active==='exercises'){
   body.innerHTML=`<p class="meta">按题型分组，在纸上或笔记中作答后，切换到「参考答案」核对。</p>${study.exercise_groups.map((g,i)=>`<section class="panel workbook-exercise-group"><h2>${esc(g.title)}</h2>${i===3?'<p class="meta">听写音频二维码在下方「音频与原书资料」中。</p>':''}${g.notes.map(note=>`<p class="meta">${esc(note)}</p>`).join('')}<div class="workbook-exercise-grid">${g.items.map(item=>`<div class="workbook-question"><span class="meta">${String(item.number).padStart(2,'0')}</span><span lang="ja">${esc(item.text).replace(/[_＿]{2,}/g,'<span class="workbook-blank" aria-label="待填写"></span>')}</span></div>`).join('')}</div></section>`).join('')}`;
  }else if(active==='answers')body.innerHTML='<p class="meta">按题型展开原书参考答案，题号与练习对应。</p>'+answerGroups();
  else body.innerHTML=`<article class="panel workbook-prose">${chapter.html}</article>`;
 }
 root.querySelectorAll('[data-workbook-tab]').forEach(button=>button.onclick=()=>{active=button.dataset.workbookTab;render();});
 render();remember(book.id,{part:meta.id,label:meta.title});
}
