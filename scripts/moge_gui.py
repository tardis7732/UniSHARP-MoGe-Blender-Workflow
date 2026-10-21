"""MoGe tab for the existing Gradio application; heavy inference is isolated."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime
from uuid import uuid4

import gradio as gr
from moge_image import original_height

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT/'scripts'
MODELS = {'ViT-L (기본 / default)': 'Ruicheng/moge-3-vitl',
          'ViT-G (대형 / large)': 'Ruicheng/moge-3-vitg'}


def runtime_config():
    config = ROOT/'.moge-runtime.json'
    return json.loads(config.read_text(encoding='utf-8')) if config.is_file() else {}


def moge_python():
    config = runtime_config()
    executable = Path(os.environ.get('MOGE_PYTHON') or config.get('python') or
                      ROOT/('.venv-moge/Scripts/python.exe' if os.name == 'nt' else '.venv-moge/bin/python'))
    if not executable.is_file():
        raise gr.Error('MoGe 환경이 없습니다. Setup_MoGe.bat을 먼저 실행하세요. / Run Setup_MoGe.bat first.')
    return str(executable)


def blender_executable():
    configured = os.environ.get('BLENDER_EXE')
    if configured:
        return configured
    found = shutil.which('blender')
    if found:
        return found
    if os.name == 'nt':
        candidates = sorted(Path(os.environ.get('PROGRAMFILES', 'C:/Program Files')).glob('Blender Foundation/Blender */blender.exe'), reverse=True)
        if candidates:
            return str(candidates[0])
    raise gr.Error('Blender를 설치하거나 BLENDER_EXE를 설정하세요. / Set BLENDER_EXE.')


def run(command, label):
    env = os.environ.copy()
    env['PYTHONUTF8'] = '1'
    result = subprocess.run(command, cwd=ROOT, env=env, text=True, encoding='utf-8', errors='replace',
                            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if result.returncode:
        raise gr.Error(f'{label}\n{(result.stdout + result.stderr)[-5000:]}')


def generate_moge(image, folder, model_name, width, height, lock_aspect, tokens, edge, reference, save_fbx, progress=gr.Progress()):
    if not image or not Path(image).is_file():
        raise gr.Error('원본 사진을 선택해 주세요. / Select an original photograph.')
    if reference and (not Path(reference).is_file() or Path(reference).suffix.lower() != '.blend'):
        raise gr.Error('유효한 .blend 카메라 참조 파일을 선택해 주세요.')
    python, blender = moge_python(), blender_executable()
    if model_name not in MODELS:
        raise gr.Error('Unknown MoGe model.')
    if not str(folder).strip():
        raise gr.Error('출력 폴더를 입력해 주세요. / Enter an output folder.')
    name = ''.join(c if c.isalnum() or c in '-_' else '_' for c in Path(image).stem).strip('_') or 'image'
    out = Path(folder).expanduser().resolve()/f'{name}_MoGe3_{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex[:6]}'
    out.mkdir(parents=True, exist_ok=False)
    camera_file = out/'reference_camera.json'
    if reference:
        progress(.05, desc='저장된 Blender 카메라 읽는 중 / Reading saved camera')
        run([blender, '--background', '--factory-startup', '--python-exit-code', '1', '--disable-autoexec', str(Path(reference).resolve()),
             '--python', str(SCRIPTS/'read_reference_camera.py'), '--', '--output', str(camera_file)], 'Camera read failed')
    progress(.15, desc='MoGe-3 추론 중 (첫 실행은 모델 다운로드) / MoGe inference')
    model_id = MODELS[model_name]
    command = [python, str(SCRIPTS/'infer_moge.py'), '--input', str(Path(image).resolve()), '--output', str(out),
               '--model', model_id, '--width', str(int(width)), '--tokens', str(int(tokens))]
    if not lock_aspect:
        if height is None:
            raise gr.Error('세로 해상도를 입력해 주세요. / Enter a height.')
        command += ['--height', str(int(height))]
    checkpoint = runtime_config().get('checkpoints', {}).get(model_id)
    if checkpoint and Path(checkpoint).is_file():
        command += ['--checkpoint', checkpoint]
    if reference:
        command += ['--camera-json', str(camera_file)]
    run(command, 'MoGe inference failed')
    progress(.65, desc='Blender 메시·FBX 내보내는 중 / Exporting')
    command = [blender, '--background', '--factory-startup', '--python-exit-code', '1', '--python', str(SCRIPTS/'export_moge_blender.py'),
               '--', '--folder', str(out), '--name', name, '--edge-threshold', str(float(edge))]
    if reference:
        command += ['--camera-json', str(camera_file)]
    if save_fbx:
        command += ['--fbx']
    run(command, 'Blender export failed')
    blend = out/f'{name}_moge3.blend'
    expected = [blend]
    if save_fbx:
        expected += [out/f'{name}_unreal_mesh.fbx', out/f'{name}_unreal_camera.fbx', out/'texture.png']
    if any(not p.is_file() for p in expected):
        raise gr.Error('Export did not create all expected files. Inspect the output folder.')
    shutil.copyfile(ROOT/'docs/MOGE_UNREAL.md', out/'UNREAL_IMPORT.md')
    files = sorted(str(p) for p in out.iterdir() if p.is_file() and p.suffix not in {'.npz', '.npy'})
    progress(1, desc='완료 / Complete')
    return files, str(blend), f'완료 / Done: {out}'


def open_blend(path):
    if not path or not Path(path).is_file() or Path(path).suffix.lower() != '.blend':
        raise gr.Error('먼저 MoGe Blender 파일을 생성해 주세요.')
    subprocess.Popen([blender_executable(), '--disable-autoexec', str(Path(path).resolve())],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 'Blender를 열었습니다. / Opened Blender on the machine running this UI.'


def resolution_settings(image, width, locked):
    if width is None:
        return gr.update(interactive=not locked)
    if locked:
        height = original_height(image, width) if image else round(int(width)*9/16)
        return gr.update(value=height, interactive=False)
    return gr.update(interactive=True)


def build_moge_tab(default_output):
    gr.Markdown('### MoGe-3 → 텍스처 메시 · Blender · Unreal\n'
                '사진 한 장의 깊이를 추정해 실제 삼각형 메시를 만듭니다. 뒤에 가려진 면은 복원하지 않습니다.\n\n'
                '첫 설치: `Setup_MoGe.bat` 실행. 모델은 첫 변환 시 다운로드됩니다. '
                'ViT-L과 ViT-G 모두 공식 비양자화 가중치를 사용합니다.')
    with gr.Row():
        with gr.Column():
            image = gr.File(label='원본 사진 / Original photo', file_types=['image'], type='filepath')
            reference = gr.File(label='카메라 각도를 가져올 .blend (선택) / Saved workflow camera', file_types=['.blend'], type='filepath')
            gr.Markdown('이 도구에서 만든 `.blend`를 넣으면 **저장된 활성 카메라**를 복사합니다. '
                        '원본 사진과 화면 비율이 같아야 하며, 메시 크기는 중앙 깊이를 기준으로 맞춥니다.')
        with gr.Column():
            folder = gr.Textbox(value=str(Path(default_output)/'MoGe3'), label='출력 폴더 / Output folder')
            model = gr.Dropdown(choices=list(MODELS), value=next(iter(MODELS)), label='모델 / Model')
            lock_aspect = gr.Checkbox(value=True, label='원본 화면비 고정 / Lock original aspect ratio')
            with gr.Row():
                width = gr.Number(value=1536, minimum=256, maximum=4096, precision=0, label='출력 가로 px / Width')
                height = gr.Number(value=864, minimum=128, maximum=8192, precision=0, interactive=False, label='출력 세로 px / Height')
            gr.Markdown('메시 생성 해상도입니다. 원본 비율 고정 시 세로는 자동 계산됩니다. '
                        '고정 해제 시 지정한 비율로 중앙 크롭합니다. 자동 렌더는 하지 않습니다.')
            tokens = gr.Slider(1200, 3600, value=1200, step=600, label='추론 디테일 / Inference tokens')
            edge = gr.Slider(.01, .20, value=.04, step=.01, label='깊이 경계 절단: 작을수록 구멍 증가 / Edge threshold')
            fbx = gr.Checkbox(value=True, label='Unreal용 메시 FBX + 카메라 FBX + 텍스처 저장')
    generate = gr.Button('MoGe 메시·Blender 생성 / Generate', variant='primary')
    files = gr.File(label='생성 파일 / Generated files', file_count='multiple')
    blend = gr.Textbox(label='생성된 Blender 파일 / Blender file', interactive=False)
    open_button = gr.Button('Blender에서 열기 / Open in Blender')
    status = gr.Markdown()
    for component in (image, width, lock_aspect):
        component.change(resolution_settings, inputs=[image, width, lock_aspect], outputs=height, queue=False)
    generate.click(generate_moge, inputs=[image, folder, model, width, height, lock_aspect, tokens, edge, reference, fbx],
                   outputs=[files, blend, status], concurrency_id='gpu_conversion', concurrency_limit=1)
    open_button.click(open_blend, inputs=blend, outputs=status)
