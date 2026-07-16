"""VL(고품질 AI OCR) 지원 — 런타임 감지 + 모델 경로/설치 확인 + 다운로드.

Qt 비의존(코어 계층). 실제 추론은 ocr_subprocess의 VL 어댑터가 한다.

상태: **뼈대 단계.** 실제 VL 추론 연결은 GPU 환경에서 마무리한다.
- GPU 런타임 감지(detect_runtime)는 동작·검증됨.
- 모델 다운로드(download_models)는 소스 URL이 비어 있어(_MODEL_SOURCES)
  아직 실행되지 않는다 — PaddleOCR-VL ONNX 배포 URL을 채운 뒤 활성화한다.
  그전까지 vl_installed()는 항상 False라 UI에서 "미설치"로 안전하게 표시된다.

VL은 수 GB 다운로드 + GPU 추론이라 GPU 없는 환경에선 검증이 어렵다.
검증 가능한 부분(경로/감지/UI 연결)을 먼저 확정하고, 실추론 연결과 모델
소스는 GPU 환경에서 마무리한다.
"""

import os

from . import paths


# --- 모델 파일 정의 ----------------------------------------------------
# PaddleOCR-VL(약 0.9B)을 ONNX로 돌린다는 가정. 파일명/개수는 실제 배포본을
# 받아 확정한다. 지금은 자리표시자 — _MODEL_SOURCES가 비어 있어 다운로드가
# 시작되지 않는다.
_MODEL_FILES = (
    "paddleocr_vl_visual.onnx",
    "paddleocr_vl_decoder.onnx",
    "paddleocr_vl_tokenizer.json",
)

# TODO: 각 파일의 실제 다운로드 URL을 채운다. (파일명 -> URL)
# 채우기 전까지 vl_installed()=False, download_models()는 거부한다.
_MODEL_SOURCES = {}


def models_dir():
    """VL 모델 저장 위치 — 사용자 폴더(설치본에 번들 안 함, 수 GB이므로)."""
    d = os.path.join(paths.user_data_dir(), "vl_models")
    os.makedirs(d, exist_ok=True)
    return d


def vl_installed():
    """VL 모델이 전부 내려받아져 있나."""
    d = models_dir()
    return all(os.path.exists(os.path.join(d, f)) for f in _MODEL_FILES)


def missing_models():
    d = models_dir()
    return [f for f in _MODEL_FILES if not os.path.exists(os.path.join(d, f))]


# --- 런타임(가속기) 감지 ----------------------------------------------

def detect_runtime():
    """사용 가능한 최적 onnxruntime 실행 제공자를 고른다.

    반환: ("cuda"|"directml"|"cpu", 사람이 읽을 설명).
    - NVIDIA(CUDA) > DirectML(AMD/인텔/NVIDIA 공용, Windows) > CPU 순.
    onnxruntime를 import하므로(Qt와 충돌) **자식 프로세스에서만 호출**할 것.
    """
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
    except Exception:
        return "cpu", "onnxruntime 없음 — CPU"
    if "CUDAExecutionProvider" in providers:
        return "cuda", "NVIDIA GPU (CUDA)"
    if "DmlExecutionProvider" in providers:
        return "directml", "GPU (DirectML)"
    return "cpu", "CPU"


def runtime_summary():
    """UI 표시용 — Qt 프로세스에서 자식으로 물어본다(직접 import 회피).

    부모(Qt) 프로세스는 onnxruntime를 절대 import하면 안 되므로
    (paths/ocr 참고), 감지도 자식 프로세스에 맡긴다. 실패하면 보수적으로
    CPU로 답한다.
    """
    import json
    import subprocess
    from .paths import ocr_command  # 워커 실행 명령 재사용
    try:
        cmd = ocr_command() + ["--detect-runtime"]
        out = subprocess.check_output(
            cmd, text=True, encoding="utf-8", timeout=30,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for line in out.splitlines():
            try:
                m = json.loads(line)
            except ValueError:
                continue
            if m.get("type") == "runtime":
                return m["kind"], m["desc"]
    except Exception:
        pass
    return "cpu", "감지 실패 — CPU 가정"


# --- 다운로드 (게이트) --------------------------------------------------

def can_download():
    """다운로드 소스가 준비됐나 — 지금은 False(URL을 채운 뒤 True)."""
    return bool(_MODEL_SOURCES) and all(
        f in _MODEL_SOURCES for f in _MODEL_FILES)


def download_models(progress=None):
    """VL 모델을 사용자 폴더로 내려받는다. progress(done_bytes, total, name).

    소스 URL이 없으면(can_download False) 조용히 거부한다 — 가짜 URL로
    엉뚱한 걸 받는 사고를 막기 위한 게이트.
    """
    if not can_download():
        raise RuntimeError(
            "VL 모델 다운로드 소스가 아직 설정되지 않았습니다.\n"
            "vl.py의 _MODEL_SOURCES에 PaddleOCR-VL ONNX URL을 채운 뒤 "
            "사용하세요.")
    import urllib.request
    d = models_dir()
    for name in missing_models():
        url = _MODEL_SOURCES[name]
        dst = os.path.join(d, name)
        tmp = dst + ".part"
        with urllib.request.urlopen(url) as resp:  # noqa: S310 (신뢰 URL)
            total = int(resp.headers.get("Content-Length", 0))
            done = 0
            with open(tmp, "wb") as f:
                while True:
                    chunk = resp.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total, name)
        os.replace(tmp, dst)
