import {mountPDFReader} from './pdf-reader.js';
import {mountWorkbook} from './workbook.js';
let catalogTask;
function catalog(){return catalogTask ||= fetch('data/reading-library.json').then(r=>{if(!r.ok)throw Error('书架数据暂不可用');return r.json()}).catch(e=>{catalogTask=null;throw e;});}
function position(id){try{return JSON.parse(localStorage.getItem('jp-reading-'+id)||'null');}catch{return null;}}
function remember(id,value){try{localStorage.setItem('jp-reading-'+id,JSON.stringify({...value,opened_at:new Date().toISOString()}));}catch{}}
export function updateReadingPart(root,id,part){
 if(!root||root.dataset.pdfBook!==id||!root.setReadingPart)return false;
 root.setReadingPart(part);return true;
}
export async function mountReading(root,id,part,{esc}){
 root.innerHTML='<p class="loading">正在打开书籍…</p>';
 try{
  const isWorkbook=id==='vocab-workbook';
  const data=isWorkbook?{books:[await fetch('data/vocabulary-workbook-reader.json').then(r=>{if(!r.ok)throw Error('刷词手册暂不可用');return r.json();})]}:await catalog();if(!root.isConnected)return;
  if(!id){
   root.innerHTML=`<div class="page-head"><div><span class="eyebrow">READ BEYOND THE TEXTBOOK</span><h1>课外阅读</h1><p class="muted">从日本历史与文化出发，按自己的兴趣慢慢读。</p></div></div><div class="reading-shelf">${data.books.map(b=>{const p=position(b.id);return `<article class="panel leisure-book"><a class="reading-cover" href="#reading/${b.id}"><img src="${esc(b.cover)}" alt="${esc(b.title)}封面" loading="lazy"></a><div class="reading-book-info"><span class="pill">${esc(b.category)}</span><h2>${esc(b.title)}</h2><p class="meta">${esc(b.author)} · ${esc(b.language)}</p><p class="muted">${esc(b.description)}</p><p class="meta">${b.sections?`${b.sections} 个原书章节/书页`:`${b.pages} 页原书扫描`}</p><a class="button" href="#reading/${b.id}">${p?'继续阅读':'打开阅读'} →</a>${p?`<p class="meta">上次打开：${esc(p.label)}</p>`:''}</div></article>`}).join('')}</div><p class="meta">已收录文件夹里的 ${data.books.length} 部历史、文化读物。阅读位置保存在本浏览器；打开书页不会计为已读完或日语知识已掌握。</p>`;
   return;
  }
  const book=data.books.find(b=>b.id===id);if(!book){root.innerHTML='<p class="notice">没有找到这本书。</p><a href="#reading">返回课外书架</a>';return;}
  if(isWorkbook){await mountWorkbook(root,book,part,{esc,position,remember});return;}
  if(book.reader_type==='pdf_pages'){mountPDFReader(root,book,part,{esc,position,remember});return;}
  if(isWorkbook&&part?.startsWith('lesson-'))part=book.chapters.find(c=>c.lesson===Number(part.slice(7)))?.id||book.default_part;
  const last=position(id),isPDF=book.reader_type==='pdf_pages';
  let index=0,anchor='';
  if(isPDF){const value=Number(part||last?.part||1);index=Number.isInteger(value)?Math.max(0,Math.min(book.pages-1,value-1)):0;}
  else{const [wanted,fragment]=(part||last?.part||book.default_part||book.chapters[0].id).split('~');index=Math.max(0,book.chapters.findIndex(c=>c.id===wanted));anchor=fragment||'';}
  const total=isPDF?book.pages:book.chapters.length,cid=isPDF?String(index+1):book.chapters[index].id,title=isPDF?`第 ${index+1} / ${total} 页`:book.chapters[index].title;
  const route=i=>`#reading/${book.id}/${isPDF?i+1:book.chapters[i].id}`;
  const nav=()=>`<div class="page-nav reading-page-nav">${index>0?`<a class="button secondary small" href="${route(index-1)}">← ${isPDF?'上一页':'上一节'}</a>`:'<span></span>'}<span class="meta">${index+1} / ${total}</span>${index+1<total?`<a class="button secondary small" href="${route(index+1)}">${isPDF?'下一页':'下一节'} →</a>`:'<span></span>'}</div>`;
  root.innerHTML=`<div class="reading-reader"><a class="text-link" href="${isWorkbook?'#library':'#reading'}">← ${isWorkbook?'教材书架':'课外书架'}</a><div class="page-head"><div><span class="eyebrow">${esc(book.category)} · ${esc(book.format)}</span><h1>${esc(book.title)}</h1><p class="muted">${esc(book.author)}</p></div></div><section class="panel reading-controls">${isPDF?`<form id="reading-jump" class="toolbar"><label for="reading-page">页码</label><input id="reading-page" class="select" type="number" min="1" max="${total}" value="${index+1}" required><span class="meta">共 ${total} 页</span><button class="button small" type="submit">跳转</button><a class="text-link" href="${book.original_url}" target="_blank" rel="noopener">打开原 PDF ↗</a></form>`:`<div class="toolbar"><label for="reading-chapter">原书目录</label><select class="select reading-chapter-select" id="reading-chapter">${[...new Set(book.chapters.map(c=>c.volume))].map(group=>`<optgroup label="${esc(group)}">${book.chapters.map((c,i)=>c.volume===group?`<option value="${i}" ${i===index?'selected':''}>${esc(c.title)}</option>`:'').join('')}</optgroup>`).join('')}</select><label for="reading-font">字号</label><select class="select" id="reading-font"><option value="18">标准</option><option value="21" selected>舒适</option><option value="24">大字</option></select></div><p class="meta">${esc(book.chapters[index].volume)} · EPUB 原文与插图</p>`}${isWorkbook?`<div class="actions"><a class="button secondary small" href="#reading/vocab-workbook/${book.answer_part}">查阅参考答案</a>${book.chapters[index].lesson?`<a class="button secondary small" href="#lesson/b${String(book.chapters[index].lesson).padStart(2,'0')}">返回第 ${book.chapters[index].lesson} 课</a>`:''}<a class="button secondary small" href="#review">Anki 复习</a></div><p class="meta">原书词汇、练习、插图与参考答案已收录，可自行作答后核对。音频二维码保留在书页中；此 EPUB 未附音频文件。原文尚未逐题校对。</p>`:''}${nav()}</section><article id="reading-content" class="panel ${isPDF?'pdf-reading-page':'epub-reading-page'}" aria-label="${esc(title)}"><p class="loading">正在读取${isPDF?'原书页面':'章节'}…</p></article>${nav()}<p class="meta" id="reading-position">阅读位置在内容载入后保存到本浏览器。</p></div>`;
  const body=root.querySelector('#reading-content');
  if(isPDF){
   const src=`reading/${book.id}/pages/page-${String(index+1).padStart(3,'0')}.jpg`;
   body.innerHTML=`<img class="pdf-book-page" src="${src}" alt="${esc(book.title)}，PDF第${index+1}页">`;
   const img=body.querySelector('img');const saved=()=>{if(root.isConnected){remember(id,{part:cid,label:title});root.querySelector('#reading-position').textContent='已记住本次打开的页码 · 本浏览器';}};
   img.onload=saved;img.onerror=()=>{if(root.isConnected)root.querySelector('#reading-position').textContent='本页未能载入，请刷新重试。';};if(img.complete&&img.naturalWidth)saved();
   root.querySelector('#reading-jump').onsubmit=e=>{e.preventDefault();const n=Number(root.querySelector('#reading-page').value);if(Number.isInteger(n)&&n>=1&&n<=total)location.hash=route(n-1);};
  }else{
   root.querySelector('#reading-chapter').onchange=e=>location.hash=route(Number(e.target.value));
   root.querySelector('#reading-font').onchange=e=>body.style.fontSize=e.target.value+'px';
   const response=await fetch(`reading/${book.id}/${cid}.json`);if(!response.ok)throw Error('章节暂未读取成功');const chapter=await response.json();if(!root.isConnected)return;
   // Only the build-time sanitized, local EPUB fragment is inserted here.
   body.innerHTML=chapter.html;remember(id,{part:cid,label:title});root.querySelector('#reading-position').textContent='已记住本次打开的章节 · 本浏览器';
   if(anchor){try{document.getElementById(cid+'-'+decodeURIComponent(anchor))?.scrollIntoView({block:'start'});}catch{}}
  }
 }catch(error){if(root.isConnected)root.innerHTML=`<p class="notice">${esc(error.message)}。请重新打开本书。</p><a class="button secondary" href="#reading">返回课外书架</a>`;}
}
