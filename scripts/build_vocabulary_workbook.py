"""Publish the supplied workbook as a separate textbook companion reader."""
from pathlib import Path
import re, zipfile, json
from epub_reader import extract_epub, dump
from workbook_structure import structure_lesson, answers_by_chapter

ROOT = Path(__file__).resolve().parents[1]
import argparse
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',required=True,type=Path);args=parser.parse_args()
source=args.source.resolve()
# Keep the source's small QR codes and icons from expanding across the page.
image_widths = {}
with zipfile.ZipFile(source) as archive:
    for member in archive.namelist():
        if member.endswith('.css'):
            for name, rules in re.findall(r'\.([\w-]+)\s*\{([^}]+)}', archive.read(member).decode()):
                width = re.search(r'(?:^|;)\s*width\s*:\s*(\d+)px', rules)
                if width:
                    image_widths[name] = int(width[1])
book = extract_epub(source, ROOT / 'website/dist/reading/vocab-workbook', 'vocab-workbook', image_widths)
for chapter in book['chapters']:
    if chapter['id'] == 'c002':
        chapter['title'] = '原书封面'
    elif chapter['title'] == 'Unknown':
        chapter['title'] = '卷首插页'
    match = re.fullmatch(r'第\s*(\d+)\s*课', chapter['title'])
    chapter['lesson'] = int(match[1]) if match else None
    if chapter['lesson']:
        chapter['volume'] = '初级上' if chapter['lesson'] <= 24 else '初级下'
    elif '单元测试' in chapter['title']:
        chapter['volume'] = '单元测试'
    elif '模拟题' in chapter['title']:
        chapter['volume'] = '模拟题'
    elif '参考答案' in chapter['title']:
        chapter['volume'] = '参考答案'
    else:
        chapter['volume'] = '其他原书内容'
assert sorted(c['lesson'] for c in book['chapters'] if c['lesson']) == list(range(1, 49))
folder = ROOT / 'website/dist/reading/vocab-workbook'
with zipfile.ZipFile(source) as archive:
    answer_meta = next(c for c in book['chapters'] if c['volume'] == '参考答案')
    answer_source = json.loads((folder / f"{answer_meta['id']}.json").read_text())
    answers = answers_by_chapter(archive.read(answer_source['source_member']))
    for chapter in book['chapters']:
        path = folder / f"{chapter['id']}.json"
        data = json.loads(path.read_text())
        data['answers'] = answers.get(chapter['title'], [])
        if chapter['lesson']:
            data['study'] = structure_lesson(archive.read(data['source_member']))
            data['study']['audio_images'] = re.findall(r'<img[^>]*style="width:98px"[^>]*src="([^"]+)"', data['html'])
            assert data['answers'], chapter['title']
            chapter['word_count'] = len(data['study']['words'])
        dump(path, data)
book.update({
    'id': 'vocab-workbook', 'title': '标准日语初级词汇·刷词手册',
    'author': '新东方日语研究中心 编著', 'category': '教材配套',
    'format': 'EPUB', 'reader_type': 'epub',
    'source_path': source.name,
    'default_part': next(c['id'] for c in book['chapters'] if c['lesson'] == 1),
    'answer_part': next(c['id'] for c in book['chapters'] if c['volume'] == '参考答案'),
    'embedded_audio': False, 'quality': 'source_epub_not_proofread',
})
dump(ROOT / 'website/dist/data/vocabulary-workbook-reader.json', book)
dump(ROOT / 'study/library/vocabulary-workbook-reader.json', book)
print(f"Published {book['sections']} original sections, 48 lessons, 12 unit tests and answer key.")
