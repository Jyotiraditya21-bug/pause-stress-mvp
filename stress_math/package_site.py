"""Publish only tracked experiment source, never local data or environments."""
from pathlib import Path
import subprocess
import zipfile


def main():
    root=Path(__file__).resolve().parent.parent
    destination=root/'frontend'/'public'/'experiment'
    destination.mkdir(parents=True,exist_ok=True)
    tracked=subprocess.check_output(['git','ls-files','-z','--','stress_math'],cwd=root).decode().split('\0')
    allowed=[]
    for name in tracked:
        if not name: continue
        p=Path(name)
        if any(part in {'.venv','cache','results','__pycache__'} for part in p.parts): continue
        if p.suffix in {'.py','.md','.txt','.obj'} or p.name in {'.gitignore','LICENSE.mediapipe'}: allowed.append(p)
    if not allowed: raise RuntimeError('No tracked experiment source; stage stress_math before packaging.')
    with zipfile.ZipFile(destination/'stress_math.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for p in sorted(allowed): archive.write(root/p,p.as_posix())
    (destination/'README.md').write_text((root/'stress_math'/'README.md').read_text())
    print(f'Packaged {len(allowed)} source files; no datasets, results or credentials.')

if __name__=='__main__': main()
