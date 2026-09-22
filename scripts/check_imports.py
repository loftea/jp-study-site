"""Original synthetic material only; run in the disposable release-test copy."""
from pathlib import Path
import json, subprocess, sys, tempfile, zipfile
from build_learning_library import build
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='jp-import-fixture-') as tmp:
    root=Path(tmp);profile=root/'study/profile.json';profile.parent.mkdir()
    profile.write_text('{"preferences":{"language":"fixture"}}')
    before=profile.read_bytes();build(ROOT/'examples/library.demo.json',root)
    assert profile.read_bytes()==before
    assert json.loads((root/'website/dist/data/legacy-classrooms.json').read_text())==[]
    data=json.loads((root/'website/dist/data/library.json').read_text())
    assert data['study']['sessions_completed']==0 and not data['vocabulary']
    # A small original EPUB proves the importer doesn't depend on the developer's books.
    source=root/'sample.epub'
    with zipfile.ZipFile(source,'w') as z:
        z.writestr('META-INF/container.xml','<container><rootfiles><rootfile full-path="OEBPS/content.opf"/></rootfiles></container>')
        z.writestr('OEBPS/content.opf','<package xmlns="http://www.idpf.org/2007/opf"><manifest><item id="a" href="chapter.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="a"/></spine></package>')
        z.writestr('OEBPS/chapter.xhtml','<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Original fixture</title></head><body><p>晴れです。</p><script>alert(1)</script></body></html>')
    cmd=[sys.executable,str(ROOT/'scripts/build_reading_library.py'),'--source',str(source),'--id','release-test-reader','--title','Original fixture']
    subprocess.run(cmd,check=True)
    chapter=json.loads((ROOT/'website/dist/reading/release-test-reader/c001.json').read_text())
    assert '晴れです。' in chapter['html'] and 'script' not in chapter['html'] and 'alert' not in chapter['html']
print('PASS: clean library, preserved profile, empty history and original EPUB import with scripts removed.')
