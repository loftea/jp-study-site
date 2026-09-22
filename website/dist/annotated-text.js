// Mixed Chinese/Japanese prose is never guessed from adjacent Han characters.
export const escapeText = text => String(text??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function annotatedText(text){
 return escapeText(text).replace(/｜([一-龯々〆ヵヶぁ-んァ-ヶー0-9０-９]+)《([ぁ-んァ-ヶー・]+)》/g,'<ruby lang="ja">$1<rt>$2</rt></ruby>');
}
export function japaneseText(text){
 // Only call for source paragraphs/fields already explicitly classified as Japanese.
 return annotatedText(text).replace(/([0-9０-９一-龯々〆ヵヶ]+[ぁ-んァ-ヶー]*)[（(]([ぁ-んァ-ヶー・]+)[）)]/g,'<ruby lang="ja">$1<rt>$2</rt></ruby>');
}
