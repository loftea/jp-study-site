// Merge the current Anki mirror into the reading view; never overwrite source
// files, teacher assessments, learner answers or scheduling data in Anki.
export function mergeAnkiVocabulary(sourceWords, snapshot) {
 const notes=snapshot.notes||{},words=[],known=new Set(sourceWords.map(w=>String(w.note_id)));
 let matched=0;
 function merge(original,note){
  const w={...original};
  if(!note){w.anki_status='missing_or_outside_jp';return w;}
  matched++;
  const cards=note.cards||[],v=note.vocabulary;
  w.anki_cards=cards;w.card_ids=cards.map(c=>c.cardId);w.anki_synced_at=snapshot.captured_at;
  w.anki_status=cards.some(c=>c.is_due)?'due':cards.every(c=>c.queue===-1)?'suspended':cards.some(c=>c.reviewed_today)?'reviewed_today':cards.every(c=>c.type===0)?'new':'scheduled';
  if(v){
   for(const key of ['word','reading','ruby_source','meaning','part_of_speech'])w[key]=v[key]??w[key];
   if(v.lesson_number){w.lesson_number=v.lesson_number;w.lesson_id=`b${String(v.lesson_number).padStart(2,'0')}`;}
   else w.anki_lesson_unmapped=true;
   w.fallback_audio=w.audio;w.audio=v.audio_filename?`/api/anki/audio?note_id=${note.note_id}`:null;
   w.live_audio_filename=v.audio_filename;
  }
  return w;
 }
 for(const word of sourceWords)words.push(merge(word,notes[String(word.note_id)]));
 for(const [id,note] of Object.entries(notes)){
  if(known.has(id)||!note.vocabulary?.lesson_number)continue;
  // Only infer new textbook mappings inside this exact beginner deck family.
  if(!note.cards.some(c=>c.deckName==='JP::标日::初级'||c.deckName?.startsWith('JP::标日::初级::')))continue;
  words.push(merge({id:`anki-${note.note_id}`,note_id:note.note_id,assessment:'not_assessed',source_id:'local_anki_sync',source_verified_against_pdf:false,audio:null},note));
 }
 return {words,matched,missing:sourceWords.filter(w=>!notes[String(w.note_id)]).length};
}
