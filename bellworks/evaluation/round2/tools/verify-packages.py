"""Extract into a clean temp directory; no npm or app dependencies available."""
import hashlib,json,subprocess,tempfile,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='bellworks-round2-pack-') as task_tmp:
    task=Path(task_tmp)
    for name,target in [('Bellworks-Round2-AI-Input.zip','a'),('Bellworks-Round2-Operator-Kit.zip','b')]:
        with zipfile.ZipFile(root/name) as z:
            assert z.testzip() is None
            z.extractall(task/target)
    a,b=task/'a',task/'b'
    for rel,digest in json.loads((a/'input/MANIFEST.json').read_text())['files'].items():
        assert hashlib.sha256((a/'input'/rel).read_bytes()).hexdigest()==digest
        assert (a/'input'/rel).read_bytes()==(b/'input'/rel).read_bytes()
    key=json.loads((b/'operator/ground-truth.json').read_text())
    fixture={'protocol_id':key['protocol_id'],'cases':[dict(id=c['id'],bell_by_30s=c['bell_by_30s'],p_bell_by_30s=.9 if c['bell_by_30s'] else .1,stages=c['stages'],contacts=c['contacts'],predicted_first_bell_seconds=None,first_interruption='SYNTHETIC',reasoning='SYNTHETIC SOFTWARE FIXTURE, NOT AN AI PREDICTION') for c in key['cases']]}
    (b/'synthetic.json').write_text(json.dumps(fixture))
    subprocess.run(['node','tools/freeze.mjs','synthetic.json','--id','synthetic-check','--model','SYNTHETIC_NOT_A_MODEL'],cwd=b,check=True,capture_output=True,text=True)
    subprocess.run(['node','tools/score.mjs','operator/attempts/synthetic-check'],cwd=b,check=True,capture_output=True,text=True)
    result=json.loads((b/'operator/attempts/synthetic-check/score.json').read_text())
    assert result['total_100']==100 and abs(result['brier_score']-.01)<1e-12
    print('PASS: A/B CRC, identical input hashes; extracted operator kit freezes and scores a synthetic fixture without npm or project dependencies. Temp fixture removed.')
