# Windows 렌더링 백엔드 설계

작성일: 2026-09-01 · 구현 현황 갱신: 2026-09-02

상태: Direct2D 타일 합성 및 제한형 PDF 벡터·글자 GPU 래스터화 적용

구현 현황: sPDF 1.23.0에서 ABI v4 DLL을 독립 실행 리더·편집기의 실제 Qt HWND에 연결했다. Intel Iris Xe의 하드웨어 D3D feature level 11.1에서 D3D11/DXGI 장치, Direct2D device context, DirectWrite factory와 flip-model swap chain을 검증했다. PyMuPDF의 512px BGRA 타일, 페이지 회전 행렬, 검색·선택·편집 테두리를 Direct2D로 합성한다. 지원되는 페이지는 MuPDF가 CPU에서 해석한 선·사각형·베지어와 원래 글꼴 glyph 윤곽을 immutable Direct2D geometry 및 realization으로 만들어 상세 CPU 타일 없이 GPU 래스터화한다. CPU에서 디코딩한 배치 이미지는 원래 PDF 행렬로 Direct2D가 확대·합성한다. 숨김·닫기 때 네이티브 캐시를 해제하며 실패하면 같은 문서와 좌표를 유지한 채 Qt 표시로 전환한다.

## 결정

sPDF 독립 실행 리더와 편집기의 Windows 우선 화면 백엔드는 다음 조합을 목표로 한다.

- Direct3D 11 장치와 DXGI flip-model swap chain으로 창 표면과 프레임 표시를 관리한다.
- Direct2D device context로 페이지 이미지, 편집 개체, 선택 표시와 안내선을 합성한다.
- DirectWrite로 sPDF가 새로 만드는 조판 텍스트의 측정·glyph 배치·화면 표시를 처리한다.
- 리더와 편집기는 같은 백엔드 코드를 사용하되 장치·swap chain·캐시·문서 상태를 각 OS 프로세스가 독립 소유한다.
- 장치 생성 실패, 원격 데스크톱, 드라이버 reset에는 CPU 표시 경로로 전환한다. 편집 좌표와 저장 결과는 백엔드와 무관해야 한다.

Direct2D는 PDF 파일을 해석하는 엔진이 아니다. PyMuPDF가 CPU에서 PDF 명령을 해석하고 원래 glyph 윤곽과 이미지를 제공하며, Direct2D는 지원되는 장면을 래스터화·합성한다. 기존 PDF 글자를 DirectWrite로 다시 조판하지 않는다. 클리핑·그라데이션·마스크·투명도 그룹·복잡한 선 모양이 있거나 이미지 장면 데이터가 64 MiB를 넘으면 페이지 전체를 기존 CPU 타일 경로로 표시한다.

