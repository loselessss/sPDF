"""OCR 자식 프로세스 — Qt 없이 onnxruntime만 로드해 실행한다.

왜 별도 프로세스인가: PyQt5가 먼저 로드된 프로세스에서 onnxruntime를
import하면 DLL 초기화가 실패한다(Windows, "DLL 초기화 루틴을 실행할 수
없습니다"). 스레드로는 못 피한다 — 같은 프로세스이기 때문. 그래서 OCR은
이 스크립트를 자식 프로세스로 띄워 처리하고, 부모(Qt 앱)는 stdout으로
결과 JSON만 받는다.

프로토콜(부모가 파싱):
    stdin(JSON 한 줄): {"path","password","pages":[...],"zoom"}
    stdout(줄 단위 JSON):
        {"type":"progress","done":k,"total":n}
        {"type":"page","page":p,"items":[[x0,y0,x1,y1,text],...]}
        {"type":"error","message":...}
        {"type":"done"}

사용법:
    python -m pdfeditor.ocr_subprocess    # stdin으로 작업 전달
"""

import json
import sys


def _force_utf8_io():
    """stdin/stdout을 UTF-8로 고정한다.

    PYTHONIOENCODING 환경변수로는 부족하다 — PyInstaller로 얼린 EXE에서는
    무시되고 콘솔 기본 인코딩(한국어 Windows면 cp949)으로 출력해서, 부모가
    UTF-8로 읽다 UnicodeDecodeError로 죽는다(한글 OCR 결과가 통째로 유실).
    파일 경로에 한글이 있으면 stdin도 같은 이유로 깨진다.
    """
    for stream in (sys.stdin, sys.stdout):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass  # 파이프가 아닌 경우 등 — 무시


# 렌더 목표: 긴 변 기준 픽셀 수. A4(842pt)면 약 6배율(430dpi 상당)이 된다.
# 고정 3배율로는 저해상도 스캔(예: 115dpi 영수증)의 작은 글씨가 깨졌다 —
# 실측으로 이 값에서 인식이 눈에 띄게 좋아지고 처리 시간은 거의 같았다.
# 상한을 두는 이유: 스캐너가 만드는 '페이지=픽셀' PDF(수천 pt)는 배율을
# 낮춰야 렌더 버퍼가 수백 MB로 터지지 않는다. 페이지당 순간 사용량은
# 긴 변 5000px 기준 약 50MB이고, 자식 프로세스가 페이지마다 해제한다.
# 5100인 이유: A4(842pt)가 상한 6.0배에 정확히 걸리게 — 5.9배 근처에서
# '일시불' 같은 작은 글씨가 왔다갔다 하는 걸 실측으로 확인했다.
TARGET_LONG_PX = 5100.0
ZOOM_MIN, ZOOM_MAX = 1.0, 6.0


def _page_zoom(rect):
    long_pt = max(rect.width, rect.height)
    if long_pt <= 0:
        return 3.0
    return max(ZOOM_MIN, min(ZOOM_MAX, TARGET_LONG_PX / long_pt))


def _emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _build_engine(engine="rapidocr"):
    """OCR 엔진 생성. engine="vl"이면 PaddleOCR-VL(고품질 AI) 시도.

    VL은 모델이 사용자 폴더에 설치돼 있어야 한다(vl.py). 미설치거나 아직
    구현 전이면 명확한 예외를 던져 호출부가 사용자에게 안내하게 한다 —
    조용히 RapidOCR로 떨어지지 않는다(품질 기대가 다르므로).
    """
    if engine == "vl":
        return _build_vl_engine()
    return _build_rapidocr_engine()


def _build_vl_engine():
    # 뼈대 단계: 모델 설치 여부만 확인하고, 실추론 연결 전까지는 명확한
    # 미구현 신호를 준다(조용히 다른 엔진으로 떨어지지 않음).
    from pdfeditor import vl
    if not vl.vl_installed():
        raise RuntimeError(
            "VL 모델이 설치되어 있지 않습니다. 설정에서 'AI 고품질 OCR'을 "
            "켜고 모델을 먼저 내려받으세요.")
    # TODO: onnxruntime로 PaddleOCR-VL 세션을 만들고 페이지를 처리한다.
    # runtime = vl.detect_runtime()로 CUDA/DirectML/CPU 제공자를 고른다.
    raise RuntimeError("VL 추론은 아직 연결되지 않았습니다.")


