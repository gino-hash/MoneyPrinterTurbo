# PRD — 업종 맞춤형 쇼츠 워크벤치 (shorts-workbench) v0.1

- 작성일: 2026-09-04
- 근거 문서: `docs/handoff/` 핸드오프 패키지 5종 (README, 01 통합브리프, 02 실행프롬프트, 03 출력스키마, 04 Codex 보강지점)
- 상태: 구현 착수 전 확정용 초안
- **2026-09-06 방향 전환**: 독립 Node 앱 대신 **MoneyPrinterTurbo(MIT) 포크 안에 Python 모듈로 구현**한다. 렌더링(음성·자막·합성)은 MPT를 쓰고, 이 PRD의 1단계(기획·검수·이력)는 MPT 웹 화면의 추가 탭으로 붙인다. 13장과 18장이 이를 반영한다. 기능 요구사항(1~12장)은 그대로 유효하다.

---

## 1. 한 줄 정의

**권리가 명확한 원본 텍스트/이미지 메모를 넣으면, 업종 문맥에 맞는 쇼츠 콘텐츠 패키지(각도·후킹·대본·장면계획·영상프롬프트·제목·썸네일문구·설명·고정댓글·CTA) 초안 3세트를 만들어 주고, 사람이 검수·승인한 뒤 배포하도록 돕는 내부용 웹 워크벤치.**

## 2. 이 제품이 아닌 것

| 아닌 것 | 이유 |
|---|---|
| 쇼핑쇼츠 부업 복제기 | 남의 영상·구조 복제 금지. 입력은 사용자 소유 원본만 받는다. |
| AI 영상 렌더러 | 영상 생성 자체는 범위 밖. 영상 툴에 넘길 `video_prompt` 텍스트까지만 만든다. |
| 자동 업로드 봇 | 배포는 항상 사람이 한다. SNS API 연동 없음. |
| 범용 만능 생성기 | 업종 1개용 vertical MVP. 구조만 확장 가능하게 둔다. |
| SaaS | 단일 사용자 내부 실험 도구. 로그인·권한 없음. |

## 3. 목표와 비목표

### 목표 (MVP)
1. 프로젝트 1건 입력 → 저장 → 초안 3세트 생성 → 검수 상태 저장 → 이력 재조회가 끊김 없이 동작한다.
2. 초안 3세트가 서로 다른 angle을 갖고, 10개 필수 필드를 빠짐없이 채운다.
3. 출력은 사람이 바로 복사해 쓸 수 있는 텍스트다.
4. 과장 표현·금지어는 자동으로 걸러지거나 경고로 표시된다.
5. 업종 템플릿을 JSON 파일 1개 추가하는 것만으로 새 업종을 붙일 수 있는 구조다.

### 비목표 (이번 버전 제외)
- 자동 영상 렌더링, 자동 업로드, 외부 SNS API, 광고 집행 자동화
- 성과 분석 대시보드
- 멀티유저·권한·인증
- 업종 2개 이상 (구조만 대비)

## 4. 사용자와 핵심 시나리오

**사용자**: 자사 서비스 홍보 쇼츠를 직접 기획·운영하는 1인 마케터/대표. 조회수보다 **문의·상담·제안 전환**을 원한다.

**시청자 유형(audience_mode)은 두 가지이며 프로젝트마다 하나를 고른다.** 같은 원본이라도 유형에 따라 통점·훅·CTA가 달라야 하므로 생성기는 이 값을 첫 번째 분기 조건으로 쓴다.

| 유형 | 키 | 누가 보나 | 무엇을 원하나 | 기본 CTA |
|---|---|---|---|---|
| 최종고객 | `end_customer` | 공장·상가·건물·농장의 전기요금 담당자, 설비 관리자 | 전기요금 절감을 계측 데이터로 확인하고 싶다 | 상담문의, 견적요청, 현장진단신청 |
| 파트너 모집 | `partner` | 전기공사업체, 설비 설치업체, 지역 대리점 후보 | 팔 만한 제품인지, 마진·설치 난이도·A/S 부담이 어떤지 알고 싶다 | 대리점문의, 자료요청 |

**핵심 시나리오 (해피 패스)**
1. 새 프로젝트 화면에서 프로젝트명, 업종, 타깃, 목표 CTA, 톤, 원본 텍스트, 이미지 메모, 금지어/필수어를 입력하고 저장한다.
2. "초안 생성" 버튼을 누르면 업종 템플릿이 로드되고 초안 3세트가 생성돼 카드로 나열된다.
3. 카드마다 hook/script/title/thumbnail_copy/CTA를 읽고, 필드별 복사 버튼으로 옮겨 쓴다.
4. 마음에 드는 초안은 **승인**, 다듬을 것은 **수정중**, 아닌 것은 **보류**로 상태를 바꾼다.
5. 나중에 이력 화면에서 과거 프로젝트와 초안, 상태 변경 기록을 다시 본다.
6. 같은 프로젝트에서 "다시 생성"하면 새 세대(generation)의 초안 3세트가 추가되고, 이전 세대는 이력에 남는다.

