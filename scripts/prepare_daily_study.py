"""Prepare the homepage without starting a classroom or changing learner evidence."""
from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'website'))
from daily_preparation import DailyPreparation

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--context',action='store_true',help='Read current facts and fingerprint for coach preparation')
    parser.add_argument('--publish-draft',type=Path,help='Validate and save a JSON coach draft')
    parser.add_argument('--trigger',default='manual',choices=['manual','scheduled'])
    args=parser.parse_args();preparation=DailyPreparation(ROOT)
    try:
        result=preparation.context() if args.context else preparation.get(args.trigger,json.loads(args.publish_draft.read_text()) if args.publish_draft else None)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except ValueError as e:print(str(e),file=sys.stderr);sys.exit(1)
