#!/usr/bin/env python3
"""Package an explicit committed ref; never include untracked runtime files."""
from pathlib import Path
import argparse, hashlib, io, json, re, subprocess, tarfile, zipfile
ROOT=Path(__file__).resolve().parents[1]

def package(ref,output):
    if not re.fullmatch(r'v\d+\.\d+\.\d+(?:-[a-z0-9.-]+)?',ref):raise ValueError('Use an explicit version tag such as v0.1.0')
    commit=subprocess.check_output(['git','rev-parse','--verify',ref+'^{commit}'],cwd=ROOT,text=True).strip()
    raw=subprocess.check_output(['git','archive','--format=tar',commit],cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        files={m.name:archive.extractfile(m).read() for m in archive if m.isfile()}
    assert 'LICENSE' in files and 'NOTICE' in files
    destination=Path(output).resolve();destination.mkdir(parents=True,exist_ok=False)
    def write(name,items):
        p=destination/name
        with zipfile.ZipFile(p,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for key,data in sorted(items.items()):
                entry=zipfile.ZipInfo(key,(2026,1,1,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o644<<16;z.writestr(entry,data)
        return {'name':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'files':len(items)}
    results=[write('jp-study-site-'+ref+'.zip',{'jp-study-site-'+ref+'/'+name:content for name,content in files.items()})]
    skills={name.removeprefix('skills/'):content for name,content in files.items() if name.startswith('skills/')}
    for skill in ('jp-study-site','jp-listening-tts'):
        for name in ('LICENSE','NOTICE'):skills[skill+'/'+name]=files[name]
    results.append(write('jp-study-skills-'+ref+'.zip',skills))
    (destination/'SHA256SUMS').write_text(''.join(item['sha256']+'  '+item['name']+'\n' for item in results))
    (destination/'release-manifest.json').write_text(json.dumps({'version':ref,'commit':commit,'artifacts':results},indent=2)+'\n')
    print(json.dumps({'version':ref,'commit':commit,'artifacts':results},indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ref',required=True);p.add_argument('--output',required=True,type=Path);a=p.parse_args();package(a.ref,a.output)
