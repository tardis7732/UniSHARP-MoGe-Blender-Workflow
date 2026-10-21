"""Local GUI for converting normal images to UniSHARP Blender scenes."""

from __future__ import annotations

import argparse
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
UNISHARP_PYTHON = REPO_ROOT.parent / "miniforge3" / "envs" / "unisharp" / "python.exe"
if UNISHARP_PYTHON.is_file() and Path(sys.executable).resolve() != UNISHARP_PYTHON.resolve():
    os.execv(str(UNISHARP_PYTHON), [str(UNISHARP_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])

import gradio as gr
from moge_gui import build_moge_tab, blender_executable


SCRIPTS = REPO_ROOT / "scripts"
DEFAULT_CHECKPOINT = REPO_ROOT / "checkpoints" / "pretained_model.pt"
CHECKPOINT_REPOSITORY = "Insta360-Research/Unisharp"
CHECKPOINT_FILENAME = "pretained_model.pt"
APP_ROOT = Path(os.environ.get("UNISHARP_APP_ROOT", REPO_ROOT)).resolve()
DEFAULT_OUTPUT = APP_ROOT / "Blender_Output"
VIEWER_SCRIPT = SCRIPTS / "viser_ply_viewer.py"
_VIEWER_PROCESS: subprocess.Popen[str] | None = None


TEXT = {
    "ko": {
        "title": "이미지 → UniSHARP / MoGe 3D",
        "language": "언어",
        "basic": "### 기본 설정",
        "output_folder": "출력 폴더",
        "camera_kind": "카메라 종류",
        "input": "### 입력 이미지",
        "images": "이미지 추가 (일반 / 어안 / ERP 파노라마)",
        "options": "### 옵션",
        "force_square": "정사각형 픽셀 강제 (세로 오버레이 보정)",
        "force_square_info": "원근 사진에서만 적용됩니다. 추정된 fx를 유지하고 fy=fx로 맞춥니다.",
        "background": "원본 이미지를 카메라 배경으로 포함",
        "metric_reference": "1m 레퍼런스 큐브 포함",
        "save_ply": "Unreal용 Gaussian Splat PLY 저장",
        "save_camera_fbx": "Unreal용 카메라 FBX 저장",
        "generate": "Blender 파일 생성",
        "result": "### 생성 결과",
        "result_files": "생성된 파일",
        "viewer_title": "## Unreal용 Gaussian Splat PLY 미리보기",
        "viewer_ply": "미리보기할 PLY",
        "open_viewer": "PLY 미리보기 열기",
        "viewer_empty": "PLY를 선택한 뒤 미리보기를 열어 주세요.",
        "auto": "자동",
        "perspective": "원근",
        "fisheye": "어안",
        "panorama": "파노라마",
        "checkpoint_downloading": "UniSHARP 모델 체크포인트가 없어 다운로드합니다. 최초 1회 약 4.7GB를 받으므로 인터넷 연결과 여유 공간이 필요합니다.",
        "checkpoint_failed": "UniSHARP 체크포인트를 다운로드하지 못했습니다: {detail}",
        "images_required": "이미지를 하나 이상 선택해 주세요.",
        "image_missing": "입력 이미지를 찾지 못했습니다: {path}",
        "inference": "UniSHARP 추론",
        "color_conversion": "색상 변환",
        "blender_export": "Blender 내보내기",
        "unreal_export": "Unreal PLY 내보내기",
        "done": "완료: 파일 {count}개를 생성했습니다.\n\n{destination}",
        "viewer_select": "미리보기할 Unreal용 Gaussian Splat PLY를 선택해 주세요.",
        "viewer_missing": "PLY를 찾지 못했습니다: {path}",
        "viewer_failed": "PLY 뷰어를 시작하지 못했습니다.",
    },
    "en": {
        "title": "Image → UniSHARP / MoGe 3D",
        "language": "Language",
        "basic": "### Basic Settings",
        "output_folder": "Output Folder",
        "camera_kind": "Camera Type",
        "input": "### Input Image",
        "images": "Add Images (standard / fisheye / ERP panorama)",
        "options": "### Options",
        "force_square": "Force square pixels (vertical overlay correction)",
        "force_square_info": "Perspective images only. Keeps the estimated fx and sets fy=fx.",
        "background": "Include source image as camera background",
        "metric_reference": "Include 1 m reference cube",
        "save_ply": "Save Unreal Gaussian Splat PLY",
        "save_camera_fbx": "Save Unreal Camera FBX",
        "generate": "Create Blender File",
        "result": "### Result",
        "result_files": "Generated Files",
        "viewer_title": "## Unreal Gaussian Splat PLY Preview",
        "viewer_ply": "PLY to Preview",
        "open_viewer": "Open PLY Preview",
        "viewer_empty": "Select a PLY file, then open the preview.",
        "auto": "Auto",
        "perspective": "Perspective",
        "fisheye": "Fisheye",
        "panorama": "Panorama",
        "checkpoint_downloading": "The UniSHARP model checkpoint is missing and will be downloaded. The first download is about 4.7 GB, so an internet connection and free disk space are required.",
        "checkpoint_failed": "Could not download the UniSHARP checkpoint: {detail}",
        "images_required": "Select at least one image.",
        "image_missing": "Input image was not found: {path}",
        "inference": "UniSHARP inference",
        "color_conversion": "Color conversion",
        "blender_export": "Blender export",
        "unreal_export": "Unreal PLY export",
        "done": "Done: created {count} file(s).\n\n{destination}",
        "viewer_select": "Select an Unreal Gaussian Splat PLY to preview.",
        "viewer_missing": "PLY was not found: {path}",
        "viewer_failed": "Could not start the PLY viewer.",
    },
}


def _t(language: str, key: str, **values: object) -> str:
    return TEXT.get(language, TEXT["ko"])[key].format(**values)


def _camera_choices(language: str) -> list[tuple[str, str]]:
    return [
        (_t(language, "auto"), "auto"),
        (_t(language, "perspective"), "perspective"),
        (_t(language, "fisheye"), "fisheye"),
        (_t(language, "panorama"), "panorama"),
    ]


def _header_html(language: str) -> str:
    return (
        "<div id='unisharp-header'><h1>"
        f"{_t(language, 'title')}</h1>"
        "<a href='https://github.com/tardis7732/UniSHARP-MoGe-Blender-Workflow' target='_blank' rel='noopener'>GitHub ↗</a></div>"
    )


def _blender_executable() -> str:
    """Share executable discovery with the MoGe tab, including Windows installs."""
    return blender_executable()


def _ensure_checkpoint(language: str) -> Path:
    if DEFAULT_CHECKPOINT.is_file():
        return DEFAULT_CHECKPOINT
    try:
        from huggingface_hub import hf_hub_download

        DEFAULT_CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
        gr.Info(_t(language, "checkpoint_downloading"), duration=10)
        hf_hub_download(
            repo_id=CHECKPOINT_REPOSITORY,
            filename=CHECKPOINT_FILENAME,
            local_dir=DEFAULT_CHECKPOINT.parent,
        )
    except Exception as error:
        raise gr.Error(_t(language, "checkpoint_failed", detail=str(error)[-500:])) from error
    if not DEFAULT_CHECKPOINT.is_file():
        raise gr.Error(_t(language, "checkpoint_failed", detail="download finished without the expected file"))
    return DEFAULT_CHECKPOINT


def _language_updates(language: str) -> tuple[object, ...]:
    """Return all visible UI text updates while preserving user-selected values."""
    return (
        _header_html(language),
        _t(language, "basic"),
        gr.update(label=_t(language, "output_folder")),
        gr.update(label=_t(language, "camera_kind"), choices=_camera_choices(language)),
        _t(language, "input"),
        gr.update(label=_t(language, "images")),
        _t(language, "options"),
        gr.update(label=_t(language, "force_square"), info=_t(language, "force_square_info")),
        gr.update(label=_t(language, "background")),
        gr.update(label=_t(language, "metric_reference")),
        gr.update(label=_t(language, "save_ply")),
        gr.update(label=_t(language, "save_camera_fbx")),
        gr.update(value=_t(language, "generate")),
        _t(language, "result"),
        gr.update(label=_t(language, "result_files")),
        _t(language, "viewer_title"),
        gr.update(label=_t(language, "viewer_ply")),
        gr.update(value=_t(language, "open_viewer")),
        f"<div>{_t(language, 'viewer_empty')}</div>",
    )


def _run(command: list[str], label: str) -> None:
    completed = subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True, errors="replace")
    if completed.returncode:
        detail = (completed.stderr or completed.stdout or "No diagnostic output").strip()
        raise RuntimeError(f"{label} failed.\n\n{detail[-4000:]}")


