import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root=Path(__file__).resolve().parents[1]
for folder in ['source_trail','scripts','tests','experiments']:
    for source in (root/folder).glob('*.py'): ast.parse(source.read_text(encoding='utf-8'), filename=str(source))
env=os.environ | {'PYTHONDONTWRITEBYTECODE':'1','SOURCE_TRAIL_MODE':'fixture'}
subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=root,env=env,check=True)
with tempfile.TemporaryDirectory() as temporary:
    command=[sys.executable,'-m','source_trail','--db',temporary+'/requests.sqlite3','suggest','examples/notes.json','--goal','Plan the fictional workshop','--key','verify-fixture-request','--out',temporary+'/output']
    result=subprocess.run(command,cwd=root,env=env,check=True,capture_output=True,text=True)
    metadata=json.loads(result.stdout);assert metadata['status']=='ready_for_human_review' and not metadata['inference_performed']
    metadata=json.loads(subprocess.run(command,cwd=root,env=env,check=True,capture_output=True,text=True).stdout)
    report=next(Path(temporary,'output').glob('*.json'))
    value=json.loads(report.read_text());assert value['replayed'] is True
    subprocess.run([sys.executable,'-m','source_trail','verify',str(report)],cwd=root,env=env,check=True)
print('Syntax, behavior tests, versioned synthetic pilot reproduction, offline CLI export and persisted replay passed. No provider call was made.')
