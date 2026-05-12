import os
import subprocess
import zipfile

output = subprocess.check_output(['git', 'ls-files', '-mo', '--exclude-standard']).decode('utf-8')
files_to_zip = output.split('\n')

with zipfile.ZipFile('update.zip', 'w', zipfile.ZIP_DEFLATED) as zf:
    for f in files_to_zip:
        f = f.strip()
        if not f: continue
        if 'molecular-design-source.zip' in f: continue
        if 'deploy_sync.tar' in f: continue
        if f.startswith('scratch/') or f.startswith('src/'): continue
        if os.path.isfile(f):
            print(f"Adding {f}")
            zf.write(f)
