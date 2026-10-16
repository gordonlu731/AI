"""Explicit allowlists keep measured answers out of the AI input ZIP."""
import hashlib, json, zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'input/MANIFEST.json').read_text())
assert manifest['protocol_id']=='BW-PREDICT-002'
assert len(manifest['files'])==11
for name,digest in manifest['files'].items():
    assert Path(name).name==name
    assert hashlib.sha256((root/'input'/name).read_bytes()).hexdigest()==digest
inputs=[root/'input'/n for n in [*manifest['files'],'MANIFEST.json']]
a=root/'Bellworks-Round2-AI-Input.zip'; b=root/'Bellworks-Round2-Operator-Kit.zip'
def pack(path, files):
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for f in sorted(set(files)):z.write(f,f.relative_to(root).as_posix())
    with zipfile.ZipFile(path) as z:assert z.testzip() is None
pack(a,inputs)
validation=root/'operator/browser-validation.json'
assert json.loads(validation.read_text())['success'], 'Browser verification must complete before packaging'
assert (root/'operator/VALIDATION.md').exists()
operator=[f for f in (root/'operator').rglob('*') if f.is_file() and 'attempts' not in f.relative_to(root/'operator').parts]
pack(b,inputs+operator+[root/'README.zh-CN.md',root/'README.md',root/'config/parameters.mjs']+[root/'tools'/n for n in ['protocol.mjs','lib.mjs','freeze.mjs','score.mjs']])
with zipfile.ZipFile(a) as z:
    assert set(z.namelist())=={'input/'+f.name for f in inputs}
    assert not any('operator/' in n or 'ground-truth' in n or 'solver-evidence' in n for n in z.namelist())
(root/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in [a,b]))
for p in [a,b]:print(p.name,p.stat().st_size,'bytes, CRC and explicit file allowlist verified')