## 5. 첫 업종 선택: `energy-saving-device` (전기절감기 제조업)

사용자의 사업이 **전기절감기(전력 절감 장치) 제조업체**이므로 첫 vertical은 이 업종으로 고정한다. 브리프의 권장 예시(`b2b-service` 등)는 참고만 하고, 실제 원본 자료로 바로 실험할 수 있는 자사 업종을 우선한다.

업종 특성과 설계에 미치는 영향
- **B2B 고관여 구매**: 타깃은 공장·상가·건물·농장의 전기요금 담당자와 설비 관리자, 그리고 대리점·설치업체다. 조회수보다 상담·견적·대리점 문의 전환이 목표라는 원칙과 정확히 맞는다.
- **절감률 과장이 업계 최대 리스크**: "전기요금 30% 절감", "무조건 절감 보장" 류 표현은 규제·신뢰 문제를 일으킨다. 템플릿의 `banned_claims`와 `required_disclaimers`를 이 업종 기준으로 두껍게 잡고, 품질 검사기가 **수치+보장 조합**을 특별히 감지한다.
- **근거 중심 소재**: 설치 전후 계측 데이터, 역률·고조파·전압 안정화 같은 기술 원리, 설치 현장 사진, 고객 검증 사례가 원본이 된다. 원본 기반성 검사가 특히 중요하다.
- **CTA 종류**: 상담문의 / 견적요청 / 대리점문의 / 자료요청(기술자료·검증데이터) / 현장진단신청. 시청자 유형에 따라 드롭다운 기본값이 바뀐다.
- **파트너 모집 콘텐츠의 소재**: 설치 소요 시간과 난이도, 설치 전후 계측으로 고객을 설득하는 방식, 제조사 직접 A/S, 교육·기술 지원, 지역 독점 여부 같은 "팔기 쉬운 이유"가 원본이 된다. 마진율 같은 숫자는 공개 콘텐츠에 넣지 않고 "자료요청"으로 넘긴다.

업종 키는 템플릿 파일명과 1:1로 대응한다 (`src/server/templates/energy-saving-device.json`). 다른 업종은 파일만 추가하면 드롭다운에 자동 노출된다.

## 6. 기능 범위와 우선순위

| 우선순위 | 기능 | 완료 기준 |
|---|---|---|
| P0 | 프로젝트 생성 입력 폼 + 저장 | 필수값 검증 후 SQLite에 저장, 목록에서 다시 열림 |
| P0 | 업종 템플릿 로더 | JSON 파일을 읽어 스키마 검증 후 메모리에 캐시, `/api/templates`로 노출 |
| P0 | 초안 3세트 생성기 | 입력+템플릿 조합으로 서로 다른 angle 3개, 필수 10필드 전부 채움 |
| P0 | 결과 카드 UI | 카드별 전체 필드 표시, 필드별 복사 버튼, 전체 JSON 복사 |
| P0 | 승인/수정중/보류 상태 저장 | 버튼 클릭 즉시 저장, 새로고침 후 유지, 상태 변경 이력 기록 |
| P0 | 이력 화면 | 프로젝트 목록, 프로젝트별 초안 세대 목록, 이벤트 로그 |
| P1 | 품질 검사기 | 과장어·금지어 감지 시 경고 배지, 필수어 누락 경고, CTA 불일치 경고 |
| P1 | 초안 인라인 수정 | 카드에서 필드 편집 → `edited_version_json`에 저장 (원본 보존) |
| P1 | 재생성 | 같은 프로젝트에서 새 세대 생성, 이전 세대 보존 |
| P2 | LLM 생성 모드 | 환경변수로 API 키가 있으면 LLM으로 초안을 다듬고, 없으면 규칙 기반 생성으로 동작 (기본은 규칙 기반) |

## 7. 화면 요구사항

디자인 원칙: 화려함 없이 **가독성·복사 편의·빠른 반복**. 단일 HTML + 바닐라 JS, 좌측 내비 3개.

