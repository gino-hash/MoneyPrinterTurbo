# 출력 예시 JSON 스키마

```json
{
  "project": {
    "name": "태양광 점검 쇼츠 실험",
    "industry": "solar-maintenance",
    "target_audience": "태양광 설비 운영자",
    "goal_cta": "상담문의",
    "tone": "전문적이지만 쉬운 설명"
  },
  "source_assets": [
    { "type": "text", "content": "패널 오염, 인버터 이상, 발전량 저하를 빠르게 점검하는 서비스 소개" },
    { "type": "image", "content": "before_after_panel.jpg" }
  ],
  "drafts": [
    {
      "angle": "문제 제기형",
      "hook": "발전량이 줄었는데 패널만 의심하고 계세요?",
      "script": "...20초 대본...",
      "scene_plan": ["0-3초: 문제 화면", "4-8초: 원인 제시", "9-15초: 해결 과정", "16-20초: CTA"],
      "video_prompt": "...영상 생성 툴용 프롬프트...",
      "title": "발전량 떨어질 때 제일 먼저 볼 것",
      "thumbnail_copy": "발전량 저하 원인 3초 체크",
      "description": "설비 이상, 발전량 저하가 반복된다면 점검이 먼저예요...",
      "pinned_comment": "점검 체크리스트 필요하시면 댓글이나 문의 주세요.",
      "cta": "상담문의"
    }
  ]
}
```

## 필수 출력 필드
- `angle`
- `hook`
- `script`
- `scene_plan`
- `video_prompt`
- `title`
- `thumbnail_copy`
- `description`
- `pinned_comment`
- `cta`

## MVP 규칙
- 초안은 **기본 3세트** 생성
- 각 초안은 업종 문맥이 달라야 함
- 과장 표현은 자동으로 줄이거나 경고 표시
- 출력은 복붙 가능한 텍스트여야 함
- 영상 생성 자체보다 **콘텐츠 패키지 완성도**를 우선함
