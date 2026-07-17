"""VL(고품질 AI OCR) 지원 — 런타임 감지 + 모델 설치 확인 + 다운로드.

Qt 비의존(코어 계층). 실제 추론은 ocr_subprocess의 _VLEngine이 한다
(transformers "Spotting:" 태스크 — 줄 단위 텍스트+좌표).

백엔드 현실(2026-07 확인): PaddleOCR-VL은 **onnxruntime로 못 돌린다.**
공식 배포는 Hugging Face의 transformers(=PyTorch) 경로뿐이고, ONNX 변환은
아직 미지원(optimum 오픈 이슈, 그마저 transformers.js용). 따라서 VL을 쓰려면
가벼운 onnxruntime가 아니라 **torch + transformers 스택**(수 GB, GPU 권장)이
필요하다. 이건 설치 파일(exe)에 번들하지 않고, VL을 켤 때 별도로 받는다.
transformers는 5.0 이상이어야 한다(모델 카드 요구 — VL 아키텍처 지원).

- 모델: Hugging Face repo(_HF_REPO)를 사용자 폴더로 snapshot 다운로드.
- 런타임: torch.cuda 유무로 CUDA/CPU 판별(DirectML은 torch-directml 별도).
"""

import importlib.util
import os

from . import paths

# PaddleOCR-VL 0.9B — Apache 2.0, Hugging Face 공개. transformers로 로드.
_HF_REPO = "PaddlePaddle/PaddleOCR-VL-1.5"

# 스냅샷이 받아졌는지 판단할 대표 파일(HF repo 루트에 항상 있는 것).
_MODEL_MARKER = "config.json"

# VL 추론에 필요한 파이썬 패키지(무겁다 — 설치본에 없음, 사용자가 별도 설치).
# torchvision: transformers의 이미지 프로세서가 요구한다(없으면 로드 실패).
_RUNTIME_PKGS = ("torch", "torchvision", "transformers")


def models_dir():
    """VL 모델 저장 위치 — 사용자 폴더(설치본에 번들 안 함, 수 GB이므로)."""
    d = os.path.join(paths.user_data_dir(), "vl_models")
    os.makedirs(d, exist_ok=True)
    return d


# --- 설치 상태 ----------------------------------------------------------

def _have(pkg):
    try:
        return importlib.util.find_spec(pkg) is not None
    except (ImportError, ValueError):
        return False


def runtime_present():
    """torch + transformers가 깔려 있나(VL 추론 가능 여부의 절반)."""
    return all(_have(p) for p in _RUNTIME_PKGS)


def model_present():
    """모델 스냅샷이 사용자 폴더에 받아져 있나."""
    return os.path.exists(os.path.join(models_dir(), _MODEL_MARKER))


def vl_installed():
    """VL을 실제로 쓸 수 있나 — 런타임 + 모델 둘 다 있어야 True."""
    return runtime_present() and model_present()


def install_hint():
    """UI 안내용 — 지금 뭐가 빠졌는지 사람이 읽을 문구."""
    missing = []
    if not runtime_present():
        missing.append("실행 런타임(torch, torchvision, transformers)")
    if not model_present():
        missing.append("모델(약 2GB, 첫 실행 시 다운로드)")
    return " · ".join(missing) if missing else "설치됨"


# --- 런타임(가속기) 감지 ----------------------------------------------

def detect_runtime():
    """VL이 쓸 가속기를 판별. 반환: (kind, 사람이 읽을 설명).

    kind: "cuda" | "directml" | "cpu" | "none"(torch 자체가 없음).
    torch를 lazy import 한다 — 설정 다이얼로그에서만 불리므로 부담이 적고,
    torch가 없으면 즉시 "none"으로 답한다.
    """
    if not _have("torch"):
        return "none", "PyTorch 미설치 — VL 실행 불가 (torch/transformers 필요)"
    try:
        import torch
        if torch.cuda.is_available():
            try:
                name = torch.cuda.get_device_name(0)
            except Exception:
                name = "CUDA"
            return "cuda", "NVIDIA GPU (CUDA) — %s" % name
    except Exception:
        pass
    if _have("torch_directml"):
        return "directml", "GPU (DirectML)"
    return "cpu", "CPU — VL은 CPU에서 매우 느림 (GPU 권장)"


def runtime_summary():
    """UI 표시용. detect_runtime을 그대로 쓴다(별도 프로세스 불필요 —
    torch는 onnxruntime 같은 Qt DLL 충돌이 없다)."""
    return detect_runtime()