### 화면 1. 새 프로젝트
- 필드: 프로젝트명*, 업종*(드롭다운, 템플릿에서 자동), **시청자 유형***(라디오: 최종고객 / 파트너 모집), 타깃 고객*(유형 선택 시 템플릿 기본값이 자동 채워지고 수정 가능), 목표 CTA*(드롭다운, 유형에 맞는 CTA만 노출 + 직접입력), 톤(드롭다운: 전문적이지만 쉬운 설명/친근한/단호한/차분한), 원본 텍스트*(textarea), 원본 메모/이미지 메모(textarea, 줄마다 1개), 금지어(쉼표 구분), 필수어(쉼표 구분)
- 버튼: "저장" / "저장 후 초안 생성"
- 검증: 프로젝트명·업종·타깃·CTA·원본 텍스트 필수. 원본 텍스트 최소 30자.

### 화면 2. 결과 패널
- 상단: 프로젝트 요약(업종, 타깃, CTA, 톤), "다시 생성" 버튼, 세대 선택
- 카드 3개(가로 스크롤 또는 세로 나열). 카드 헤더: angle 배지 + 상태 배지
- 카드 본문: hook, script, scene_plan(리스트), video_prompt, title, thumbnail_copy, description, pinned_comment, cta. 필드마다 "복사" 버튼
- 카드 하단: 상태 버튼 3개(승인/수정중/보류), "JSON 복사", 품질 경고 목록
- 상태 변경은 즉시 저장하고 토스트로 확인

### 화면 3. 이력
- 프로젝트 목록 테이블: 생성일, 이름, 업종, CTA, 초안 수, 승인 수
- 행 클릭 → 해당 프로젝트 결과 패널로 이동
- 하단: 최근 이벤트 로그(생성/상태변경/수정) 50건

## 8. 데이터 모델 (SQLite)

브리프 7장을 기준으로 하되, 재생성 세대와 이벤트 로그를 추가한다.

```sql
project (
  id TEXT PK, name, industry, audience_mode ('end_customer'|'partner'),
  target_audience, goal_cta, tone,
  source_text, source_notes,
  banned_phrases_json, required_phrases_json,
  created_at, updated_at
)

source_asset (
  id TEXT PK, project_id FK, type ('text'|'image'|'note'),
  path_or_content, note, created_at
)

template_profile (
  id TEXT PK, industry UNIQUE, name, version, config_json, loaded_at
)   -- 파일에서 로드한 스냅샷. 원본은 JSON 파일.

shorts_draft (
  id TEXT PK, project_id FK, generation INTEGER, draft_index INTEGER,
  angle, hook, script, scene_plan_json, video_prompt,
  title, thumbnail_copy, description, pinned_comment, cta,
  approval_status ('draft'|'approved'|'editing'|'hold'),
  quality_flags_json, edited_version_json, generator ('rule'|'llm'),
  created_at, updated_at
)

event_log (
  id INTEGER PK AUTOINCREMENT, project_id, draft_id NULL,
  event_type ('project.created'|'draft.generated'|'draft.status_changed'|'draft.edited'),
  payload_json, created_at
)
```

ID는 `crypto.randomUUID()`. 시간은 ISO 8601 UTC 문자열.

## 9. 업종 템플릿 스키마

파일: `src/server/templates/<industry>.json`

