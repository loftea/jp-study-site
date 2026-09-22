// Persistent reader for the PDF's existing, full-page scan images.
// Navigation changes only the page inside the viewport, never the app shell.
export function mountPDFReader(root,book,part,{esc,position,remember}){
 let page=0,request=0,failed=false;
 const parse=value=>{const n=Number(value||position(book.id)?.part||1);return Number.isInteger(n)?Math.max(1,Math.min(book.pages,n)):1;};
 root.innerHTML=`<div class="reading-reader"><a class="text-link" href="#reading">← 课外书架</a><div class="page-head"><div><span class="eyebrow">${esc(book.category)} · ${esc(book.format)}</span><h1>${esc(book.title)}</h1><p class="muted">${esc(book.author)}</p></div></div><section class="panel pdf-reader" aria-label="PDF 阅读器"><div class="pdf-reader-toolbar"><button class="button secondary small" data-pdf-step="-1" aria-label="上一页">← 上一页</button><form data-pdf-jump><label for="reading-page">页码</label><input id="reading-page" class="select" type="number" min="1" max="${book.pages}" required><span class="meta">/ ${book.pages}</span><button class="button secondary small" type="submit">跳转</button></form><button class="button secondary small" data-pdf-step="1" aria-label="下一页">下一页 →</button><label for="pdf-zoom" class="meta">缩放</label><select id="pdf-zoom" class="select"><option value="width">适合宽度</option><option value="page">适合整页</option><option value="125">125%</option><option value="150">150%</option></select><a class="text-link" href="${esc(book.original_url)}" target="_blank" rel="noopener">原 PDF ↗</a></div><div class="pdf-reader-viewport" tabindex="0" role="region" aria-label="书页阅读区，可在区内滚动"></div><div class="pdf-reader-footer"><span data-pdf-status class="meta" role="status"></span><button class="button secondary small" data-pdf-retry hidden>重试本页</button><span class="meta">← / → 翻页 · 页码自动记忆</span></div></section></div>`;
 const viewport=root.querySelector('.pdf-reader-viewport'),input=root.querySelector('#reading-page'),status=root.querySelector('[data-pdf-status]'),zoom=root.querySelector('#pdf-zoom'),retry=root.querySelector('[data-pdf-retry]');
 function scale(){
  viewport.dataset.zoom=zoom.value;
  const img=viewport.querySelector('img');if(!img)return;
  img.style.width=zoom.value==='width'||zoom.value==='page'?'100%':zoom.value+'%';
 }
 function show(value,{historyMode=null,force=false}={}){
  const target=parse(value);
  if(target===page&&!force&&!failed)return;
  page=target;failed=false;const token=++request;
  if(historyMode)history[historyMode]({},'',`#reading/${book.id}/${page}`);
  input.value=String(page);retry.hidden=true;
  root.querySelectorAll('[data-pdf-step]').forEach(b=>b.disabled=Number(b.dataset.pdfStep)<0?page===1:page===book.pages);
  status.textContent=`正在读取第 ${page} / ${book.pages} 页…`;
  viewport.setAttribute('aria-busy','true');viewport.setAttribute('aria-label',`书页阅读区，第 ${page} / ${book.pages} 页`);
  // Keep the viewport's dimensions unchanged while the next image loads.
  const img=new Image();img.className='pdf-book-page';img.alt=`${book.title}，PDF 第 ${page} 页`;
  img.onload=()=>{
   if(!root.isConnected||token!==request)return;
   viewport.replaceChildren(img);scale();viewport.scrollTop=0;viewport.scrollLeft=0;viewport.setAttribute('aria-busy','false');
   remember(book.id,{part:String(target),label:`第 ${target} / ${book.pages} 页`});
   status.textContent=`第 ${target} / ${book.pages} 页 · 已记住阅读位置`;
  };
  img.onerror=()=>{
   if(!root.isConnected||token!==request)return;
   failed=true;viewport.replaceChildren();viewport.setAttribute('aria-busy','false');
   status.textContent=`第 ${target} 页未能载入，请重试。`;retry.hidden=false;
  };
  img.src=`reading/${book.id}/pages/page-${String(page).padStart(3,'0')}.jpg`;
 }
 root.dataset.pdfBook=book.id;
 root.setReadingPart=value=>show(value);
 root.querySelectorAll('[data-pdf-step]').forEach(b=>b.onclick=()=>show(page+Number(b.dataset.pdfStep),{historyMode:'pushState'}));
 root.querySelector('[data-pdf-jump]').onsubmit=e=>{e.preventDefault();const n=Number(input.value);if(Number.isInteger(n)&&n>=1&&n<=book.pages)show(n,{historyMode:'pushState'});};
 zoom.onchange=scale;retry.onclick=()=>show(page,{force:true});
 viewport.onkeydown=e=>{if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();show(page+(e.key==='ArrowRight'?1:-1),{historyMode:'pushState'});}};
 show(part);
}
