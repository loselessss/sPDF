# 변경 이력

[English](CHANGELOG.md) | 한국어

## 1.28.1 - 2026-09-02

### 성능 개선

- 격리된 PDF 그룹의 색조(Hue)·채도(Saturation)·색상(Color)·명도(Luminosity) 혼합도 기존 배경과 그룹 불투명도를 유지하면서 GPU 표시 경로를 사용합니다.
- 미지원 클리핑/마스크 중첩과 비격리·knockout 그룹은 CPU 대체 경로를 유지합니다.
