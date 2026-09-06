"""규칙 기반 초안 생성기. 입력 + 템플릿(시청자 유형별) 조합으로 서로 다른 angle 3세트를 만든다.

LLM 없이 동작한다. 문장은 템플릿 패턴 + 원본 핵심 문장 조합이며, 사람이 검수·수정하는 것을 전제로 한다.
"""

from __future__ import annotations

import re
from typing import Any

from app.ecozin.generators.source_analyzer import Analysis, classify_asset_visual, pain_field, pain_text
from app.ecozin.models import Draft, Project, Scene

_N = "3"


def _fill(pattern: str, values: dict[str, str]) -> str:
    def rep(m):
        key = m.group(1)
        return values.get(key, "")
    text = re.sub(r"\{(\w+)\}", rep, pattern)
    text = re.sub(r"\s+([,，.])", r"\1", text)      # "전 , 후 ." 같은 빈 자리 흔적 정리
    text = re.sub(r"([,，.]){2,}", r"\1", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    text = re.sub(r"^[,，.]\s*", "", text)
    return text


def _pattern_ok(pattern: str, values: dict[str, str]) -> bool:
    """패턴의 자리표시자가 모두 채워질 수 있는지."""
    for key in re.findall(r"\{(\w+)\}", pattern):
        if not values.get(key):
            return False
    return True


def _pick_pattern(patterns: list[str], values: dict[str, str]) -> str:
    for p in patterns:
        if _pattern_ok(p, values):
            return _fill(p, values)
    # 모두 못 채우면 자리표시자를 비우고 첫 패턴 사용
    return _fill(patterns[0], values)


def _values(project: Project, audience: dict[str, Any], analysis: Analysis, template: dict[str, Any]) -> dict[str, str]:
    pains = audience.get("pain_points") or []
    pain = analysis.pain_hits[0] if analysis.pain_hits else (pains[0] if pains else "")
    pain_txt = pain_text(pain).rstrip(".") if pain else ""
    pain_short = pain_field(pain, "short") if pain else ""
    pain_q = pain_field(pain, "question") if pain else ""
    cause = analysis.cause_term or (template["vocabulary"].get("cause_terms") or ["역률"])[0]
    term = analysis.terms_found[0] if analysis.terms_found else (template["vocabulary"]["domain_terms"][0])
    wrong = (audience.get("wrong_focus") or ["고지서"])[0]
    audience_default = (audience.get("audience_defaults") or [""])[0]
    audience_short = project.target_audience if 0 < len(project.target_audience) <= 20 else audience_default
    return {
        "pain": pain_txt,
        "pain_short": pain_short,
        "pain_q": pain_q,
        "cause": cause,
        "term": term,
        "wrong_focus": wrong,
        "audience": project.target_audience or audience_default,
        "audience_short": audience_short,
        "before": (f"{analysis.metric} {analysis.before}".strip() if analysis.metric else (analysis.before or "")),
        "after": analysis.after or "",
        "site": analysis.site or "",
        "install_time": analysis.install_time or "",
        "n": _N,
        "cta": project.goal_cta,
    }


def _tone_suffix(tone: str) -> dict[str, str]:
    """톤에 따라 문장 끝맺음 어투를 조정한다."""
    if "친근" in tone:
        return {"ask": "보셨어요?", "tell": "예요", "cta_end": "편하게 문의 주세요."}
    if "단호" in tone:
        return {"ask": "보셨습니까?", "tell": "입니다", "cta_end": "지금 문의하십시오."}
    return {"ask": "보셨나요?", "tell": "입니다", "cta_end": "문의 주세요."}


def _key(analysis: Analysis, idx: int, fallback: str = "") -> str:
    if len(analysis.key_sentences) > idx:
        return analysis.key_sentences[idx].strip()
    return fallback


def _build_script(angle: dict[str, Any], mode: str, project: Project, audience: dict[str, Any],
                  analysis: Analysis, template: dict[str, Any], v: dict[str, str]) -> list[str]:
    """4단락(비트) 리스트를 돌려준다. 마지막은 CTA."""
    tone = _tone_suffix(project.tone)
    cta_sentence = template["cta_patterns"].get(project.goal_cta, f"{project.goal_cta}는 프로필 링크로 주세요.")
    k0, k1, k2 = _key(analysis, 0), _key(analysis, 1), _key(analysis, 2)
    outcomes = audience.get("desired_outcomes", [])
    outcome = outcomes[0] if outcomes else "계측으로 확인되는 결과"
    key = angle["key"]

    if key == "problem":
        if mode == "partner":
            p1 = f"{v['pain_q']}, 전기공사 하시는 분들이 절감기를 안 다루는 이유가 대부분 이겁니다."
            p2 = f"그런데 이 제품은 다릅니다. {k0}"
            p3 = f"{k1 or k2 or outcome + '이(가) 핵심입니다.'} 설치 후 계측 리포트가 나오니 고객 설득도 파트너가 아니라 숫자가 합니다."
        else:
            p1 = f"{v['pain_q']}, {v['wrong_focus']}만 {tone['ask']} 원인은 다른 데 있을 수 있습니다."
            p2 = f"{v['cause']} 문제면 설비를 바꿔도 요금은 안 내려갑니다. {k0}"
            p3 = f"{k1 or outcome + '이(가) 핵심입니다.'} 결과는 계측기로 찍어서 리포트로 드립니다."
    elif key == "before_after":
        if analysis.has_before_after:
            ba = f"설치 전 {v['before']}, 설치 후 {v['after']}."
        else:
            ba = "설치 전과 후를 같은 조건에서 계측했습니다."
        site = f"{v['site']} 현장{tone['tell']}. " if v["site"] else ""
        if mode == "partner":
            p1 = f"{site}{ba} 파트너가 직접 설치한 현장 그대로{tone['tell']}."
            p2 = f"{k0}" + (f" 설치는 {v['install_time']}이면 끝났습니다." if v["install_time"] else "")
            p3 = f"계약은 이 계측 리포트 한 장으로 됩니다. {k1 or '설치 교육과 A/S는 제조사가 직접 합니다.'}"
        else:
            p1 = f"{site}{ba} 계측기 화면 그대로{tone['tell']}."
            p2 = f"{k0}" + (f" 설치는 {v['install_time']}, 생산 중단은 없었습니다." if v["install_time"] else "")
            p3 = f"{k1 or '설치 전후 계측 리포트를 그대로 드립니다.'} 효과는 현장 조건에 따라 다르니 먼저 진단부터 받아보세요."
    elif key == "proof":
        site = v["site"] or "실증 현장"
        if mode == "partner":
            p1 = f"{site} 실증 현장{tone['tell']}. 파트너가 팔기 전에 제조사가 먼저 증명합니다."
            p2 = k0 or "절감 장치를 달기 전에 계측기부터 설치해 설치 전 기준 데이터를 확보합니다."
            p3 = f"{k1 or '기준 데이터를 잡은 뒤 설치하고 같은 계측기로 전후를 비교합니다.'} 이 비교 리포트는 파트너 영업 자료로 그대로 드립니다."
        else:
            p1 = f"{site}, 절감 장치보다 계측기를 먼저 달았습니다."
            p2 = k0 or "설치 전 기준 데이터를 먼저 확보합니다."
            p3 = f"{k1 or '기준 데이터를 잡은 뒤 설치하고, 같은 계측기로 전후를 비교해 계측 리포트로 공개합니다.'} 절감률은 결과가 나온 뒤에 말하겠습니다."
    else:  # mistake
        if mode == "partner":
            p1 = f"절감기 대리점 계약 전에 꼭 확인할 {v['n']}가지{tone['tell']}."
            p2 = "첫째, 설치 전후 계측 리포트를 제조사가 주는지. 둘째, A/S를 누가 책임지는지. 셋째, 설치 시간이 하루를 넘기는지."
            p3 = f"우리 파트너 현장 결과는 이렇습니다. {k0} {k1 or '이 세 가지가 안 되면 팔고 나서 파트너가 다 떠안게 됩니다.'}"
        else:
            p1 = f"전기절감기 고를 때 가장 많이 속는 {v['n']}가지{tone['tell']}."
            p2 = "첫째, '절감 보장'이라는 말. 둘째, 계측 없이 견적부터 내는 곳. 셋째, 우리 설비 조건을 안 묻는 곳."
            p3 = f"저희는 이렇게 합니다. {k0} {k1 or '계측 리포트 없는 절감률은 믿지 마세요.'}"

    # CTA 문장이 이미 요청형이면 어투 꼬리를 덧붙이지 않는다 (중복 방지)
    if any(w in cta_sentence for w in ("주세요", "드립니다", "받습니다", "하십시오", "하세요")):
        p4 = cta_sentence
    else:
        p4 = f"{cta_sentence} {tone['cta_end']}".strip()
    return [p1, p2, p3, p4]


def _trim_script(paragraphs: list[str], min_len: int = 180, max_len: int = 300) -> list[str]:
    """공백 포함 180~300자 범위로 맞춘다. 길면 2·3단락에서 문장 단위로 줄인다."""
    def total(ps):
        return sum(len(p) for p in ps)
    ps = [p.strip() for p in paragraphs]
    guard = 0
    while total(ps) > max_len and guard < 6:
        guard += 1
        for i in (2, 1):
            sents = re.split(r"(?<=[.!?])\s+", ps[i])
            if len(sents) > 1:
                ps[i] = " ".join(sents[:-1])
                break
        else:
            break
    return ps


def _scene_plan(angle: dict[str, Any], template: dict[str, Any], analysis: Analysis,
                paragraphs: list[str], hook: str) -> list[Scene]:
    scenes: list[Scene] = []
    image_assets = [a for a in analysis.assets if a.get("type") == "image"]
    screen_assets = [a for a in image_assets if classify_asset_visual(a) == "screen"]
    photo_assets = [a for a in image_assets if classify_asset_visual(a) == "photo"]
    # 외관·전경 사진은 첫 장면(훅)에 가장 잘 어울리므로 앞으로 보낸다
    photo_assets.sort(key=lambda a: 0 if any(k in f"{a.get('ref','')} {a.get('note','')}" for k in ("외관", "전경", "전체")) else 1)
    used: set[str] = set()

    def take(pool: list[dict[str, Any]]):
        for a in pool:
            if a["ref"] not in used:
                used.add(a["ref"])
                return a
        return None

    role_text = {
        "hook": hook,
        "problem": paragraphs[1] if len(paragraphs) > 1 else "",
        "solution": paragraphs[2] if len(paragraphs) > 2 else "",
        "cta": paragraphs[-1],
    }
    for tpl in template["scene_plan_template"]:
        role = tpl["role"]
        default_visual = tpl.get("default_visual", "screen")
        asset = None
        if role == "hook" and angle.get("hook_visual") == "photo":
            asset = take(photo_assets) or take(screen_assets)
        elif role in ("hook", "cta"):
            asset = take(screen_assets) or take(photo_assets)
        elif role == "solution":
            asset = take(photo_assets) or take(screen_assets)
        elif role == "problem":
            asset = take(screen_assets)
        if asset:
            visual = classify_asset_visual(asset)
            scenes.append(Scene(t=tpl["t"], role=role, text=role_text.get(role, ""),
                                visual_source=visual, asset_ref=asset["ref"], visual_note=asset.get("note", "")))
        else:
            # 실사가 없으면 템플릿 기본값. AI 생성은 사람이 승인해야 실제로 호출된다.
            note = {"hook": "제목 자막 + 계측 화면 또는 현장 컷", "problem": "원리 도해 또는 고지서·계측 화면",
                    "solution": "설치 현장 실사 또는 설치 전후 비교", "cta": "연락 방법 자막 + 로고"}.get(role, "")
            scenes.append(Scene(t=tpl["t"], role=role, text=role_text.get(role, ""),
                                visual_source=default_visual, asset_ref=None, visual_note=note))
    return scenes


def _video_prompt(angle: dict[str, Any], template: dict[str, Any], scenes: list[Scene], project: Project) -> str:
    base = template.get("video_prompt_base", "")
    style = angle.get("video_style", "")
    lines = [f"{base} 스타일: {style}.", "장면 구성:"]
    for s in scenes:
        src = {"photo": "실사 사진 사용", "screen": "화면 캡처 사용", "ai": "AI 생성 컷"}.get(s.visual_source, "")
        ref = f" ({s.asset_ref})" if s.asset_ref else ""
        lines.append(f"- {s.t} [{s.role}] {src}{ref}: {s.visual_note or s.text[:40]}")
    lines.append(f"자막: 대본 그대로, 문장 단위. 톤: {project.tone or '전문적이지만 쉬운 설명'}.")
    lines.append("Keywords: vertical 9:16, factory electrical panel, power meter close-up, realistic, no exaggeration, Korean subtitles.")
    return "\n".join(lines)


def _description(mode: str, project: Project, template: dict[str, Any], paragraphs: list[str], v: dict[str, str]) -> str:
    disclaimers = template.get("required_disclaimers", [])
    tags = template.get("vocabulary", {}).get("hashtags", [])
    if mode == "partner":
        tags = tags[:2] + ["#대리점모집", "#설치파트너", "#전기공사"]
    body1 = paragraphs[0]
    body2 = paragraphs[2] if len(paragraphs) > 2 else ""
    cta = template["cta_patterns"].get(project.goal_cta, "")
    parts = [body1, body2, cta]
    text = " ".join(p for p in parts if p).strip()
    if disclaimers:
        text += "\n" + disclaimers[0]
    if tags:
        text += "\n" + " ".join(tags[:5])
    return text


def generate(project: Project, template: dict[str, Any], audience: dict[str, Any], analysis: Analysis,
             generation: int) -> list[Draft]:
    mode = project.audience_mode
    v = _values(project, audience, analysis, template)
    drafts: list[Draft] = []
    stage_map = template.get("stage_angles") or {}
    wanted = stage_map.get(analysis.stage) or [a["key"] for a in template["angles"][:3]]
    by_key = {a["key"]: a for a in template["angles"]}
    angles = [by_key[k] for k in wanted if k in by_key][:3]
    if len(angles) < 3:
        angles = template["angles"][:3]
    for idx, angle in enumerate(angles):
        key = angle["key"]
        hook = _pick_pattern(audience["hook_patterns"][key], v)
        paragraphs = _trim_script(_build_script(angle, mode, project, audience, analysis, template, v))
        scenes = _scene_plan(angle, template, analysis, paragraphs, hook)
        title = _pick_pattern(angle.get("title_patterns", [hook]), v) or hook[:30]
        thumb = _pick_pattern(angle.get("thumbnail_patterns", [title]), v) or title[:12]
        pinned = audience.get("pinned_comment_patterns", {}).get(
            project.goal_cta, template["cta_patterns"].get(project.goal_cta, ""))
        if mode == "partner" and "파트너" not in pinned and "대리점" not in pinned:
            pinned = "파트너·대리점 문의: " + pinned
        draft = Draft(
            project_id=project.id,
            generation=generation,
            draft_index=idx,
            audience_mode=mode,
            angle=angle["label"],
            angle_key=key,
            hook=hook,
            script="\n".join(paragraphs),
            scene_plan=scenes,
            video_prompt=_video_prompt(angle, template, scenes, project),
            title=title[:40],
            thumbnail_copy=thumb[:24],
            description=_description(mode, project, template, paragraphs, v),
            pinned_comment=pinned,
            cta=project.goal_cta,
            generator="rule",
        )
        drafts.append(draft)
    return drafts
