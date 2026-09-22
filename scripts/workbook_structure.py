"""Reflow the workbook's lesson content without inventing answers or readings."""
import re
import xml.etree.ElementTree as ET

def paragraphs(raw):
    root = ET.fromstring(raw)
    return [re.sub(r'\s+', ' ', ''.join(el.itertext())).strip()
            for el in root.iter() if el.tag.rsplit('}', 1)[-1] in ('p', 'h1', 'h2', 'h3')]

def answers_by_chapter(raw):
    result, current = {}, None
    for el in ET.fromstring(raw).iter():
        tag = el.tag.rsplit('}', 1)[-1]
        text = re.sub(r'\s+', ' ', ''.join(el.itertext())).strip()
        if tag == 'h2':
            current = []
            result[text] = current
        elif tag == 'p' and current is not None and text:
            current.append(text)
    return result

def structure_lesson(raw):
    words, groups, notes = [], [], []
    mode, word, group = 'intro', None, None
    for text in paragraphs(raw):
        if not text:
            continue
        if '重点单词学一学' in text:
            mode = 'words'
            continue
        if re.match(r'^[一二三四五六七八九十]+、', text):
            mode = 'exercises'
            group = {'title': text, 'items': [], 'notes': []}
            groups.append(group)
            continue
        if '返记词汇列表' in text:
            mode = 'checklist'
            continue
        if mode == 'words':
            match = re.match(r'^(\d{2})\s*(.+)$', text)
            if match:
                label = match[2].strip()
                accent = re.search(r'[⓪①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳+]+$', label)
                if accent:
                    label = label[:accent.start()].strip()
                reading = re.search(r'[（(]([ぁ-ゖァ-ヺー・\s]+)[）)]', label)
                word = {'number': int(match[1]), 'word': label, 'reading': '',
                        'accent': accent[0] if accent else '', 'meaning': '', 'part_of_speech': ''}
                if reading:
                    word['word'] = (label[:reading.start()] + label[reading.end():]).strip()
                    word['reading'] = reading[1].replace(' ', '')
                words.append(word)
            elif word:
                definition = re.sub(r'[_＿]{2,}', '', text).strip()
                pos = re.match(r'^[〔［]([^〕］]+)[〕］]\s*', definition)
                if pos and not word['part_of_speech']:
                    word['part_of_speech'] = pos[1]
                    definition = definition[pos.end():]
                word['meaning'] += (' ' if word['meaning'] else '') + definition
            else:
                notes.append(text)
        elif mode == 'exercises':
            match = re.match(r'^(\d{2})\s*(.*)$', text)
            if match:
                group['items'].append({'number': int(match[1]), 'text': match[2].strip()})
            elif text != '音频':
                group['notes'].append(text)
    # EPUB column flow can put 11–15 before 6–10. Preserve original question numbers.
    for group in groups:
        numbers = [item['number'] for item in group['items']]
        if len(numbers) == len(set(numbers)):
            group['items'].sort(key=lambda item: item['number'])
    assert words and all(w['word'] and w['meaning'] for w in words)
    assert len(groups) == 4 and all(g['items'] for g in groups)
    return {'words': words, 'exercise_groups': groups, 'notes': notes}
