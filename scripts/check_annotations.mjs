import assert from 'node:assert/strict';
import {annotatedText,japaneseText} from '../website/dist/annotated-text.js';
assert.equal(annotatedText('下次先短时复习（ふくしゅう）'),'下次先短时复习（ふくしゅう）');
assert.equal(annotatedText('先复习飲んで（のんで）'),'先复习飲んで（のんで）');
assert.equal(annotatedText('请写｜名前《なまえ》'),'请写<ruby lang="ja">名前<rt>なまえ</rt></ruby>');
assert(!annotatedText('<img onerror="oops">').includes('<img'));
assert(japaneseText('学生（がくせい）です').includes('<rt>がくせい</rt>'));
console.log('PASS: Chinese boundary, explicit Japanese annotations, escaping, Japanese-only source readings.');