```json
{
  "industry": "energy-saving-device",
  "name": "전기절감기 제조·설치",
  "version": 1,
  "audiences": {
    "end_customer": {
      "label": "최종고객",
      "audience_defaults": ["공장 전기요금 담당자", "상가·건물 설비 관리자"],
      "pain_points": [
        "전기요금은 오르는데 어디서 새는지 모름",
        "설비는 그대로인데 피크 요금이 튐",
        "절감 장치 광고가 많아 뭘 믿어야 할지 모름",
        "역률 저하로 기본요금 가산"
      ],
      "desired_outcomes": ["계측 데이터로 확인되는 전기요금 절감", "설비 부하 안정화", "설치 후 관리 부담 없음"],
      "hook_patterns": [
        { "angle": "problem", "pattern": "{pain}? {wrong_focus}만 보고 계세요?" },
        { "angle": "before_after", "pattern": "설치 전 {before}, 설치 후 {after}. 계측기로 찍었습니다" },
        { "angle": "mistake", "pattern": "전기절감기 고를 때 {audience}가 가장 많이 속는 {n}가지" }
      ],
      "default_ctas": ["상담문의", "견적요청", "현장진단신청"]
    },
    "partner": {
      "label": "파트너 모집",
      "audience_defaults": ["전기공사업체 대표", "설비 설치업체", "지역 대리점 후보"],
      "pain_points": [
        "절감 장치는 팔고 나서 효과 시비가 생길까 부담",
        "설치가 복잡하면 인건비가 마진을 먹음",
        "A/S를 설치업체가 다 떠안게 될까 걱정",
        "본사 지원 없이 혼자 영업해야 하는 구조"
      ],
      "desired_outcomes": ["계측 리포트로 고객 설득이 되는 제품", "짧은 설치 시간", "제조사 직접 A/S와 교육", "기존 전기공사 고객에 붙여 팔 수 있는 추가 매출"],
      "hook_patterns": [
        { "angle": "problem", "pattern": "전기공사 하시면서 {pain} 때문에 절감기 안 다루셨죠?" },
        { "angle": "before_after", "pattern": "설치 {install_time}, 계측 리포트 한 장으로 계약. 파트너 현장 그대로 보여드립니다" },
        { "angle": "mistake", "pattern": "절감기 대리점 계약 전에 꼭 확인할 {n}가지" }
      ],
      "default_ctas": ["대리점문의", "자료요청"]
    }
  },
  "angles": [
    { "key": "problem", "label": "문제 제기형", "script_beats": ["문제 제시", "원인(기술 원리)", "해결", "CTA"] },
    { "key": "before_after", "label": "전후 비교형", "script_beats": ["설치 전 계측", "설치 후 계측", "차이와 조건", "CTA"] },
    { "key": "mistake", "label": "실수 방지형", "script_beats": ["흔한 실수·과장 광고", "왜 문제인지", "제대로 고르는 기준", "CTA"] }
  ],
  "cta_patterns": {
    "상담문의": ["현장 조건 알려주시면 적용 가능 여부부터 상담해 드립니다."],
    "견적요청": ["계약전력과 월 사용량만 알려주시면 견적 드립니다."],
    "대리점문의": ["지역 대리점·설치 파트너 문의는 프로필 링크로 주세요."],
    "자료요청": ["설치 전후 계측 자료 필요하시면 댓글에 '자료'라고 남겨주세요."],
    "현장진단신청": ["현장 부하 진단 신청은 프로필 링크에서 받습니다."]
  },
  "banned_claims": [
    "무조건", "100%", "누구나", "확실히 보장", "절감 보장", "전기요금 반값",
    "설치만 하면", "즉시 절감", "정부 인증 절감률", "모든 설비에"
  ],
  "claim_rules": {
    "percent_with_guarantee": "절감률 수치와 '보장/확실/무조건'이 같은 문장에 오면 경고",
    "percent_without_condition": "절감률 수치가 있으면 '현장 조건에 따라 다름' 류 조건 문구가 같은 초안에 있어야 함"
  },
  "required_disclaimers": ["절감 효과는 설비 부하·사용 패턴·현장 조건에 따라 달라집니다."],
  "preferred_video_styles": ["현장 계측기 화면 클로즈업 + 자막", "설치 전후 계측값 스플릿 비교", "설치 현장 실사 + 원리 도해"],
  "scene_plan_template": [
    { "t": "0-3초", "role": "hook" }, { "t": "4-8초", "role": "problem" },
    { "t": "9-15초", "role": "solution" }, { "t": "16-20초", "role": "cta" }
  ],
  "vocabulary": {
    "domain_terms": ["역률", "피크", "계약전력", "고조파", "전압 안정화", "kWh", "기본요금", "부하", "계측", "무효전력"]
  }
}
```

로더는 필수 키 존재, `angles` 3개 이상, `audiences`에 `end_customer`와 `partner` 두 키가 모두 있는지를 검증하고, 실패 시 서버 기동을 막는다. `claim_rules`는 이 업종 전용 확장 키이며, 품질 검사기가 존재할 때만 적용한다. `angles`, `cta_patterns`, `banned_claims`, `required_disclaimers`, `preferred_video_styles`, `scene_plan_template`, `vocabulary`는 두 시청자 유형이 공유한다.

## 10. 초안 생성 파이프라인

```
입력(project) + 템플릿 → 원본 분석 → angle 3개 선택 → 필드 조립 → 품질 검사 → 저장
```

