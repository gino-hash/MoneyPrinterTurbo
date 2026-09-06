# Ecozin 기획 워크벤치 (MoneyPrinterTurbo 포크)

전기절감기 제조업체용 **업종 맞춤형 쇼츠 기획·검수 시스템**입니다. MoneyPrinterTurbo(MPT)의 렌더링(음성·자막·합성)은 그대로 쓰고,
그 앞단에 "무엇을 만들지" 정하는 기획 두뇌를 붙였습니다. 원본(MPT) 파일은 수정하지 않았습니다.

- 회사 모듈: `app/ecozin/`
- 화면: `webui/pages/1_기획_워크벤치.py` (MPT 웹UI 왼쪽 사이드바에 자동 등록)
- 문서: `docs/ecozin/PRD.md`, `docs/ecozin/handoff/`
- 테스트: `test/ecozin/`

## 흐름

```
원본 자료(텍스트·사진 메모·사진 업로드)
  → 업종 템플릿(최종고객 / 파트너 모집 분기)
  → 초안 3세트 (문제제기형 · 전후비교형 · 실수방지형)
  → 품질 검사 (과장어 완화·경고, 절감률+보장 표현 차단, 금지어, 필수어, CTA 정합성, 원본 기반성)
  → 사람 검수: 승인 / 수정중 / 보류  (문구 직접 수정 가능, 원본 보존)
  → [승인] 프리뷰 생성 → 확인 후 장면 확정 → 최종 생성   (모두 MPT 파이프라인, 로컬 사진 + 무료 한국어 음성)
  → 업로드는 사람이 직접
```

## 실행 (회사 PC, Windows)

```bat
git clone https://github.com/gino-hash/MoneyPrinterTurbo
cd MoneyPrinterTurbo
pip install -r requirements.txt
copy config.example.toml config.toml
webui.bat
```

브라우저에서 `http://127.0.0.1:8501` 을 열고 왼쪽 사이드바에서 **기획 워크벤치** 를 선택합니다.
`config.toml` 은 기본값으로 두어도 됩니다. 워크벤치는 `video_source=local`, 한국어 Edge TTS, 한글 자막 폰트를 작업마다 직접 지정하므로
MPT 기본 화면의 설정에 영향을 받지 않습니다. 자동 업로드(`upload_post_enabled`)는 끈 상태로 두세요.

선택 설정 (`config.toml` 의 `[app]` 아래):

```toml
ecozin_voice_name = "ko-KR-InJoonNeural-Male"   # 기본은 ko-KR-SunHiNeural-Female
```

## 사용 순서

1. **새 프로젝트**: 프로젝트명, 업종, 시청자 유형(최종고객/파트너 모집), 타깃, 목표 CTA, 톤, 원본 텍스트(30자 이상), 이미지 메모, 사진 업로드, 금지어/필수어 → "저장 후 초안 3세트 생성"
2. **결과 패널**: 카드 3개. 훅·대본·장면계획·영상프롬프트·제목·썸네일문구·설명·고정댓글·CTA. 각 항목은 펼쳐서 복사. 품질 경고 확인. 승인/수정중/보류.
3. 승인한 카드에서 **프리뷰 생성** → 영상 확인 → **프리뷰 확인 완료 → 장면 확정** → **최종 생성**
4. **이력**: 프로젝트 목록(세대·초안·승인 수), 최근 이벤트 50건

## 데이터 위치

- `storage/ecozin/ecozin.db` — 프로젝트·초안·상태·이벤트 (SQLite)
- `storage/ecozin/assets/<project_id>/` — 업로드한 사진
- `storage/tasks/<task_id>/` — MPT 렌더링 결과 (final-1.mp4 등)

## 업종 추가

`app/ecozin/templates/<industry>.json` 파일을 하나 더 만들면 드롭다운에 자동으로 뜹니다. 구조는 `energy_saving_device.json` 을 복사해서 채우면 되고,
`audiences.end_customer` 와 `audiences.partner` 두 유형이 모두 있어야 로드됩니다.

## 테스트

```bash
python -m pytest test/ecozin -q
```

## 아직 안 넣은 것

- 프리뷰 저해상도 렌더링 (MPT 파이프라인이 해상도 옵션을 노출하지 않아 현재 프리뷰와 최종은 배경음악·전환 효과만 다름)
- AI 생성 장면 실제 호출 (장면 계획에 "AI 생성"으로 표시만 하고, 렌더링은 업로드한 실사만 사용)
- LLM 생성기 (규칙 기반만 있음. 같은 인터페이스로 추가 예정)
- 업종 템플릿 2개 이상
