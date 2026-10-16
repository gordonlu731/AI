"""Build the complete local application archive from versioned/eligible source.
Run after npm run build. Requires Python only for maintainers packaging a release.
"""
from pathlib import Path
import subprocess, zipfile
root=Path(__file__).resolve().parents[1]
paths=subprocess.check_output(['git','ls-files','-co','--exclude-standard','--','.'],cwd=root,text=True).splitlines()
files=[]
for name in set(paths):
    p=root/name
    if not p.is_file() or p.suffix=='.zip' or p.name=='SHA256SUMS.txt':continue
    files.append(p)
files.extend(p for p in (root/'dist').rglob('*') if p.is_file())
assert root/'dist/round2.html' in files
assert root/'dist/index.html' in files
out=root/'Bellworks.zip'
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in sorted(set(files)):z.write(p,'Bellworks/'+p.relative_to(root).as_posix())
with zipfile.ZipFile(out) as z:
    assert z.testzip() is None
    assert not any('/node_modules/' in n or '/attempts/' in n or '/releases/' in n or 'response.json' in n for n in z.namelist())
    print(f'{out.name}: {len(z.namelist())} files, {out.stat().st_size} bytes, CRC verified; private attempts excluded.')