0. **시청자 유형 분기**: `project.audience_mode`로 템플릿 `audiences[mode]`를 고른다. 이후 단계의 `pain_points`, `hook_patterns`, `audience_defaults`는 모두 이 하위 객체에서 온다. 파트너 모집 모드에서는 `mistake` angle이 "대리점 계약 전 확인할 것"으로, `before_after`가 "설치 시간·계약 과정"으로 해석되도록 angle별 `script_beats`를 유형별로 덮어쓸 수 있게 한다(`audiences[mode].angle_overrides`, 선택).
1. **원본 분석**: `source_text`를 문장 단위로 나누고, 템플릿 `domain_terms`·`pain_points`와 겹치는 문장을 핵심 문장으로 뽑는다. 숫자·전후 표현("전/후", "%", "kW")을 추출해 전후비교형 소재로 쓴다. 이미지 메모는 scene_plan에 실제 화면 소재로 배치한다.
2. **angle 선택**: 템플릿 `angles`에서 서로 다른 3개를 고정 순서로 사용한다 (문제제기형 → 전후비교형 → 실수방지형). 각 angle은 자기 `hook_patterns`만 쓴다.
3. **필드 조립** (필드별 규칙)
   - `hook`: angle 패턴에 핵심 문장의 pain/소재를 채움. 25자 내외, 물음표 또는 숫자 포함 우선.
   - `script`: 15~25초 분량(공백 포함 180~260자). `script_beats` 순서로 4단락. 마지막 단락은 CTA. 원본 핵심 문장을 최소 1개 그대로 또는 축약해 포함(원본 기반성).
   - `scene_plan`: `scene_plan_template` 시간대에 role별 문장 배치. 이미지 메모가 있으면 해당 장면에 "(자료: 파일명)" 표기.
   - `video_prompt`: 세로 9:16, 20초, `preferred_video_styles` 중 angle에 맞는 것 1개, 장면 4개 요약, 자막 포함, 실제 촬영 소재 우선이라는 지시문. 한국어 설명 + 핵심 영문 키워드.
   - `title`: 30자 이내, hook과 다른 표현.
   - `thumbnail_copy`: 12자 이내 2줄까지.
   - `description`: 2~3문장 + `required_disclaimers` 1개 + 해시태그 3~5개.
   - `pinned_comment`: CTA 유도 1문장 + 무엇을 보내달라는 구체 요청.
   - `cta`: `goal_cta` 그대로. `cta_patterns[goal_cta]`가 있으면 문장형도 script 마지막에 사용.
4. **품질 검사** (결과는 `quality_flags_json`에 저장, 카드에 배지로 표시)
   - `exaggeration`: 템플릿 `banned_claims` + 공통 과장어 사전("무조건", "100%", "누구나 쉽게", "큰돈") 감지. 감지 시 완화 표현으로 치환 시도 후에도 남으면 경고.
   - `claim_guarantee`: 절감률 수치(`\d+%`)와 보장성 표현이 한 문장에 함께 있으면 경고. 수치가 있는데 조건 문구(`required_disclaimers`)가 초안 어디에도 없으면 description에 자동 추가.
   - `banned_phrase`: 프로젝트 금지어 포함 시 치환 불가 → 경고.
   - `required_phrase_missing`: 필수어가 script/description 어디에도 없으면 description 끝에 자연스럽게 추가, 실패 시 경고.
   - `cta_mismatch`: `cta` 필드와 script 마지막 단락의 CTA 유형이 다르면 경고.
   - `source_grounding_weak`: 원본 핵심 문장이 script에 하나도 반영되지 않으면 경고.
5. **생성기 인터페이스**: `generateDrafts(project, template, options) → Draft[3]`. 기본 구현은 규칙 기반(`ruleGenerator`). P2에서 `llmGenerator`가 같은 인터페이스로 들어오며, 결과는 동일한 품질 검사를 통과해야 한다. 어느 쪽이 만들었는지 `generator` 컬럼에 남긴다.

## 11. 출력 스키마 (draft)

핸드오프 03 문서와 동일하며, 검수용 메타 필드를 추가한다.

```json
{
  "id": "uuid", "project_id": "uuid", "generation": 1, "draft_index": 0,
  "audience_mode": "end_customer",
  "angle": "문제 제기형",
  "hook": "전기요금은 오르는데 설비는 그대로? 역률부터 보셨어요?",
  "script": "...",
  "scene_plan": [
    { "t": "0-3초", "role": "hook", "text": "...", "visual_source": "screen", "asset_ref": "before_after_meter.jpg" },
    { "t": "4-8초", "role": "problem", "text": "...", "visual_source": "ai", "asset_ref": null },
    { "t": "9-15초", "role": "solution", "text": "...", "visual_source": "photo", "asset_ref": "install_site.jpg" },
    { "t": "16-20초", "role": "cta", "text": "...", "visual_source": "screen", "asset_ref": null }
  ],
  "video_prompt": "...",
  "title": "...", "thumbnail_copy": "...", "description": "...",
  "pinned_comment": "...", "cta": "상담문의",
  "approval_status": "draft",
  "quality_flags": [{ "type": "exaggeration", "field": "hook", "match": "100%" }],
  "generator": "rule",
  "created_at": "..."
}
```

