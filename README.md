# UniSHARP + MoGe Blender Workflow

단일 이미지를 **UniSHARP Gaussian** 또는 **MoGe-3 텍스처 메시**로 변환하는 Blender / Unreal용 도구입니다. 기존 UniSHARP 기능과 MoGe 기능을 별도 탭에서 선택합니다.

## MoGe-3 추가 기능

- 공식 비양자화 ViT-L / ViT-G 모델 선택, 입력 해상도와 디테일 조절
- 원본 화면비 고정(기본), 가로·세로 해상도 설정. 고정 해제 시 중앙 크롭.
- 이미지 → 깊이맵 → UV 텍스처 삼각형 메시 → `.blend`
- 기존 워크플로우 `.blend`의 저장된 카메라 위치·회전·렌즈 복사 (선택)
- 모델이 추정한 원본 시점 깊이맵 저장 (별도 카메라 렌더 없음)
- Unreal Static Mesh용 **FBX + 원본 텍스처 + 카메라 FBX**
- 생성된 파일을 Blender에서 바로 열기

`Run_UniSHARP_UI.bat`으로 기본 환경을 설치한 뒤 **`Setup_MoGe.bat`을 최초 1회 실행**하고, UI의 **MoGe-3 · Depth Mesh** 탭을 선택하세요. 설치에는 Git도 필요합니다. 기본 모델은 ViT-L이며 ViT-G는 더 많은 VRAM이 필요합니다. [MoGe/Unreal 사용 안내](docs/MOGE_UNREAL.md)

사진에 가려진 뒷면은 생성하지 않습니다. 카메라를 옮기면 구멍이 나타날 수 있습니다. 참조 장면의 크기는 중앙 깊이로 맞추므로 서로 다른 추정 모델 사이의 정합은 근사입니다.

> [Insta360 Research Team의 UniSHARP](https://github.com/Insta360-Research-Team/UniSHARP)를 기반으로 한 비공식 워크플로우입니다. 연구 코드·논문·모델의 원본 정보는 [UniSHARP 원본 저장소](https://github.com/Insta360-Research-Team/UniSHARP)를 참고하세요.

## 일반 사용자 실행 (Windows)

1. 64-bit Python 3.11과 Blender 5.2를 설치합니다.
2. 저장소 최상단의 **`Run_UniSHARP_UI.bat`** 파일을 더블클릭합니다.
3. 브라우저가 열리지 않으면 `http://127.0.0.1:7860`으로 접속합니다.

첫 실행에서는 가상환경 생성과 패키지 설치가 자동으로 진행됩니다. 모델 체크포인트도 첫 변환 시 약 4.7GB가 자동 다운로드됩니다. 설치 및 사용 중에는 배치 파일이 연 검은 창을 닫지 마세요.

## Windows 설치 및 가상환경 설정

일반 사진을 `Perspective` 모드로 변환하는 기준입니다. NVIDIA GPU와 Blender가 설치되어 있어야 하며, Python은 **3.11 (64-bit)** 사용을 권장합니다.

PowerShell에서 저장소 폴더로 이동한 뒤 가상환경을 만들고 활성화합니다.

```powershell
cd "C:\경로\UniSHARP-Blender-Workflow"
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

PowerShell 실행 정책 때문에 활성화가 막히면, 현재 창에만 적용되도록 아래 명령을 한 번 실행한 뒤 다시 활성화합니다.

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

패키지를 설치합니다. RTX 50 시리즈처럼 최신 GPU에서는 NVIDIA CUDA에 맞는 PyTorch 설치 명령을 [PyTorch 설치 페이지](https://pytorch.org/get-started/locally/)에서 먼저 확인한 뒤, 나머지 패키지를 설치하세요.

```powershell
python -m pip install --upgrade pip
pip install torch==2.8.0 torchvision==0.23.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements.txt
```

Blender가 PATH에 없으면 설치 파일 경로를 환경 변수로 지정합니다. 예를 들어 Blender 5.2의 기본 설치 경로는 다음과 같습니다.

```powershell
$env:BLENDER_EXE = "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
```

가상환경을 종료할 때는 `deactivate`를 실행합니다. 다음에 다시 사용할 때는 저장소 폴더에서 `.\.venv\Scripts\Activate.ps1`만 실행하면 됩니다.

## 실행

프로젝트 Python 환경에서 아래 한 줄로 브라우저 UI를 엽니다.

```powershell
python scripts/blender_gui.py
```

첫 변환 때는 UniSHARP 체크포인트(약 4.7GB)를 Hugging Face에서 자동으로 받습니다. UI에서 이미지 한 장을 추가하고, 일반 사진은 카메라 종류를 `Perspective`로 선택하세요. 결과는 기본적으로 `Blender_Output` 폴더에 저장됩니다.

어안(`Fisheye`) 모드는 별도 3DGEER rasterizer 빌드가 필요하므로, 해당 구성요소를 설치하지 않았다면 사용하지 마세요.

서버 브라우저 접속용 PIN UI는 다음과 같이 실행합니다.

```bash
export UNISHARP_UI_PIN='123457'
bash scripts/run_browser_ui.sh --share
```

`BLENDER_EXE`가 설정돼 있으면 그 실행 파일을 쓰고, 그렇지 않으면 PATH의 `blender` 명령을 사용합니다. 체크포인트가 없을 때는 공식 Hugging Face 배포처에서 자동으로 받습니다.

## 생성 파일

- `<이름>_unisharp.blend` — Gaussian 포인트와 카메라가 포함된 Blender 장면
- `<이름>_unreal_gaussian_splat.ply` — Unreal Gaussian Splat 플러그인용 PLY
- `<이름>_unreal_camera.fbx` — Unreal Engine으로 가져올 수 있는 소스 카메라 FBX (UI 옵션 사용 시)

카메라 FBX는 원본 이미지의 가로·세로 화각과 주점을 함께 맞춰 내보냅니다. Unreal에서 임포트한 카메라는 Filmback을 임의의 Full Frame 프리셋으로 바꾸지 말고, `Custom` 센서 값을 유지하세요.

## 문서

- [GPU 서버 브라우저/PIN 접속](docs/GPU_SERVER_BROWSER_ACCESS.md)
- [서드파티 고지 및 라이선스](THIRD_PARTY_NOTICES.md)

## 라이선스

- UniSHARP 기반 소스: [CC BY-NC 4.0](LICENSE)
- 포함된 `UniK3D/` 소스: [CC BY-NC-SA 4.0](UniK3D/LICENSE)

상업적 사용 또는 재배포 전에는 원 저작권자와 각 외부 구성요소의 라이선스를 확인하세요.
