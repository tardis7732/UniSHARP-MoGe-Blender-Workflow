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


def generate_moge(image, folder, model_name, width, height, lock_aspect, tokens, edge, include_background, include_metric_reference, save_fbx, progress=gr.Progress(), save_camera_fbx=None):
    if save_camera_fbx is None:
        save_camera_fbx = save_fbx
    if not image or not Path(image).is_file():
        raise gr.Error('원본 사진을 선택해 주세요. / Select an original photograph.')
    python, blender = moge_python(), blender_executable()
    if model_name not in MODELS:
        raise gr.Error('Unknown MoGe model.')
    if not str(folder).strip():
        raise gr.Error('출력 폴더를 입력해 주세요. / Enter an output folder.')
    name = ''.join(c if c.isalnum() or c in '-_' else '_' for c in Path(image).stem).strip('_') or 'image'
    out = Path(folder).expanduser().resolve()/f'{name}_MoGe3_{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex[:6]}'
    out.mkdir(parents=True, exist_ok=False)
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
    run(command, 'MoGe inference failed')
    progress(.65, desc='Blender 메시·FBX 내보내는 중 / Exporting')
    command = [blender, '--background', '--factory-startup', '--python-exit-code', '1', '--python', str(SCRIPTS/'export_moge_blender.py'),
               '--', '--folder', str(out), '--name', name, '--edge-threshold', str(float(edge))]
    if not include_background:
        command += ['--no-background']
    if not include_metric_reference:
        command += ['--no-metric-reference']
    if save_fbx:
        command += ['--mesh-fbx']
    if save_camera_fbx:
        command += ['--camera-fbx']
    run(command, 'Blender export failed')
    blend = out/f'{name}_moge3.blend'
    expected = [blend]
    if save_fbx:
        expected += [out/f'{name}_unreal_mesh.fbx', out/'texture.png']
    if save_camera_fbx:
        expected += [out/f'{name}_unreal_camera.fbx']
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



def generate_moge_default(image, folder, lock_aspect, background, metric_reference, mesh_fbx, camera_fbx, progress=gr.Progress()):
    """Expose workflow options while retaining the tested model settings."""
    return generate_moge(image, folder, 'ViT-L (기본 / default)', 1536, 864, lock_aspect,
                         1200, .04, background, metric_reference, mesh_fbx,
                         progress=progress, save_camera_fbx=camera_fbx)


def build_moge_tab(default_output):
    gr.Markdown('### 기본 설정', elem_classes='workflow-section')
    folder = gr.Textbox(value=str(Path(default_output)/'MoGe3'), label='출력 폴더')
    with gr.Row():
        with gr.Column(scale=3):
            gr.Markdown('### 입력 이미지', elem_classes='workflow-section')
            image = gr.File(label='이미지 추가', file_types=['image'], type='filepath', height=305)
        with gr.Column(scale=2):
            gr.Markdown('### 옵션', elem_classes='workflow-section')
            lock_aspect = gr.Checkbox(value=True, label='원본 화면비 고정', info='원본 비율을 유지합니다. 해제하면 16:9로 중앙 크롭합니다.')
            background = gr.Checkbox(value=True, label='원본 이미지를 카메라 배경으로 포함')
            metric_reference = gr.Checkbox(value=True, label='1m 레퍼런스 큐브 포함')
            mesh_fbx = gr.Checkbox(value=True, label='Unreal용 메시 FBX 저장')
            camera_fbx = gr.Checkbox(value=True, label='Unreal용 카메라 FBX 저장')
    generate = gr.Button('Blender 파일 생성', variant='primary', size='lg')
    gr.Markdown('### 생성 결과', elem_classes='workflow-section')
    files = gr.File(label='생성된 파일', file_count='multiple')
    blend = gr.Textbox(label='생성된 Blender 파일', interactive=False)
    open_button = gr.Button('Blender에서 열기')
    status = gr.Markdown()
    generate.click(generate_moge_default, inputs=[image, folder, lock_aspect, background, metric_reference, mesh_fbx, camera_fbx],
                   outputs=[files, blend, status], concurrency_id='gpu_conversion', concurrency_limit=1)
    open_button.click(open_blend, inputs=blend, outputs=status)
