# MoGe-3 → Blender / Unreal Engine

## 사용

1. `Run_UniSHARP_UI.bat`으로 기존 UI 환경을 설치합니다. Python 3.11, Git, Blender 5.2, NVIDIA CUDA GPU가 필요합니다.
2. 최초 1회 `Setup_MoGe.bat`을 실행합니다. MoGe는 `.venv-moge`에 설치하며, 기존 `.venv`의 PyTorch 2.8과 공통 패키지를 읽어 사용합니다. 두 환경은 같은 폴더에 유지하세요.
3. UI의 **MoGe-3** 탭에서 원본 사진을 선택합니다. ERP/어안 대신 일반 원근 사진을 사용하세요.
   **원본 화면비 고정**이 기본으로 켜져 있어 가로 해상도를 바꾸면 세로가 자동 계산됩니다. 고정을 풀면 가로·세로를 직접 지정하고 해당 비율로 사진을 중앙 크롭합니다. 표시된 해상도는 메시 깊이 격자와 저장된 Blender 장면의 해상도이며 자동 렌더는 실행하지 않습니다. 지원 화면비는 1:2~2:1입니다.
4. 필요한 경우 이 워크플로우에서 만든 `.blend`를 카메라 참조로 추가합니다. Blender에서 먼저 저장해야 합니다. 파일의 활성 카메라를 복사하며 실시간 연동은 아닙니다.
5. **MoGe 메시·Blender 생성**을 누릅니다. ViT-L/ViT-G 공식 모델 가중치는 최초 사용 시 Hugging Face 캐시에 다운로드합니다. 둘 다 비양자화이며 추론은 FP16입니다. ViT-G는 더 많은 GPU 메모리가 필요합니다.
6. 생성 후 **Blender에서 열기**를 누릅니다. 서버 UI라면 서버 컴퓨터에서 열리므로 `.blend`를 내려받아 로컬 Blender로 여세요.

기본값은 로컬 RTX 5070 Ti에서 검증한 ViT-L, 1,200 tokens, 1,536px입니다. ViT-G 옵션은 제공하지만 이 기기에서 생성 검증하지 않았습니다. GPU 메모리가 부족하면 다른 GPU 작업을 종료하거나 해상도를 낮추세요.

## 결과

- `*_moge3.blend`: 원본 사진 텍스처를 내장한 삼각형 메시. 원본 카메라와 선택한 참조 카메라 포함.
- `source_depth_*`: 카메라 변경 전 원본 사진의 모델 깊이. TIFF는 참조 장면 스케일을 적용하기 전 모델 단위.
- `*_unreal_mesh.fbx`, `*_unreal_camera.fbx`, `texture.png`: Unreal용 파일.

단일 사진의 보이는 표면만 생성하므로 카메라를 많이 옮기면 구멍과 늘어짐이 생깁니다. 깊이 경계 절단값을 높이면 구멍이 줄어드는 대신 물체 사이를 잇는 긴 삼각형이 늘어납니다. 참조 장면과의 크기 정렬은 중앙 깊이 기준의 근사이며 절대적인 측량 정합이 아닙니다.

## Unreal에 가져오기

1. 콘텐츠 브라우저의 **Import**에서 `*_unreal_mesh.fbx`를 선택합니다. **Static Mesh**로 가져옵니다. 같은 폴더의 `texture.png`도 가져옵니다.
2. 배경용이라면 자동 충돌 생성과 Lightmap UV 생성을 끄는 편이 간단합니다. 메시가 크면 프로젝트에 맞춰 Nanite 사용을 검토하세요.
3. 머티리얼을 만들고 **Shading Model = Unlit**, 원본 텍스처 RGB를 **Emissive Color**에 연결합니다. 이 머티리얼을 메시에 지정합니다. FBX로 가져온 기본 머티리얼만으로 Blender의 unlit 표시가 자동 재현되지는 않습니다.
4. 뒤에서 보아야 하면 **Two Sided**를 켤 수 있지만, 사진에 없는 뒤쪽 구조가 생기는 것은 아닙니다.
5. 메시는 레벨에 배치합니다. 카메라는 Sequencer의 FBX 카메라 임포트로 가져오고, Filmback의 Custom 센서 크기를 유지합니다. 메시와 카메라를 함께 이동해야 상대 위치가 유지됩니다.
6. Unreal의 노출·톤매핑에 따라 사진 밝기와 색이 달라질 수 있으므로 최종 카메라에서 확인합니다.

Blender에서 각도를 다시 바꾼 경우 먼저 저장하세요. 이 UI에 새 `.blend`를 참조로 넣으면 저장된 카메라를 새 메시 장면에 복사합니다. 변환은 파일 내보내기만 수행하며 컬러 이미지나 카메라 깊이 이미지를 자동 렌더하지 않습니다.

## 설치/실행 설정

`BLENDER_EXE`로 Blender 실행 파일, `MOGE_PYTHON`으로 이미 설치된 MoGe Python을 지정할 수 있습니다. 선택적 `.moge-runtime.json`은 로컬 전용이며 Git에서 제외됩니다:

```json
{"python": "D:/tools/moge/Scripts/python.exe", "checkpoints": {"Ruicheng/moge-3-vitl": "D:/models/moge-3-vitl/model.pt"}}
```

## 출처

- [MoGe 공식 코드](https://github.com/microsoft/MoGe)
- [MoGe-3 ViT-L 모델](https://huggingface.co/Ruicheng/moge-3-vitl)
- [Unreal FBX Static Mesh Pipeline](https://dev.epicgames.com/documentation/en-us/unreal-engine/fbx-static-mesh-pipeline-in-unreal-engine)
- [Unreal Sequencer FBX Import/Export](https://dev.epicgames.com/documentation/en-us/unreal-engine/import-and-export-cinematic-fbx-animations-in-unreal-engine)
