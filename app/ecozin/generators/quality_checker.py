"""출력 품질 검사. 과장어 완화·경고, 금지어, 필수어, 절감률 보장 표현, CTA 정합성, 원본 기반성."""

from __future__ import annotations

import re
from typing import Any

from app.ecozin.models import Draft, QualityFlag, Project

_COMMON_EXAGGERATION = ["무조건", "100%", "누구나 쉽게", "큰돈", "무조건 절감", "확실히 보장"]
_TEXT_FIELDS = ("hook", "script", "title", "thumbnail_copy", "description", "pinned_comment", "video_prompt")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?。\n])\s*")


def _split(text: str) -> list[str]:
    return [s for s in _SENTENCE_SPLIT.split(text or "") if s.strip()]


_QUOTED = re.compile(r"(['\"“‘])(.+?)(['\"”’])")


def _split_quoted(text: str) -> list[tuple[str, bool]]:
    """따옴표로 감싼 구간(남의 과장 광고를 인용하는 부분)은 완화·경고 대상에서 제외한다."""
    parts: list[tuple[str, bool]] = []
    pos = 0
    for m in _QUOTED.finditer(text):
        if m.start() > pos:
            parts.append((text[pos:m.start()], False))
        parts.append((m.group(0), True))
        pos = m.end()
    if pos < len(text):
        parts.append((text[pos:], False))
    return parts or [(text, False)]


def unquoted_text(text: str) -> str:
    return "".join(seg for seg, quoted in _split_quoted(text) if not quoted)


def soften(text: str, softening_map: dict[str, str]) -> tuple[str, list[str]]:
    """완화 사전으로 치환. 인용 구간은 건드리지 않는다. 치환된 원문 표현 목록을 함께 돌려준다."""
    replaced = []
    out = []
    for seg, quoted in _split_quoted(text):
        if not quoted:
            for bad, good in sorted(softening_map.items(), key=lambda kv: -len(kv[0])):
                if bad in seg:
                    seg = seg.replace(bad, good)
                    replaced.append(bad)
        out.append(seg)
    return "".join(out), replaced


