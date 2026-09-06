"""원본 텍스트·이미지 메모 분석. 생성기가 쓸 소재(핵심 문장, 숫자, 전후 값, 현장명, 자산)를 뽑는다."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from app.ecozin.models import SourceAsset

_SENT_SPLIT = re.compile(r"(?<=[.!?。])\s+|\n+")
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_BEFORE_AFTER_PATTERNS = [
    # 역률 0.82에서 0.96으로 / 0.82 → 0.96 / 0.82에서 0.96
    re.compile(r"([가-힣A-Za-z\s]{0,12}?)\s*(\d+(?:\.\d+)?\s*(?:%|kWh|kW|원|만원|배)?)\s*(?:에서|→|->|에서부터)\s*(\d+(?:\.\d+)?\s*(?:%|kWh|kW|원|만원|배)?)\s*(?:으로|로)?"),
    # 설치 전 X, 설치 후 Y
    re.compile(r"설치\s*전\s*([^,，.]{1,20}?)[,，]?\s*설치\s*후\s*([^,，.]{1,20})"),
]
_INSTALL_TIME = re.compile(r"설치\s*(?:시간|소요)?\s*(?:은|는)?\s*(\d+\s*(?:시간|분|일))")
_SITE = re.compile(
    r"((?:[가-힣]{2,6}\s*)?(?:풍력|태양광|수력)?\s*발전\s*(?:단지|소)(?:\s*\d+호기)?"
    r"|(?:[가-힣]+(?:도|시|군|구)\s*)?[A-Za-z가-힣0-9]{1,12}(?:공장|빌딩|상가|농장|축사|센터|물류창고|창고|병원|학교|호텔|아파트|사업장|공단|현장))")
_BASELINE_HINT = re.compile(r"예정|실증|기준\s*데이터|설치\s*전\s*기준|계측을\s*시작|계측기를\s*설치|계측부터")
_IMAGE_EXT = re.compile(r"\.(jpe?g|png|webp|gif|mp4|mov|mkv)$", re.I)
_MEMO_LINE = re.compile(r"^\s*([^\s(（]+\.(?:jpe?g|png|webp|gif|mp4|mov|mkv))\s*[(（]?\s*([^)）]*)\s*[)）]?\s*$", re.I)


@dataclass
class Analysis:
    sentences: list[str] = field(default_factory=list)
    key_sentences: list[str] = field(default_factory=list)
    terms_found: list[str] = field(default_factory=list)
    percents: list[str] = field(default_factory=list)
    before: Optional[str] = None
    after: Optional[str] = None
    metric: Optional[str] = None
    install_time: Optional[str] = None
    site: Optional[str] = None
    pain_hits: list[Any] = field(default_factory=list)
    cause_term: str = ""
    stage: str = "general"  # result(전후 숫자 있음) | baseline(설치 전 계측 중) | general
    assets: list[dict[str, Any]] = field(default_factory=list)

    @property
    def has_before_after(self) -> bool:
        return bool(self.before and self.after)

    def short(self, text: str, limit: int = 28) -> str:
        text = text.strip().rstrip(".。")
        return text if len(text) <= limit else text[: limit - 1] + "…"


def pain_text(p: Any) -> str:
    return p["text"] if isinstance(p, dict) else str(p)


def pain_field(p: Any, key: str) -> str:
    """dict 통점이면 short/question 을, 문자열이면 text 자체를 돌려준다."""
    if isinstance(p, dict):
        return p.get(key) or p.get("text", "")
    return str(p)


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENT_SPLIT.split(text or "") if p and p.strip()]
    out: list[str] = []
    for p in parts:
        # "A. B" 형태가 한 조각으로 남은 경우 추가 분리
        for q in re.split(r"(?<=[가-힣\d)])\.\s+(?=[가-힣A-Z])", p):
            q = q.strip()
            if q:
                out.append(q if q[-1] in ".!?" else q + ".")
    return out


def parse_image_memos(source_notes: str) -> list[dict[str, Any]]:
    """'파일명 (설명)' 형태의 줄을 자산으로 해석한다. 파일명이 없는 줄은 note 자산."""
    assets = []
    for line in (source_notes or "").splitlines():
        line = line.strip().lstrip("-•*").strip()
        if not line:
            continue
        m = _MEMO_LINE.match(line)
        if m:
            assets.append({"type": "image", "ref": m.group(1), "note": m.group(2).strip()})
        elif _IMAGE_EXT.search(line.split()[0]):
            first, *rest = line.split(None, 1)
            assets.append({"type": "image", "ref": first, "note": (rest[0] if rest else "").strip("()（） ")})
        else:
            assets.append({"type": "note", "ref": "", "note": line})
    return assets


def _term_score(sentence: str, terms: list[str], pains: list[str]) -> tuple[int, list[str]]:
    hits = [t for t in terms if t and t in sentence]
    score = len(hits) * 2
    if _PERCENT.search(sentence):
        score += 2
    if re.search(r"\d", sentence):
        score += 1
    for p in pains:
        for token in re.findall(r"[가-힣]{2,}", pain_text(p)):
            if token in sentence:
                score += 1
                break
    return score, hits


def analyze(source_text: str, source_notes: str, template: dict[str, Any], audience: dict[str, Any],
            uploaded_assets: Optional[list[SourceAsset]] = None) -> Analysis:
    a = Analysis()
    a.sentences = split_sentences(source_text)
    terms = list(template.get("vocabulary", {}).get("domain_terms", []))
    pains = list(audience.get("pain_points", []))

    scored = []
    for s in a.sentences:
        score, hits = _term_score(s, terms, pains)
        scored.append((score, s, hits))
        for h in hits:
            if h not in a.terms_found:
                a.terms_found.append(h)
    scored.sort(key=lambda x: -x[0])
    a.key_sentences = [s for score, s, _ in scored if score > 0][:4] or a.sentences[:3]

    a.percents = [m.group(1) + "%" for m in _PERCENT.finditer(source_text or "")]

    for pat in _BEFORE_AFTER_PATTERNS:
        m = pat.search(source_text or "")
        if m:
            if m.re is _BEFORE_AFTER_PATTERNS[0]:
                metric = m.group(1).strip()
                a.metric = metric if metric else None
                a.before, a.after = m.group(2).strip(), m.group(3).strip()
            else:
                a.before, a.after = m.group(1).strip(), m.group(2).strip()
            break

    m = _INSTALL_TIME.search(source_text or "")
    if m:
        a.install_time = m.group(1).replace(" ", "")
    m = _SITE.search(source_text or "")
    if m:
        a.site = m.group(1).strip()

    for p in pains:
        tokens = [t for t in re.findall(r"[가-힣]{2,}", pain_text(p)) if len(t) >= 2]
        # 느슨한 매칭 방지: 앞 4개 토큰 중 2개 이상이 원본에 있어야 통점으로 본다
        if sum(1 for t in tokens[:4] if t in (source_text or "")) >= 2:
            a.pain_hits.append(p)

    if a.has_before_after or a.percents:
        a.stage = "result"
    elif _BASELINE_HINT.search(source_text or ""):
        a.stage = "baseline"
    else:
        a.stage = "general"

    cause_terms = list(template.get("vocabulary", {}).get("cause_terms", []))
    a.cause_term = next((c for c in cause_terms if c in (source_text or "")), cause_terms[0] if cause_terms else "")

    a.assets = parse_image_memos(source_notes)
    for ua in uploaded_assets or []:
        if ua.type == "image":
            import os
            name = os.path.basename(ua.path_or_content)
            if not any(x["ref"] == name for x in a.assets):
                a.assets.append({"type": "image", "ref": name, "note": ua.note or "", "path": ua.path_or_content})
            else:
                for x in a.assets:
                    if x["ref"] == name:
                        x["path"] = ua.path_or_content
    return a


def classify_asset_visual(asset: dict[str, Any]) -> str:
    """자산 메모로 화면 캡처인지 실사 사진인지 추정한다."""
    text = f"{asset.get('ref','')} {asset.get('note','')}".lower()
    if any(k in text for k in ("설치 중", "작업", "외관", "전경", "현장 사진", "엔지니어")):
        return "photo"
    if any(k in text for k in ("화면", "캡처", "screen", "그래프", "리포트", "report", "meter", "데이터")):
        return "screen"
    return "photo"
