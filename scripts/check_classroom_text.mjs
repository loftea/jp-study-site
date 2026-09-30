import assert from 'node:assert/strict';
import {classroomText} from '../website/dist/classroom-text.js';
const pair='- [音频①](audio/book01-lesson01-18.mp3)\n- [音频②](audio/book01-lesson01-13.mp3)';
const rendered=classroomText(pair);
assert.equal((rendered.match(/<audio /g)||[]).length,2);
assert(rendered.includes('src="/audio/book01-lesson01-18.mp3"'));
assert(rendered.includes('controls preload="none"'));
assert(rendered.includes('单独打开音频'));
assert(classroomText('[音频]\\(audio/book01-lesson01-18.mp3\\)').includes('<audio '));
assert(classroomText('[音频](/audio/book01-lesson01-18.mp3)').includes('<audio '));
assert(classroomText('[第1课](#lesson/b01)').includes('href="#lesson/b01"'));
assert(classroomText('**听读** ｜人《ひと》').includes('<ruby lang="ja">人<rt>ひと</rt></ruby>'));
for(const url of ['https://example.com/a.mp3','//evil/a.mp3','audio/../secret.mp3','audio/%2e%2e/secret.mp3','javascript:alert','audio/x.mp3?x=1','audio/x"onerror="evil.mp3']){
 const html=classroomText(`[音频](${url})`);
 assert(!html.includes('<audio '));assert(!html.includes('<a '));
}
const malicious=classroomText('[<img src=x onerror=evil>](audio/safe.mp3)');
assert(!malicious.includes('<img'));
assert(!classroomText('<script>alert(1)</script>').includes('<script>'));
console.log('PASS: saved audio links, escaped brackets, textbook links, kana and HTML/path safety');