필수 10필드(`angle`~`cta`)가 하나라도 비면 서버가 저장을 거부하고 500 대신 422로 이유를 돌려준다.

## 12. API

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/api/templates` | 로드된 업종 템플릿 목록(industry, name, angles 요약) |
| GET | `/api/templates/:industry` | 템플릿 전체 |
| POST | `/api/projects` | 프로젝트 생성. 본문 검증 실패 시 422 |
| GET | `/api/projects` | 프로젝트 목록 + 초안 수/승인 수 |
| GET | `/api/projects/:id` | 프로젝트 상세 + 자산 + 초안(세대별) |
| POST | `/api/projects/:id/generate` | 새 세대 초안 3세트 생성·저장 |
| PATCH | `/api/drafts/:id/status` | `{status}` 승인/수정중/보류/초안 |
| PATCH | `/api/drafts/:id` | 편집본 저장 (`edited_version`) |
| GET | `/api/history?limit=50` | 이벤트 로그 |

에러 형식: `{ "error": { "code": "VALIDATION", "message": "...", "fields": {...} } }`

## 13. 기술 스택과 구조 (MPT 포크 기준)

- 베이스: MoneyPrinterTurbo 포크 (`gino-hash/MoneyPrinterTurbo`). Python 3.11, Streamlit 웹UI, FastAPI, FFmpeg
- 회사 전용 코드는 `app/ecozin/` 아래에 모으고 원본 파일 수정은 최소화한다(업스트림 병합 대비)
- 저장: SQLite (`storage/ecozin.db`), MPT의 task 저장소와 분리
- 렌더링 연결: MPT `VideoParams`에 `video_script`(우리 대본), `video_source="local"`, `video_materials`(장면별 사진·클립), 한국어 Edge TTS, 자막 활성화로 작업 생성. `upload_post_enabled=false` 고정
- 테스트: `pytest`로 생성기·검사기·연동 파라미터 변환 테스트

```
MoneyPrinterTurbo/            # 포크
  app/
    ecozin/                   # 회사 모듈 (신규)
      db.py                   # SQLite 스키마
      templates/
        energy_saving_device.json
      template_loader.py
      generators/
        rule_generator.py     # 초안 3세트
        source_analyzer.py
        quality_checker.py    # 과장·금지어·필수어·CTA·원본기반성·절감률보장
      bridge.py               # 승인 초안 → MPT VideoParams 변환, 프리뷰/최종 작업 생성
      models.py               # Project / Draft / Scene / Event 데이터클래스
    services/                 # MPT 원본 (건드리지 않음)
  webui/
    pages/
      10_기획_워크벤치.py      # 화면 1~3 (입력·결과 카드·이력)
      11_프리뷰_검수.py         # 2단계 관문 (후속)
  config.toml                 # 회사 PC 설정 (git 제외)
  docs/ecozin/
    PRD.md                    # 이 문서
    handoff/
  tests/ecozin/
```

## 14. 상태 모델

```
draft ──승인──▶ approved
  │  └──수정중──▶ editing ──승인──▶ approved
  └──보류──▶ hold ──(되돌리기)──▶ draft
