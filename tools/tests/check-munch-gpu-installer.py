#!/usr/bin/env python3
"""Exercise ESP file-copy guards against isolated host fixtures, never a device."""
from pathlib import Path
import argparse,tempfile,zipfile,subprocess,warnings
parser=argparse.ArgumentParser()
parser.add_argument("--stage",choices=("rpen","spmi","pmic","pep-prep","pep"),default="rpen")
args=parser.parse_args()
folder={"rpen":"GPU24","spmi":"GPU25","pmic":"GPU26","pep-prep":"GPU27","pep":"GPU28D"}[args.stage]
root=Path(__file__).resolve().parents[2]
zpath=root/('out/kona-gpu/munch-gpu-pep-prep-twrp.zip' if args.stage=='pep-prep' else f'out/kona-gpu/munch-gpu-{args.stage}-bootstrap-twrp.zip')
with zipfile.ZipFile(zpath) as z:
 src=z.read('META-INF/com/google/android/update-binary').decode()
 for scenario in ('success','wrong-model','wrong-gpt','corrupt-payload','existing-different'):
  with tempfile.TemporaryDirectory() as td:
   t=Path(td);esp=t/'esp';esp.mkdir();(t/'mounts').write_text('')
   zp=t/'input.zip';zp.write_bytes(zpath.read_bytes())
   if scenario=='corrupt-payload':
    with warnings.catch_warnings():
     warnings.simplefilter('ignore',UserWarning)
     with zipfile.ZipFile(zp,'a') as bad:bad.writestr('payload/setup.cmd',b'corrupt')
   if scenario=='existing-different':
    (esp/f'MUNCH/{folder}').mkdir(parents=True);(esp/f'MUNCH/{folder}/setup.cmd').write_text('keep')
   before={str(p.relative_to(esp)):p.read_bytes() for p in esp.rglob('*') if p.is_file()}
   model='other' if scenario=='wrong-model' else 'munch'
   gpt='0'*64 if scenario=='wrong-gpt' else 'fcd05950e644d334b97e2c0b8be9ed52fc55bcf79d8c251d62c227b47bd75bb6'
   mocks=f'''
getprop() {{ case "$1" in ro.twrp.version) echo test;; *) echo {model};; esac; }}
id() {{ echo 0; }}
readlink() {{ if [ "$2" = /dev/block/bootdevice/by-name/esp ]; then echo /dev/block/sda35; else command readlink "$@"; fi; }}
blockdev() {{ if [ "$1" = --getss ]; then echo 4096; else echo 536870912; fi; }}
dd() {{ echo GPT-MOCK; }}
sha256sum() {{ if [ "$#" = 0 ]; then cat >/dev/null; echo '{gpt}  -'; else command sha256sum "$@"; fi; }}
mount() {{ echo mount >>'{t}/writes'; }}
umount() {{ :; }}
'''
   s=src.replace('ui(){',mocks+'\nui(){',1).replace('</proc/mounts',f'<{t}/mounts')
   # Map only the mounted ESP directory into an isolated fixture.
   s=s.replace(f'DEST="$WORK/esp/MUNCH/{folder}"',f'DEST="{esp}/MUNCH/{folder}"').replace('mkdir -p "$WORK/esp/MUNCH"',f'mkdir -p "{esp}/MUNCH"')
   script=t/'install.sh';script.write_text(s)
   result=subprocess.run(['sh',str(script),'3','1',str(zp)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
   after={str(p.relative_to(esp)):p.read_bytes() for p in esp.rglob('*') if p.is_file()}
   if scenario=='success':
    assert result.returncode==0,result.stdout.decode()
    for name in z.namelist():
     if name.startswith('payload/') and name!='payload/SHA256SUMS':
      assert after[f'MUNCH/{folder}/'+name[len('payload/'):]]==z.read(name)
   else:
    assert result.returncode!=0,(scenario,result.stdout.decode())
    assert after==before,scenario
    if scenario!='existing-different': assert not (t/'writes').exists(),scenario
   print(scenario,'PASS')
