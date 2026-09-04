# 변경 이력

[English](CHANGELOG.md) | 한국어

## 1.29.1 - 2026-09-04

### 개선

- PDF soft-mask transfer function을 GPU 알파 테이블로 적용해 페이지 전체 CPU 대체 없이 Direct2D 경로에 남깁니다.
- 단순 색상 벡터 타일 패턴을 Direct2D 장면 항목으로 펼쳐 페이지 전체 CPU 대체 없이 표시합니다.
- 근사 CPU island가 작은 겹침 도형을 같은 제한 영역 래스터 island에 흡수해, GPU 강제 렌더링을 유지하면서 중복 벡터 경계선을 줄입니다.
- 같은 색으로 연속 배치된 글자 glyph outline을 페이지 좌표의 결합 path로 압축해, PDF 모델 좌표는 유지하면서 GPU 장면 항목과 네이티브 path 리소스를 줄입니다.
- linear/radial gradient primitive를 감싼 중복 clip wrapper가 같은 영역이면 gradient 항목으로 합쳐, 복잡한 페이지의 장면 명령을 줄입니다.
- 선택형 실험 설정으로 유사 색상 band 병합을 기본 정확 색상 경로와 분리해 비교할 수 있습니다.
- 확대·축소 중에는 현재 GPU 장면을 즉시 재사용하고, 입력이 안정된 뒤 이미지 품질 장면을 갱신합니다.
