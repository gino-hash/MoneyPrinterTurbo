"""
Ecozin 기획 워크벤치 — 업종 맞춤형 쇼츠 기획 패키지 모듈.

MoneyPrinterTurbo 렌더링 파이프라인 앞단에 붙는 '두뇌' 계층이다.
- 원본 자료(텍스트·이미지 메모) 입력 → 업종 템플릿 → 초안 3세트 생성
- 과장 표현·금지어·필수어·CTA 정합성·원본 기반성 검사
- 승인/보류 상태와 이력 저장
- 승인된 초안을 MPT VideoParams 로 변환해 렌더링 작업 제출 (bridge)

원본(MoneyPrinterTurbo) 파일은 건드리지 않고 이 패키지와 webui/pages 안에서만 동작한다.
"""

__all__ = ["models", "db", "template_loader", "generators", "bridge"]
