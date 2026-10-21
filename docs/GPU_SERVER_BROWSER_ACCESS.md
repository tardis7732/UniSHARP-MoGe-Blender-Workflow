# GPU 서버 브라우저/PIN 실행

GPU 서버에서 브라우저 UI를 열려면 프로젝트 Python 환경에서 실행합니다.

```bash
cd ~/air/unisharp-blender
export UNISHARP_UI_PIN='123457'
bash scripts/run_browser_ui.sh --share
```

터미널에 임시 `gradio.live` 주소가 출력됩니다. 브라우저 로그인 창에서 Username은 비워 두고 Password에 PIN을 넣습니다.

`--share` URL은 실행할 때마다 바뀝니다. 고정 URL은 서버 플랫폼에서 포트/도메인 ingress를 만든 뒤 아래처럼 실행해야 합니다.

```bash
bash scripts/run_browser_ui.sh --host 0.0.0.0 --port 7860
```

`BLENDER_EXE` 환경 변수가 있으면 해당 Blender 실행 파일을 사용합니다. 없으면 PATH의 `blender` 명령을 사용합니다.