Microsoft 문서의 [Direct2D device context 구성](https://learn.microsoft.com/en-us/windows/win32/direct2d/devices-and-device-contexts), [Direct2D·Direct3D 상호 운용](https://learn.microsoft.com/en-us/windows/win32/direct2d/direct2d-and-direct3d-interoperation-overview), [DXGI 개요](https://learn.microsoft.com/en-us/windows/win32/direct3ddxgi/d3d10-graphics-programming-guide-dxgi)를 기준으로 구현한다.

## 구현 경계

Python/PyQt5의 현재 배포본에는 Direct2D QPA 플러그인이 없다. 네이티브 Windows 렌더러를 별도 모듈로 만들고 PyQt 창의 HWND에 붙이는 방식을 사용한다. Python은 문서·편집 명령·접근성 UI를 소유하고, 네이티브 모듈은 다음의 제한된 명령만 받는다.

- 창 연결·크기/DPI 변경, 장치 생성·해제, 프레임 시작·표시.
- 페이지 타일 추가·갱신·폐기와 행렬·clip·불투명도 지정.
- 조판 개체의 도형·이미지·텍스트 표시와 선택/안내선 overlay.
- 장치 손실·메모리 부족·대체 경로 전환 알림과 진단 수치.

PDF 저장, 실행 취소, OCR, 페이지 구성과 파일 잠금은 네이티브 렌더러에 넣지 않는다. 렌더러 충돌은 해당 작업 프로세스에만 국한하며, 다른 파일을 연 별도 프로세스에 전파하지 않는다. 같은 파일의 리더는 정상 인계 뒤 이미 종료될 수 있으므로 디스크의 정상본과 독립 복구 사본으로 다시 열 수 있어야 한다.

## 단계

1. 현재 타일·페이지 좌표·캐시 정책과 화면 표면 생성 코드를 분리한다. CPU와 기존 OpenGL 경로로 회귀 검사를 유지한다.
2. 작은 네이티브 시제품에서 HWND, D3D11 BGRA 장치, DXGI flip-model swap chain, Direct2D device context와 DirectWrite factory를 생성한다. 장치 생성·빈 프레임·bitmap 합성·resize·해제를 완료했다.
3. 현재 512px 타일을 복사해 리더·편집기의 확대·이동과 overlay를 표시한다. 탭당 RAM 캐시 상한, GPU bitmap 연동 폐기, 숨김·닫기 후 자원 회수를 적용했다. 다중 모니터 DPI 전환과 실제 장치 손실 복구 시험은 계속한다.
4. 단순 벡터·fill text·배치 이미지는 MuPDF 표시 장면에서 추출해 Direct2D로 표시한다. 반복 glyph geometry realization과 64 MiB 이미지 장면 상한을 적용했다.
5. 클리핑·그라데이션·마스크·투명도 그룹을 지원 범위에 넣기 전 CPU 대체 경로와 800% 확대 품질을 비교한다. PDFium/Skia GPU canvas는 별도 비교 시제품 후보로 유지한다.
6. 편집 개체의 이동·크기 조절·회전은 변경 영역만 다시 표시한다. CPU PDF 해석 지연과 GPU 래스터·합성 지연을 따로 기록한다.

## 완료 기준

- 같은 문서·장비에서 입력 후 첫 화면, 연속 이동/변형, 선명한 화면 완성 시간을 기존 경로와 비교한다.
- 100%, 폭 맞춤, 800% 확대에서 글자·선·clip·투명도와 선택 좌표가 맞는다.
- 다중 모니터 DPI 변경, 창 resize, 절전 복귀, 원격 데스크톱과 장치 reset 뒤 복구한다.
- 숨긴 탭·닫은 창의 대기 작업과 장치 자원이 남지 않고 종료를 지연하지 않는다.
- GPU를 끄거나 사용할 수 없어도 읽기·편집·실행 취소·저장 결과가 동일하다.

## PDF 내부 sPDF 편집 데이터

PDF 1.3 이후의 page-piece dictionary와 PDF 1.4 이후 문서 catalog의 `PieceInfo`에는 응용 프로그램 전용 데이터를 넣을 수 있다. sPDF는 `/PieceInfo << /sPDF ... >>` 아래 application data dictionary의 `/Private` stream에 형식 버전이 있는 JSON 또는 CBOR 데이터를 저장하는 방식을 시제품으로 검증한다. `/LastModified`를 함께 기록하고, 모르는 다른 응용 프로그램 항목은 보존한다.

여기에는 안정적인 개체 ID, 그룹·스타일·프레임 연결, 안내선, 원본 문자열과 출력 설정처럼 비교적 작은 편집 정보를 넣을 수 있다. 일반 PDF 뷰어는 이를 무시하므로 PDF 열람에는 필요하지 않아야 한다. [Adobe PDF Reference의 Page-Piece Dictionaries](https://opensource.adobe.com/dc-acrobat-sdk-docs/pdfstandards/pdfreference1.5_v6.pdf)와 [PDF Association의 custom metadata 지침](https://pdfa.org/download-area/publications/Including-custom-metadata-structures-in-PDF.pdf)을 따른다.

`PieceInfo`는 최적화·정리·다른 프로그램의 재저장에서 제거되거나 현재 PDF 내용과 불일치할 수 있다. 따라서 첫 조판 버전의 완전한 재편집 원본은 `*.spdf-layout` 컨테이너로 유지하고, PDF 내부 데이터는 이동이 편한 보조 사본으로 취급한다. 큰 원본 이미지·글꼴·복구 이력은 PDF private stream에 무조건 넣지 않는다. 데이터 크기·압축 해제 상한, 스키마 검증, checksum, 암호 PDF와 전자서명 변경 경고를 적용한다.
