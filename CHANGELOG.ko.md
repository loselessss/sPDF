# 변경 이력

[English](CHANGELOG.md) | 한국어

## 1.28.0 - 2026-09-02

### 성능 개선

- 격리된 PDF 그룹의 Soft Light, Multiply, Screen, Overlay, Darken, Lighten, Color Dodge, Color Burn, Hard Light, Difference, Exclusion을 Direct2D GPU 효과로 처리합니다.
- 지원되는 혼합 장면은 그룹 불투명도와 기존 배경을 유지하면서 페이지 전체 CPU 렌더링 대신 GPU 표시 경로를 사용합니다.

### 개선

- 렌더링 진단에서 클리핑/마스크 안의 미지원 혼합과 색상 성분 혼합을 구분합니다. 비격리·knockout 그룹과 미지원 조합은 CPU 대체 경로를 유지합니다.
