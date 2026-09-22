import assert from 'node:assert/strict';
import {mergeAnkiVocabulary} from '../website/dist/anki-sync.js';
const source=[{id:'anki-10',note_id:10,word:'旧词',meaning:'旧释义',lesson_number:1,lesson_id:'b01',assessment:'needs_review',audio:'audio/old.mp3'},{id:'anki-11',note_id:11,word:'未找到'}];
const v={word:'手帳',reading:'てちょう',ruby_source:'手帳[てちょう]',meaning:'新释义',lesson_number:2,audio_filename:'new.mp3'};
const snapshot={captured_at:'2025-02-20',notes:{'10':{note_id:10,vocabulary:v,cards:[{cardId:12,is_due:true,queue:2,type:2,deckName:'JP::标日::初级'}]},'20':{note_id:20,vocabulary:{...v,word:'新词'},cards:[{cardId:22,queue:0,type:0,deckName:'JP::标日::初级'}]},'30':{note_id:30,vocabulary:v,cards:[{cardId:32,queue:0,type:0,deckName:'JP::其他'}]}}};
const result=mergeAnkiVocabulary(source,snapshot);
assert.equal(result.words.length,3);assert.equal(result.words[0].meaning,'新释义');assert.equal(result.words[0].assessment,'needs_review');assert.equal(result.words[0].anki_status,'due');assert.equal(result.words[0].lesson_id,'b02');assert.deepEqual(result.words[0].card_ids,[12]);assert.equal(result.words[1].anki_status,'missing_or_outside_jp');assert.equal(result.words[2].assessment,'not_assessed');assert.equal(source[0].meaning,'旧释义');assert.equal(result.words[0].fallback_audio,'audio/old.mp3');
console.log('PASS: mapped fields, new beginner words, removals, other-deck exclusion; original textbook and learning evidence preserved.');
