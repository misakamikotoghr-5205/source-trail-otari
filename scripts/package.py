from pathlib import Path
import zipfile
root=Path(__file__).resolve().parents[1];destination=root/'dist/source-trail.zip';destination.parent.mkdir(exist_ok=True)
files=[root/name for name in ['README.md','LICENSE','.env.example','pyproject.toml']]
for folder in ['source_trail','examples','docs','tests','scripts','experiments']:
    files.extend(path for path in (root/folder).rglob('*') if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc')
with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(files):
        info=zipfile.ZipInfo(path.relative_to(root).as_posix(), date_time=(2026,11,5,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16
        archive.writestr(info,path.read_bytes())
print(str(destination)+': source, fictional examples and docs only; no secrets, ledger or output included.')