def _build_rapidocr_engine():
    import os

    from rapidocr import RapidOCR
    # 프로즌 EXE는 모델을 사용자 폴더에 받아야 재실행 간 유지된다
    # (부모가 RAPIDOCR_MODEL_DIR로 넘겨준다). RapidOCR은 전역 설정에서
    # 모델 저장 위치를 읽으므로, 지정돼 있으면 그리로 돌린다.
    model_dir = os.environ.get("RAPIDOCR_MODEL_DIR")
    extra = {}
    if model_dir:
        os.makedirs(model_dir, exist_ok=True)
        extra["Global.model_root_dir"] = model_dir
    try:
        from rapidocr.utils.typings import LangRec, ModelType, OCRVersion
        params = {
            "Rec.ocr_version": OCRVersion.PPOCRV5,
            "Rec.lang_type": LangRec.KOREAN,
            "Rec.model_type": ModelType.MOBILE,
        }
        params.update(extra)
        return RapidOCR(params=params)
    except Exception:
        try:
            return RapidOCR(params=extra) if extra else RapidOCR()
        except Exception:
            return RapidOCR()


def _preprocess(img_rgb):
    """OCR 전처리 — 기울기 보정(deskew) + 언샤프 마스크(sharpen).

    실측(영수증 6배 렌더): 샤픈이 인식률을 21개 토큰 중 20→21로 올렸고,
    deskew는 똑바른 문서엔 무해(0도면 원본 그대로), 기울어진 스캔에서 효과.
    cv2가 없으면 원본을 그대로 돌려준다(설치 선택 사항).
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return img_rgb

    img = img_rgb
    # --- deskew: 전경 픽셀의 최소 외접 사각형 각도로 회전 ---
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    thr = cv2.threshold(gray, 0, 255,
                        cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thr > 0))
    if len(coords) >= 100:
        ang = cv2.minAreaRect(coords)[-1]
        if ang < -45:
            ang = 90 + ang
        elif ang > 45:
            ang = ang - 90
        # 아주 작은 각도는 보정 자체가 노이즈 — 0.3도 이상만, 5도 넘는 큰
        # 각도는 오탐(표/그림 때문)일 수 있어 건드리지 않는다.
        if 0.3 <= abs(ang) <= 5.0:
            h, w = img.shape[:2]
            M = cv2.getRotationMatrix2D((w // 2, h // 2), ang, 1.0)
            img = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC,
                                 borderMode=cv2.BORDER_REPLICATE)

    # --- sharpen: 언샤프 마스크 ---
    blur = cv2.GaussianBlur(img, (0, 0), 3)
    img = cv2.addWeighted(img, 1.5, blur, -0.5, 0)
    return img


def _recognize(ocr, img_rgb, zoom):
    result = ocr(img_rgb)
    out = []
    if result is None:
        return out
    if hasattr(result, "boxes") and result.boxes is not None:
        pairs = zip(result.boxes, result.txts or [])
    else:
        res = result[0] if isinstance(result, tuple) else result
        if not res:
            return out
        pairs = ((item[0], item[1]) for item in res)
    for box, text in pairs:
        xs = [float(p[0]) for p in box]
        ys = [float(p[1]) for p in box]
        out.append([min(xs) / zoom, min(ys) / zoom,
                    max(xs) / zoom, max(ys) / zoom, str(text)])
    return out


def main():
    _force_utf8_io()  # 반드시 첫 입출력 전에 (프로즌 EXE의 cp949 폴백 방지)

    # 런타임 감지 모드 — stdin 작업 없이 가속기 종류만 보고하고 끝낸다.
    # 부모(Qt)는 onnxruntime를 못 import하므로 이 자식에게 물어본다(vl.py).
    if "--detect-runtime" in sys.argv:
        from pdfeditor import vl
        kind, desc = vl.detect_runtime()
        _emit({"type": "runtime", "kind": kind, "desc": desc})
        return 0

    try:
        job = json.loads(sys.stdin.readline())
    except Exception as e:
        _emit({"type": "error", "message": "잘못된 작업 입력: %s" % e})
        return 1

    path = job["path"]
    password = job.get("password")
    pages = job["pages"]
    fixed_zoom = job.get("zoom")  # 없으면 페이지별 자동 배율
    engine = job.get("engine", "rapidocr")

    try:
        import numpy as np
        import fitz
        ocr = _build_engine(engine)
    except Exception as e:
        _emit({"type": "error", "message": "OCR 초기화 실패: %s" % e})
        return 1

    try:
        doc = fitz.open(path)
        if doc.needs_pass:
            doc.authenticate(password or "")
        try:
            for i, pno in enumerate(pages):
                zoom = fixed_zoom or _page_zoom(doc[pno].rect)
                pix = doc[pno].get_pixmap(
                    matrix=fitz.Matrix(zoom, zoom), alpha=False)
                img = np.frombuffer(pix.samples, dtype=np.uint8) \
                    .reshape(pix.height, pix.width, 3)
                if job.get("preprocess", True):
                    img = _preprocess(img)
                items = _recognize(ocr, img, zoom)
                del pix, img
                _emit({"type": "page", "page": pno, "items": items})
                _emit({"type": "progress", "done": i + 1, "total": len(pages)})
        finally:
            doc.close()
        _emit({"type": "done"})
        return 0
    except Exception as e:
        _emit({"type": "error", "message": str(e)})
        return 1


if __name__ == "__main__":
    sys.exit(main())