# --- 사양 조사 + 적합성 판단 --------------------------------------------
# VL을 켜기 '전에' 하드웨어를 본다 — torch가 아직 없어도 동작해야 하므로
# nvidia-smi(드라이버가 있으면 존재) + RAM으로 조사한다.

def survey_specs():
    """설치 전 하드웨어 조사. 반환 dict: gpu/vram_gb/ram_gb/cpu_cores."""
    import shutil
    import subprocess

    specs = {"gpu": None, "vram_gb": None,
             "ram_gb": None, "cpu_cores": os.cpu_count()}

    # 총 RAM (Windows: GlobalMemoryStatusEx, 실패 시 psutil)
    try:
        import ctypes

        class _MEM(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = _MEM()
        m.dwLength = ctypes.sizeof(_MEM)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        specs["ram_gb"] = round(m.ullTotalPhys / 1e9, 1)
    except Exception:
        try:
            import psutil
            specs["ram_gb"] = round(psutil.virtual_memory().total / 1e9, 1)
        except Exception:
            pass

    # NVIDIA GPU + VRAM (nvidia-smi가 있으면 드라이버가 설치된 것)
    smi = shutil.which("nvidia-smi")
    if smi:
        try:
            out = subprocess.check_output(
                [smi, "--query-gpu=name,memory.total",
                 "--format=csv,noheader,nounits"],
                text=True, timeout=8, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            first = out.strip().splitlines()[0]
            name, mem_mib = [x.strip() for x in first.split(",")]
            specs["gpu"] = name
            specs["vram_gb"] = round(float(mem_mib) / 1024, 1)
        except Exception:
            pass
    return specs


def vl_suitability():
    """이 PC가 VL을 돌릴 만한가 판단. 반환: (level, specs, 설명).

    level: "good"(권장) | "marginal"(가능하나 부담) | "poor"(비권장).
    기준: VL은 실질적으로 NVIDIA CUDA가 있어야 쓸 만하다. NVIDIA GPU가
    없으면(내장/AMD, CPU) 매우 느려 비권장.
    """
    s = survey_specs()
    ram = s["ram_gb"] or 0
    vram = s["vram_gb"] or 0
    if s["gpu"] and vram >= 6 and ram >= 16:
        return "good", s, (
            "NVIDIA GPU(%s, %.0fGB) + RAM %.0fGB — VL에 적합합니다."
            % (s["gpu"], vram, ram))
    if s["gpu"] and vram >= 4:
        return "marginal", s, (
            "GPU(%s, %.0fGB)가 있으나 여유가 크지 않습니다 — 동작은 하지만 "
            "느리거나 메모리 부족이 날 수 있습니다." % (s["gpu"], vram))
    where = "NVIDIA GPU 없음(내장/AMD 또는 CPU)" if not s["gpu"] \
        else "GPU %s" % s["gpu"]
    return "poor", s, (
        "%s, RAM %.0fGB — GPU 가속을 못 써 VL이 매우 느립니다(페이지당 "
        "수십 초~분). 켜놓고 기다리는 배경 작업이면 쓸 수 있지만, 평소엔 "
        "기본(RapidOCR)을 권합니다." % (where, ram))


# --- 다운로드 -----------------------------------------------------------

def can_download():
    """모델을 받을 수 있나 — huggingface_hub가 있어야 한다.

    (transformers를 깔면 대개 함께 들어온다. 없으면 런타임부터 설치 필요.)
    """
    return _have("huggingface_hub")


def download_models(progress=None):
    """VL 모델 스냅샷을 사용자 폴더로 내려받는다(Hugging Face).

    huggingface_hub가 없으면 명확한 안내와 함께 거부한다 — VL 런타임을
    먼저 설치해야 한다는 신호.
    progress: 현재 huggingface_hub 진행 콜백을 그대로 노출하기 어려워
    자리만 둔다(TODO: 파일 단위 진행 표시).
    """
    if not can_download():
        raise RuntimeError(
            "VL 런타임이 설치되어 있지 않습니다.\n"
            "먼저 다음을 설치하세요:\n"
            "  pip install torch torchvision transformers huggingface_hub\n"
            "(GPU 사용 시 CUDA 지원 torch 빌드 필요)")
    from huggingface_hub import snapshot_download
    snapshot_download(repo_id=_HF_REPO, local_dir=models_dir())
