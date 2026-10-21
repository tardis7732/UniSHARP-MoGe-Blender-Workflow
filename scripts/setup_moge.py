"""Install MoGe separately, reusing the existing UI environment's PyTorch."""
import json
import os
from pathlib import Path
import site
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]


def main():
    import torch
    if not torch.__version__.startswith('2.8.'):
        raise RuntimeError('This tested installer expects PyTorch 2.8.x (see requirements.txt).')
    target = ROOT/'.venv-moge'
    venv.EnvBuilder(with_pip=True).create(target)
    python = target/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    sites = json.loads(subprocess.check_output([str(python), '-c', 'import site,json; print(json.dumps(site.getsitepackages()))'], text=True))
    target_site = next(Path(x) for x in sites if Path(x).name in ('site-packages', 'dist-packages'))
    base_sites = [str(Path(x).resolve()) for x in site.getsitepackages() if Path(x).is_dir()]
    (target_site/'workflow-base.pth').write_text('\n'.join(base_sites)+'\n', encoding='utf-8')
    packages = [
        'triton-windows==3.4.0.post21' if os.name == 'nt' else 'triton==3.4.0',
        'git+https://github.com/EasternJournalist/utils3d-moge.git@62f09d58509485564e24d5d9f6aac9ee9ebc0c37',
        'git+https://github.com/EasternJournalist/pipeline.git@1c511390d90226c00c101f34b84df26a0f8789b4',
        'git+https://github.com/JeffreyXiang/FlexGEMM.git@b2fadb29d41846c7981ade6801ffc689fae119cf',
        'git+https://github.com/microsoft/MoGe.git@74fbce054ebed49800de42d0ad0e83495065719a',
    ]
    subprocess.run([str(python), '-m', 'pip', 'install', '--no-deps', *packages], check=True)
    subprocess.run([str(python), '-c', 'import torch; from moge.model.v3 import MoGeModel; print("MoGe ready:", torch.cuda.is_available())'], check=True)
    config_file = ROOT/'.moge-runtime.json'
    config = json.loads(config_file.read_text(encoding='utf-8')) if config_file.is_file() else {}
    config['python'] = str(python)
    config_file.write_text(json.dumps(config, indent=2), encoding='utf-8')
    print('MoGe ready. Start Run_UniSHARP_UI.bat and select the MoGe-3 tab.')


if __name__ == '__main__':
    main()