def check_and_fix(draft: Draft, project: Project, template: dict[str, Any], key_sentences: list[str]) -> Draft:
    flags: list[QualityFlag] = []
    banned_claims = list(template.get("banned_claims", [])) + _COMMON_EXAGGERATION
    softening = template.get("softening_map", {})
    claim_rules = template.get("claim_rules", {}) or {}
    guarantee_words = claim_rules.get("guarantee_words", ["보장", "확실", "무조건", "반드시"])
    percent_re = re.compile(claim_rules.get("percent_regex", r"\d+(?:\.\d+)?\s*%"))
    disclaimers = list(template.get("required_disclaimers", []))

    # 1) 과장어 완화 후 남은 것 경고
    for f in _TEXT_FIELDS:
        text = getattr(draft, f)
        new_text, replaced = soften(text, softening)
        if replaced:
            setattr(draft, f, new_text)
            flags.append(QualityFlag("exaggeration_softened", f, ", ".join(sorted(set(replaced))),
                                     f"과장 표현을 완화했습니다: {', '.join(sorted(set(replaced)))}", "info"))
        text = unquoted_text(getattr(draft, f))
        for bad in sorted(set(banned_claims), key=len, reverse=True):
            if bad and bad in text:
                flags.append(QualityFlag("exaggeration", f, bad, f"과장·금지 표현 '{bad}' 이(가) 남아 있습니다. 수정하세요.", "warn"))

    # 2) 프로젝트 금지어 (인용 구간 포함 전부 검사)
    for f in _TEXT_FIELDS:
        text = getattr(draft, f)
        for bad in project.banned_phrases:
            if bad and bad in text:
                flags.append(QualityFlag("banned_phrase", f, bad, f"금지어 '{bad}' 포함. 치환할 수 없어 경고만 표시합니다.", "block"))

    # 3) 절감률 수치 + 보장성 표현이 한 문장에 (인용 제외)
    for f in ("hook", "script", "title", "thumbnail_copy", "description"):
        for sent in _split(unquoted_text(getattr(draft, f))):
            if percent_re.search(sent) and any(g in sent for g in guarantee_words):
                flags.append(QualityFlag("claim_guarantee", f, sent.strip()[:40],
                                         "절감률 수치와 보장성 표현이 한 문장에 있습니다. 규제 리스크가 큽니다.", "block"))

    # 4) 수치가 있으면 조건 문구가 어딘가에 있어야 함
    has_percent = any(percent_re.search(getattr(draft, f)) for f in ("hook", "script", "title", "description"))
    all_text = " ".join(getattr(draft, f) for f in _TEXT_FIELDS)
    if has_percent and disclaimers and not any(d in all_text for d in disclaimers):
        draft.description = (draft.description.rstrip() + "\n" + disclaimers[0]).strip()
        flags.append(QualityFlag("disclaimer_added", "description", disclaimers[0][:20],
                                 "절감률 수치가 있어 조건 문구를 설명에 추가했습니다.", "info"))

    # 5) 필수어
    for phrase in project.required_phrases:
        if phrase and phrase not in all_text:
            draft.description = (draft.description.rstrip() + f"\n※ {phrase} 안내 가능합니다.").strip()
            flags.append(QualityFlag("required_phrase_added", "description", phrase,
                                     f"필수어 '{phrase}' 가 없어 설명에 추가했습니다. 문맥을 확인하세요.", "info"))

    # 6) CTA 정합성: cta 필드와 script 마지막 단락
    last_par = draft.script.strip().split("\n")[-1] if draft.script.strip() else ""
    cta_sentence = template.get("cta_patterns", {}).get(draft.cta, "")
    cta_tokens = [t for t in re.findall(r"[가-힣]{2,}", draft.cta)]
    if draft.cta != project.goal_cta:
        flags.append(QualityFlag("cta_mismatch", "cta", draft.cta, f"목표 CTA({project.goal_cta})와 다릅니다.", "warn"))
    elif not (any(t in last_par for t in cta_tokens) or (cta_sentence and cta_sentence[:8] in last_par)):
        flags.append(QualityFlag("cta_mismatch", "script", last_par[:30], "대본 마지막 단락에 CTA 문장이 없습니다.", "warn"))

    # 7) 원본 자체의 과장 표현 안내 (대본에 안 들어갔더라도, 사람이 옮겨 쓸 때 주의하도록)
    src = unquoted_text(project.source_text or "")
    src_bad = sorted({b for b in banned_claims if b and b in src}, key=len, reverse=True)
    for sent in _split(src):
        if percent_re.search(sent) and any(g in sent for g in guarantee_words):
            src_bad.append(sent.strip()[:30])
            break
    if src_bad:
        flags.append(QualityFlag("source_exaggeration", "source_text", ", ".join(src_bad[:4]),
                                 "원본 자료에 과장·보장성 표현이 있습니다. 대본에는 반영하지 않았으니 옮겨 쓸 때 주의하세요.", "info"))

    # 8) 원본 기반성: 핵심 문장 조각(8자 이상)이 대본에 하나라도 있는지
    grounded = False
    for ks in key_sentences:
        body = re.sub(r"[.!?。]", "", ks).strip()
        if not body:
            continue
        chunks = [body[i:i + 8] for i in range(0, max(1, len(body) - 7), 4)]
        if any(c in draft.script for c in chunks if len(c) >= 6):
            grounded = True
            break
    if key_sentences and not grounded:
        flags.append(QualityFlag("source_grounding_weak", "script", "", "원본 핵심 문장이 대본에 반영되지 않았습니다.", "warn"))

    draft.quality_flags = flags
    return draft


def severity_summary(flags: list[QualityFlag]) -> dict[str, int]:
    out = {"info": 0, "warn": 0, "block": 0}
    for f in flags:
        out[f.severity] = out.get(f.severity, 0) + 1
    return out