```

- 모든 전이는 허용하되 `event_log`에 이전/이후 상태를 기록한다.
- `approved`는 "배포해도 됨"이라는 사람의 결정이며, 시스템은 그 이후 아무것도 자동으로 하지 않는다.

## 15. 검증 기준 (Exit Criteria)와 테스트

브리프 12장 그대로를 수용 기준으로 삼고, 각 항목에 자동 테스트를 1개 이상 붙인다.

| # | 기준 | 검증 방법 |
|---|---|---|
| 1 | 새 프로젝트를 생성할 수 있다 | API 테스트: POST 후 GET으로 동일 값 |
| 2 | source_text를 저장할 수 있다 | 위와 동일, 30자 미만 시 422 |
| 3 | 업종 템플릿 1개를 불러올 수 있다 | 로더 테스트: 필수 키 검증, 잘못된 파일은 기동 실패 |
| 4 | 초안 3세트가 생성된다 | 생성기 테스트: 길이 3, angle 3개 서로 다름 |
| 5 | 각 초안에 필수 필드가 모두 있다 | 스키마 검증 테스트: 10필드 비어있지 않음 |
| 6 | 승인/보류 상태를 저장할 수 있다 | PATCH 후 GET, event_log 1건 증가 |
| 7 | 이전 프로젝트/이력을 다시 볼 수 있다 | 서버 재시작 후 GET /api/projects 유지 |
| + | 과장어가 경고된다 | "100% 보장" 원본 입력 시 `exaggeration` 플래그 |
| + | 절감률 보장 표현 감지 | "30% 절감 보장" 입력 시 `claim_guarantee` 플래그, 조건 문구 자동 삽입 |
| + | CTA 정합성 | goal_cta=견적요청 → 3개 초안 cta 모두 "견적요청" |
| + | 시청자 유형 분기 | 같은 원본으로 end_customer와 partner를 각각 생성하면 hook이 서로 다르고, partner 초안에는 "대리점" 또는 "파트너" 어휘가 포함 |

수동 검증 시나리오: 아래 샘플 프로젝트를 입력해 3세트가 서로 다른 각도로 나오고 과장 경고가 정상 동작하는지 확인한다.
- 프로젝트명: 전기절감기 공장 설치 사례 쇼츠
- 시청자 유형: 최종고객 (같은 원본으로 파트너 모집도 한 번 더 생성해 비교)
- 타깃: 월 전기요금 500만원 이상 공장 전기 담당자
- CTA: 견적요청
- 원본 텍스트 예시: "경기도 A공장 설치 전후 계측. 역률 0.82에서 0.96으로 개선, 기본요금 가산 해소. 월 사용량 기준 약 8% 절감 확인(3개월 평균). 설치 2시간, 생산라인 중단 없음. 설치 전후 계측 리포트 제공."
- 이미지 메모: "before_after_meter.jpg (계측기 화면 비교)", "install_site.jpg (배전반 설치 현장)"
- 금지어: "반값", 필수어: "계측 리포트"

## 16. 전체 로드맵과 이번 범위

사용자가 원하는 최종 형태는 "회사 자료를 넣으면 프리뷰까지 자동으로 만들고, 사람이 프리뷰를 확인한 뒤 최종 영상을 생성하는" 흐름이다. 이를 4단계로 나누고, **이번 PRD는 1단계만** 구현한다. 단, 2·3단계가 붙을 자리는 지금 만들어 둔다.

| 단계 | 입력 | 출력 | 사람의 관문 | 상태 |
|---|---|---|---|---|
| 1. 기획 패키지 | 원본 텍스트·이미지 메모 | 초안 3세트(10필드) | 초안 승인 | **이번 범위** |
| 2. 프리뷰 생성 | 승인된 초안 | 장면별 저해상도 클립 + 자막·음성 합성 프리뷰 영상 | 장면 단위 재생성·교체·확정 | 후속 |
| 3. 최종 생성 | 확정된 장면 구성 | 고화질 9:16 영상 파일 + 썸네일 + 업로드 문구 묶음 | 최종 확인 후 수동 업로드 | 후속 |
| 4. 성과 피드백 | 업로드 후 조회·문의 수 | 훅·각도별 전환 통계, 템플릿 가중치 제안 | 템플릿 조정 승인 | 선택 |

### 1단계에서 미리 확보할 확장 지점
- `approval_status`에 후속 상태를 추가할 수 있도록 CHECK 제약 대신 코드 상수로 관리한다. 예정 상태: `approved` → `preview_generating` → `preview_ready` → `scenes_locked` → `final_generating` → `final_ready`.
- `scene_plan`의 각 장면은 문자열이 아니라 객체로 저장한다: `{ t, role, text, visual_source: 'photo'|'ai'|'screen', asset_ref }`. 2단계에서 실사(`photo`)는 생성 없이 붙이고 `ai`만 생성 API로 보낸다. 카드 UI에는 1단계에서 "0-3초: ..." 문자열로 펼쳐 보여준다.
- `source_asset` 테이블을 1단계부터 실제로 쓴다(이미지 메모 한 줄 = 자산 1건). 2단계에서 파일 업로드가 붙으면 `path_or_content`에 경로가 들어간다.
- 생성기 인터페이스(`generateDrafts`)와 같은 방식으로 `generatePreview(draft)`, `generateFinal(draft)`가 들어올 자리를 `src/server/generators/`에 남긴다. 1단계에서는 구현하지 않는다.
- 영상 생성 API 연동은 어댑터 한 파일로 격리한다(예: `src/server/adapters/videoProvider.js`). 1단계에서는 파일만 두고 비워 둔다.

### 후속 범위 (04 Codex 보강지점 반영)
이번 MVP 이후에 넘길 항목. 구조는 이를 막지 않도록 설계한다.
1. 생성 로직 리팩토링 및 LLM 생성기 추가 (같은 인터페이스)
2. JSON 스키마 엄격화 (zod 등 도입 여부 검토)
3. 에러 처리·로깅 보강
4. 복사/상태 UX 개선, 키보드 단축키
5. 업종 템플릿 2~3개 확장 (`b2b-service`, `education-coaching`)
6. 금지어/필수어 반영 로직 고도화 (형태소 단위 매칭)
7. 초안 비교 뷰, 승인본 내보내기(마크다운/CSV)
8. 2단계 PRD 작성: 프리뷰 생성 파이프라인, 영상 생성 API 선택, 비용 상한, 실사/AI 혼합 규칙

### 2·3단계 렌더링 엔진 후보 (2026-09 조사)
음성·자막·합성·렌더링은 직접 만들지 않고 기존 오픈소스를 어댑터로 붙인다.
- 1순위: MoneyPrinterTurbo (MIT, Python, REST API 제공, 스톡+AI 영상+로컬 미디어 업로드 지원, Claude 등 LLM 선택 가능). 1단계가 내놓은 승인 대본·장면 계획을 API로 넘겨 렌더링.
- 참고: ShortGPT (한국어 TTS 지원 확인), Viral-Faceless-Shorts-Generator (렌더링 전 사람 승인 관문 구조 참고).
- 공통 한계: 모두 스톡 영상 중심의 페이스리스 채널용이라 업종 문맥·과장 차단·원본 기반성·시청자 분기는 없다. 그 부분이 1단계의 고유 가치다.

## 17. 리스크와 열린 질문

| 항목 | 내용 | 기본 결정 |
|---|---|---|
| 규칙 기반 생성 품질 | 템플릿 조합만으로는 문장이 기계적일 수 있음 | MVP는 규칙 기반으로 "흐름 검증"이 목적. 품질은 P2 LLM 모드에서 올림 |
| `node:sqlite` 실험 상태 | Node 22에서 경고 로그 출력 | 기동 시 `--no-warnings` 옵션 적용. 문제 시 `better-sqlite3`로 교체 가능하도록 db.js 한 파일에 격리 |
| 이미지 처리 | 업로드·저장은 범위 밖 | 파일명/경로/메모 텍스트만 받음 |
| 저장소 | 새 GitHub 저장소 생성이 권한 문제로 실패 | 로컬 git으로 시작, 저장소 준비되면 remote 연결 |
| 절감률 표현 규제 | 전기절감기 업종은 절감률 과장 광고가 규제·신뢰 리스크 | 템플릿 `banned_claims`·`claim_rules`로 1차 차단, 최종 판단은 사람 검수 |
| 업종 선택 | 전기절감기 제조업(`energy-saving-device`)으로 확정 | 사용자 확인 완료. 다른 업종은 템플릿 파일 추가로 확장 |
| 시청자 유형 | 최종고객과 파트너 모집 둘 다 필요 | 사용자 확인 완료. 프로젝트당 1개 선택, 템플릿에 두 유형 분리 정의 |

## 18. 구현 순서 (MPT 포크 기준)

| 순서 | 작업 | 담당 | 예상 |
|---|---|---|---|
| 0 | 회사 PC에 MPT 원본 설치, Edge TTS 한국어·local 소재·자막 폰트 설정, 우리 대본+사진으로 1편 렌더링 테스트. 정지 이미지 처리 품질 확인 | 사용자(또는 텔레그램 봇) | 1~2h |
| 1 | GitHub에서 MPT 포크 → `gino-hash/MoneyPrinterTurbo`, Claude 접근 허용 | 사용자 | 30m |
| 2 | `app/ecozin/` 모듈: DB, 템플릿, 생성기, 검사기 + 기획 워크벤치 탭(입력·카드·승인·이력) | Claude | 2~3h |
| 3 | `bridge.py`: 승인 초안 → MPT 작업(프리뷰 저해상도 / 최종 고해상도 두 버튼) | Claude | 1~2h |
| 4 | 세 관문(초안 승인 → 프리뷰 확인 → 최종 생성) 화면 고정 + 이벤트 로그 | Claude | 1h |
| 5 | 실제 설치 사례 3~5건으로 훅·대본 템플릿 튜닝 | 공동 | 반복 |

완료 후 보고 형식: 프로젝트 구조 / 실행 방법 / 주요 파일 설명 / 현재 되는 것 / 아직 안 넣은 것 / 다음 우선순위 3개.

### 0단계 확인 항목
- 정지 이미지(JPG/PNG)를 `video_materials`로 넣었을 때 클립으로 변환되는지, 안 되면 FFmpeg로 3~5초 클립 변환 전처리를 `bridge.py`에 넣는다.
- Edge TTS 한국어 음성 이름과 품질.
- 한글 자막 폰트 경로.
- 프리뷰용 저해상도 설정 가능 여부(없으면 짧은 길이·낮은 비트레이트로 대체).
