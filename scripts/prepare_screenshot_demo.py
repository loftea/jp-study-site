#!/usr/bin/env python3
"""Create an isolated, explicitly fictional screenshot site. Never modify an existing directory."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse, json, shutil, subprocess, sys
ROOT=Path(__file__).resolve().parents[1]

def prepare(destination):
    destination=Path(destination).resolve()
    destination.mkdir(parents=True,exist_ok=False)
    for name in filter(None,subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')):
        p=destination/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,p)
    subprocess.run([sys.executable,str(destination/'scripts/build_learning_library.py')],check=True)
    # This fixture is fictional. It is never added to a real study directory or distribution.
    date=datetime.now(ZoneInfo('Asia/Hong_Kong')).date().isoformat();stamp=date+'T10:00:00+08:00'
    sid='00000000-0000-4000-8000-000000000001'
    messages=[
        {'id':'demo-coach-1','role':'assistant','created_at':stamp,'content':'**今天的目标：描述天气**\n\n先读两个原创例句：\n｜今日《きょう》は｜晴《は》れです。\n｜空《そら》は｜青《あお》いです。\n\n请用日语说“今天是晴天”。'},
        {'id':'demo-learner-1','role':'user','created_at':stamp,'content':'今日は晴れです。'},
        {'id':'demo-coach-2','role':'assistant','created_at':stamp,'in_reply_to':'demo-learner-1','content':'句型正确。｜今日《きょう》是“今天”，｜晴《は》れ是“晴天”。\n\n这次练习已记为即时回答正确；下次再做延迟回忆。**一次回答不等于已经掌握整课。**'}]
    data={'id':sid,'title':'天气表达 · 演示课堂','lesson_id':'b01','created_at':stamp,'updated_at':stamp,'ended_at':stamp,'status':'ended','stage':'课堂小结','job':{'status':'done'},'messages':messages,'observations':[],'memory_events':[],'last_memory_updates':[],'lesson_checks':[],'completed_activities':['演示：读句与表达'],'summary':'虚构演示：完成天气表达的阅读与一句应用。教材完成状态不会因本次会话结束而自动推进。','next_step':'演示建议：下次回忆天气表达，再练习形容词句。'}
    p=destination/'study/classrooms'/f'{sid}.json';p.parent.mkdir(parents=True);p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    p=destination/'website/dist/index.html';s=p.read_text().replace('本机日语学习','演示数据 · 非真实学习记录').replace('你的长期计划','界面演示');p.write_text(s)
    print('Created fictional screenshot site; run with both live integrations disabled.')
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);a=p.parse_args();prepare(a.output)