def _safe_name(image: Path) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "_" for char in image.stem).strip("._") or "unisharp_scene"


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_for_local_port(port: int, timeout_seconds: float = 8.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                return True
        except OSError:
            time.sleep(0.15)
    return False


def open_ply_viewer(selected_ply: str | None, language: str) -> str:
    """Start a local Viser WebGL viewer and return an iframe for Gradio."""
    global _VIEWER_PROCESS
    if not selected_ply:
        raise gr.Error(_t(language, "viewer_select"))
    ply_path = Path(selected_ply).resolve()
    if not ply_path.is_file():
        raise gr.Error(_t(language, "viewer_missing", path=ply_path))
    if _VIEWER_PROCESS is not None and _VIEWER_PROCESS.poll() is None:
        _VIEWER_PROCESS.terminate()
        try:
            _VIEWER_PROCESS.wait(timeout=3)
        except subprocess.TimeoutExpired:
            _VIEWER_PROCESS.kill()
    port = _free_local_port()
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    _VIEWER_PROCESS = subprocess.Popen(
        [sys.executable, str(VIEWER_SCRIPT), str(ply_path), "--port", str(port)],
        cwd=REPO_ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    if not _wait_for_local_port(port):
        raise gr.Error(_t(language, "viewer_failed"))
    url = f"http://127.0.0.1:{port}"
    return f'<iframe src="{url}" style="width:100%; height:720px; border:1px solid #444; border-radius:8px;"></iframe>'


def _generate_one(
    image: Path,
    scene_name: str,
    destination: Path,
    camera_kind: str,
    force_square_pixels: bool,
    include_background: bool,
    include_metric_reference: bool,
    save_ply: bool,
    save_camera_fbx: bool,
    checkpoint_path: Path,
    blender: str,
    language: str,
) -> list[str]:
    image = image.resolve()
    output_blend = destination / f"{scene_name}_unisharp.blend"
    output_ue_ply = destination / f"{scene_name}_unreal_gaussian_splat.ply"
    output_camera_fbx = destination / f"{scene_name}_unreal_camera.fbx"
    with tempfile.TemporaryDirectory(prefix="unisharp_blender_") as temp:
        temp_root = Path(temp)
        inference_command = [
            sys.executable,
            str(SCRIPTS / "infer_unisharp.py"),
            "--checkpoint",
            str(checkpoint_path),
            "--image",
            str(image),
            "--out-dir",
            str(temp_root),
            "--camera",
            camera_kind,
            "--save-ply",
            "--blender-only",
        ]
        if force_square_pixels and camera_kind in {"auto", "perspective"}:
            inference_command.append("--force-square-pixels")
        _run(inference_command, _t(language, "inference"))
        gaussian_files = list(temp_root.rglob("gaussians.ply"))
        if len(gaussian_files) != 1:
            raise RuntimeError("UniSHARP did not produce the expected Gaussian PLY.")
        source_ply = gaussian_files[0]
        colored_ply = temp_root / "colored_points.ply"
        _run([sys.executable, str(SCRIPTS / "export_colored_ply.py"), str(source_ply), str(colored_ply)], _t(language, "color_conversion"))
        blender_command = [
            blender,
            "--background",
            "--factory-startup",
            "--python",
            str(SCRIPTS / "make_blender_camera_preview.py"),
            "--",
            str(source_ply),
            str(colored_ply),
            str(image),
            str(output_blend),
            "--point-radius",
            "0.006",
            "--orientation",
            "negative_x_xminus90",
        ]
        if not include_background:
            blender_command.append("--no-background")
        if not include_metric_reference:
            blender_command.append("--no-metric-reference")
        if save_camera_fbx:
            blender_command.extend(["--output-camera-fbx", str(output_camera_fbx)])
        _run(blender_command, _t(language, "blender_export"))
        if not output_blend.is_file():
            raise RuntimeError("Blender exited without creating the requested .blend file.")
        if save_camera_fbx and not output_camera_fbx.is_file():
            raise RuntimeError("Blender exited without creating the requested Unreal camera FBX.")
        if save_ply:
            _run([sys.executable, str(SCRIPTS / "export_ue_gaussian_ply.py"), str(source_ply), str(output_ue_ply)], _t(language, "unreal_export"))
    return [
        str(path)
        for path in (output_blend, output_ue_ply if save_ply else None, output_camera_fbx if save_camera_fbx else None)
        if path is not None
    ]


def generate_blend(
    images: list[str] | str | None,
    output_folder: str,
    camera_kind: str,
    force_square_pixels: bool,
    include_background: bool,
    include_metric_reference: bool,
    save_ply: bool,
    save_camera_fbx: bool,
    language: str,
) -> tuple[list[str], str, dict[str, object]]:
    paths = [Path(item) for item in ([images] if isinstance(images, str) else (images or []))]
    if not paths:
        raise gr.Error(_t(language, "images_required"))
    destination = Path(output_folder).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    checkpoint_path = _ensure_checkpoint(language)
    blender = _blender_executable()
    final_files: list[str] = []
    ply_files: list[str] = []
    for image in paths:
        if not image.is_file():
            raise gr.Error(_t(language, "image_missing", path=image))
        scene_name = _safe_name(image) + ("_square_pixels" if force_square_pixels and camera_kind in {"auto", "perspective"} else "")
        final_files.extend(
            _generate_one(
                image,
                scene_name,
                destination,
                camera_kind,
                force_square_pixels,
                include_background,
                include_metric_reference,
                save_ply,
                save_camera_fbx,
                checkpoint_path,
                blender,
                language,
            )
        )
        if save_ply:
            output_ply = destination / f"{scene_name}_unreal_gaussian_splat.ply"
            if output_ply.is_file():
                ply_files.append(str(output_ply))
    selected_ply = ply_files[0] if len(ply_files) == 1 else None
    return final_files, _t(language, "done", count=len(final_files), destination=destination), gr.update(choices=ply_files, value=selected_ply)


CUSTOM_CSS = """
        #unisharp-header { display: flex; align-items: center; gap: 0.8rem; margin: 0.2rem 0 1.1rem; }
        #unisharp-header h1 { margin: 0; }
        #unisharp-header a { color: #8b949e; font-size: 0.9rem; text-decoration: none; }
        #unisharp-header a:hover { color: #f0f6fc; text-decoration: underline; }
        #section-basic, #section-input, #section-options, #section-result, .workflow-section {
            border: 0;
            border-radius: 0;
            padding: 0;
            margin: 0;
        }
        #section-basic h3, #section-input h3, #section-options h3, #section-result h3, .workflow-section h3 {
            color: inherit;
            border-left: 3px solid #6e7681;
            padding: 0.05rem 0 0.05rem 0.65rem;
            margin: 1.1rem 0 0.55rem;
        }
        #generate-button { margin: 0.8rem 0; }
"""


with gr.Blocks(title="UniSHARP + MoGe Blender Workflow") as demo:
    with gr.Row():
        header = gr.HTML(_header_html("ko"), scale=8)
        language = gr.Dropdown(
            choices=[("한국어", "ko"), ("English", "en")],
            value="ko",
            label="언어 / Language",
            show_label=True,
            scale=1,
            min_width=150,
        )

    with gr.Tab("UniSHARP · Gaussian"):
        with gr.Column():
            basic_heading = gr.Markdown(_t("ko", "basic"), elem_id="section-basic")
            with gr.Row():
                output_folder = gr.Textbox(label=_t("ko", "output_folder"), value=str(DEFAULT_OUTPUT), scale=3)
                camera_kind = gr.Dropdown(
                    _camera_choices("ko"),
                    value="perspective",
                    label=_t("ko", "camera_kind"),
                    scale=1,
                )

        with gr.Row():
            with gr.Column(scale=3):
                input_heading = gr.Markdown(_t("ko", "input"), elem_id="section-input")
                images = gr.File(
                    label=_t("ko", "images"),
                    file_types=["image"],
                    file_count="multiple",
                    type="filepath",
                    height=305,
                )

            with gr.Column(scale=2):
                with gr.Column():
                    options_heading = gr.Markdown(_t("ko", "options"), elem_id="section-options")
                    force_square_pixels = gr.Checkbox(
                        label=_t("ko", "force_square"),
                        value=True,
                        info=_t("ko", "force_square_info"),
                    )
                    include_background = gr.Checkbox(label=_t("ko", "background"), value=True)
                    include_metric_reference = gr.Checkbox(label=_t("ko", "metric_reference"), value=True)
                    save_ply = gr.Checkbox(label=_t("ko", "save_ply"), value=True)
                    save_camera_fbx = gr.Checkbox(label=_t("ko", "save_camera_fbx"), value=True)
        generate = gr.Button(_t("ko", "generate"), variant="primary", size="lg", elem_id="generate-button")
        with gr.Column():
            result_heading = gr.Markdown(_t("ko", "result"), elem_id="section-result")
            result_files = gr.File(label=_t("ko", "result_files"), file_count="multiple")
            status = gr.Markdown()
        viewer_heading = gr.Markdown(_t("ko", "viewer_title"))
        viewer_ply = gr.Dropdown(label=_t("ko", "viewer_ply"), choices=[], interactive=True)
        open_viewer = gr.Button(_t("ko", "open_viewer"))
        viewer_html = gr.HTML(f"<div>{_t('ko', 'viewer_empty')}</div>")
        generate.click(
            generate_blend,
            inputs=[images, output_folder, camera_kind, force_square_pixels, include_background, include_metric_reference, save_ply, save_camera_fbx, language],
            outputs=[result_files, status, viewer_ply],
            concurrency_id="gpu_conversion", concurrency_limit=1,
        )
        open_viewer.click(open_ply_viewer, inputs=[viewer_ply, language], outputs=viewer_html)
        language.change(
            _language_updates,
            inputs=language,
            outputs=[
                header,
                basic_heading,
                output_folder,
                camera_kind,
                input_heading,
                images,
                options_heading,
                force_square_pixels,
                include_background,
                include_metric_reference,
                save_ply,
                save_camera_fbx,
                generate,
                result_heading,
                result_files,
                viewer_heading,
                viewer_ply,
                open_viewer,
                viewer_html,
            ],
        )
    with gr.Tab("MoGe-3 · Depth Mesh"):
        build_moge_tab(DEFAULT_OUTPUT)



def launch_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the UniSHARP Blender web UI.")
    parser.add_argument("--host", default=os.environ.get("UNISHARP_UI_HOST", "127.0.0.1"), help="Bind host; use 0.0.0.0 only with an authenticated network path.")
    parser.add_argument("--port", type=int, default=int(os.environ.get("UNISHARP_UI_PORT", "7860")), help="Bind port.")
    parser.add_argument("--share", action="store_true", help="Create a temporary Gradio public URL. A PIN is strongly recommended.")
    parser.add_argument("--require-pin", action="store_true", help="Require the browser to authenticate with a PIN.")
    parser.add_argument("--pin", default=os.environ.get("UNISHARP_UI_PIN"), help="PIN to require. Prefer UNISHARP_UI_PIN over putting a secret in shell history.")
    parser.add_argument("--pin-only", action="store_true", help="Validate only the password/PIN field; the browser username field may be left blank.")
    parser.add_argument("--username", default=os.environ.get("UNISHARP_UI_USERNAME", "unisharp"), help="Browser login username when PIN protection is enabled.")
    return parser.parse_args()


def launch_browser_ui() -> None:
    args = launch_arguments()
    pin = args.pin
    auth: object | None = None
    if args.require_pin or args.pin_only or pin:
        if not pin:
            pin = f"{secrets.randbelow(1_000_000):06d}"
            print("\n[UniSHARP] Browser PIN generated for this run.")
        if args.pin_only:
            def authenticate_pin(_: str, password: str) -> bool:
                return secrets.compare_digest(password or "", pin or "")

            print(f"[UniSHARP] Browser PIN: {pin}  |  Leave the username field blank and enter this PIN as the password.")
            auth = authenticate_pin
        else:
            print(f"[UniSHARP] Browser login  |  username: {args.username}  |  PIN: {pin}")
            auth = (args.username, pin)
    if args.share and auth is None:
        print("[UniSHARP] Warning: --share makes a temporary public URL without a PIN. Use --require-pin for protected access.")
    demo.launch(
        server_name=args.host,
        server_port=args.port,
        inbrowser=not args.share and args.host in {"127.0.0.1", "localhost"},
        share=args.share,
        auth=auth,
        auth_message="UniSHARP browser access is protected. Enter the PIN printed in the server terminal. When username-free PIN mode is used, leave Username blank.",
        footer_links=[],
        css=CUSTOM_CSS,
    )


if __name__ == "__main__":
    launch_browser_ui()
