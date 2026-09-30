import {annotatedText,escapeText} from './annotated-text.js';

// Parse links before formatting labels so model text never enters HTML attributes.
export function classroomText(text, ruby=annotatedText){
 const prose=value=>ruby(value).replace(/\*\*([^\n]+?)\*\*/g,'<strong>$1</strong>').replace(/^#{1,4} (.+)$/gm,'<strong class="class-text-heading">$1</strong>');
 const links=/\[([^\]\n]+)\]\\?\(([^\s()]+?)\\?\)/g;
 let html='',offset=0;
 for(const match of String(text??'').matchAll(links)){
  html+=prose(text.slice(offset,match.index));
  const [raw,label,target]=match;
  if(/^\/?audio\/[a-zA-Z0-9_-]+\.(?:mp3|wav|ogg|m4a|flac)$/.test(target)){
   const src='/'+target.replace(/^\//,'');
   html+=`<span class="class-audio"><span>${prose(label)}</span><audio controls preload="none" src="${src}" aria-label="${escapeText(label)}"></audio><a class="text-link" href="${src}" target="_blank" rel="noopener">单独打开音频</a></span>`;
  }else if(/^#(?:lesson|textbook)\/b\d{2}$/.test(target)){
   html+=`<a class="text-link" href="${target}">${prose(label)}</a>`;
  }else html+=prose(raw);
  offset=match.index+raw.length;
 }
 return html+prose(String(text??'').slice(offset));
}
