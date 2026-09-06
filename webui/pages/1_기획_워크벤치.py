# -*- coding: utf-8 -*-
"""Ecozin 기획 워크벤치 — Streamlit 멀티페이지 (webui/Main.py 옆의 pages/ 로 자동 등록).

화면 1: 새 프로젝트 / 화면 2: 결과 패널 / 화면 3: 이력
원본(MoneyPrinterTurbo) 코드는 수정하지 않는다.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import streamlit as st

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
if root_dir in sys.path:
    sys.path.remove(root_dir)
sys.path.insert(0, root_dir)

from app.ecozin import bridge, db, template_loader  # noqa: E402
from app.ecozin.generators import DraftValidationError, generate_drafts  # noqa: E402
from app.ecozin.generators.quality_checker import severity_summary  # noqa: E402
from app.ecozin.models import (  # noqa: E402
    AUDIENCE_LABELS,
    AUDIENCE_MODES,
    STATUS_APPROVED,
    STATUS_DRAFT,
    STATUS_EDITING,
    STATUS_FINAL_READY,
    STATUS_HOLD,
    STATUS_LABELS,
    STATUS_PREVIEW_READY,
    STATUS_SCENES_LOCKED,
    Event,
    Project,
    SourceAsset,
)

st.set_page_config(page_title="기획 워크벤치 · Ecozin", page_icon="🎬", layout="wide")

TONES = ["전문적이지만 쉬운 설명", "친근한", "단호한", "차분한"]
FIELD_LABELS = [
    ("hook", "훅 (첫 3초)"), ("script", "대본"), ("scene_plan", "장면 계획"), ("video_prompt", "영상 생성 프롬프트"),
    ("title", "제목"), ("thumbnail_copy", "썸네일 문구"), ("description", "설명글"), ("pinned_comment", "고정 댓글"), ("cta", "CTA"),
]
SEVERITY_ICON = {"info": "ℹ️", "warn": "⚠️", "block": "⛔"}


def _ss(key: str, default: Any = None) -> Any:
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]


def _copy_button(label: str, text: str, key: str) -> None:
    """클립보드 복사는 브라우저 제약이 있어 st.code 의 내장 복사 아이콘을 쓴다."""
    with st.expander(label, expanded=False):
        st.code(text, language=None)


# ---------------------------------------------------------------- 화면 1

def render_new_project() -> None:
    st.subheader("1. 새 프로젝트")
    industries = template_loader.list_industries()
    ind_keys = [k for k, _ in industries]
    ind_labels = {k: n for k, n in industries}

    c1, c2 = st.columns([2, 1])
    with c1:
        name = st.text_input("프로젝트명 *", placeholder="예) A공장 설치 사례 쇼츠")
    with c2:
        industry = st.selectbox("업종 *", ind_keys, format_func=lambda k: ind_labels[k])
    template = template_loader.get_template(industry)

    mode = st.radio("시청자 유형 *", AUDIENCE_MODES, format_func=lambda m: AUDIENCE_LABELS[m], horizontal=True,
                    help="같은 원본이라도 유형에 따라 통점·훅·CTA가 달라집니다.")
    aud = template_loader.audience_section(template, mode)
    c3, c4, c5 = st.columns(3)
    with c3:
        target = st.selectbox("타깃 고객 *", aud["audience_defaults"] + ["직접 입력"], key=f"target_{mode}")
        if target == "직접 입력":
            target = st.text_input("타깃 고객 직접 입력", key=f"target_custom_{mode}")
    with c4:
        ctas = template_loader.default_ctas(template, mode) + ["직접 입력"]
        goal_cta = st.selectbox("목표 CTA *", ctas, key=f"cta_{mode}")
        if goal_cta == "직접 입력":
            goal_cta = st.text_input("CTA 직접 입력", key=f"cta_custom_{mode}")
    with c5:
        tone = st.selectbox("톤", TONES)

    source_text = st.text_area(
        "원본 텍스트 * (30자 이상)", height=160,
        placeholder="예) 경기도 A공장 설치 전후 계측. 역률 0.82에서 0.96으로 개선, 기본요금 가산 해소. 3개월 평균 약 8% 절감 확인. 설치 2시간, 생산라인 중단 없음. 설치 전후 계측 리포트 제공.",
        help="설치 사례, 계측 데이터, 기술 원리, 자주 받는 질문 등 사실 위주로. 이 텍스트가 대본의 재료가 됩니다.",
    )
    c6, c7 = st.columns(2)
    with c6:
        source_notes = st.text_area(
            "이미지 메모 (한 줄에 하나: 파일명 (설명))", height=100,
            placeholder="before_after_meter.jpg (계측기 화면 비교)\ninstall_site.jpg (배전반 설치 현장)",
            help="아래에서 같은 이름의 파일을 올리면 장면에 자동 배치되고 렌더링에 그대로 쓰입니다.",
        )
    with c7:
        uploads = st.file_uploader("실사 사진·화면 캡처 업로드 (jpg/png/mp4)", type=["jpg", "jpeg", "png", "webp", "mp4", "mov"],
                                   accept_multiple_files=True)
    c8, c9 = st.columns(2)
    with c8:
        banned = st.text_input("금지어 (쉼표 구분)", placeholder="반값, 무조건")
    with c9:
        required = st.text_input("필수어 (쉼표 구분)", placeholder="계측 리포트")

    b1, b2 = st.columns([1, 1])
    save_only = b1.button("저장", use_container_width=True)
    save_gen = b2.button("저장 후 초안 3세트 생성", type="primary", use_container_width=True)
    if not (save_only or save_gen):
        return

    project = Project.from_form({
        "name": name, "industry": industry, "audience_mode": mode, "target_audience": target, "goal_cta": goal_cta,
        "tone": tone, "source_text": source_text, "source_notes": source_notes,
        "banned_phrases": banned, "required_phrases": required,
    })
    errors = project.validate()
    if errors:
        for msg in errors.values():
            st.error(msg)
        return
    db.save_project(project)
    db.log_event(Event(project_id=project.id, event_type="project.created",
                       payload={"name": project.name, "audience_mode": mode, "goal_cta": goal_cta}))
    # 자산 저장: 업로드 파일 + 메모 줄
    asset_dir = db.assets_dir(project.id)
    saved_files = []
    for up in uploads or []:
        path = os.path.join(asset_dir, os.path.basename(up.name))
        with open(path, "wb") as f:
            f.write(up.getbuffer())
        saved_files.append(path)
        db.save_asset(SourceAsset(project_id=project.id, type="image", path_or_content=path, note=""))
    db.save_asset(SourceAsset(project_id=project.id, type="text", path_or_content=project.source_text, note="원본 텍스트"))
    for line in project.source_notes.splitlines():
        if line.strip():
            db.save_asset(SourceAsset(project_id=project.id, type="note", path_or_content=line.strip(), note="이미지 메모"))
    st.success(f"프로젝트 저장 완료 (자료 파일 {len(saved_files)}개)")
    st.session_state["ecozin_project_id"] = project.id

    if save_gen:
        _generate(project)
        st.session_state["ecozin_tab"] = "결과 패널"
        st.rerun()


def _generate(project: Project) -> None:
    try:
        assets = db.list_assets(project.id)
        drafts = generate_drafts(project, assets=assets)
        st.success(f"초안 {len(drafts)}세트 생성 완료 (세대 {drafts[0].generation})")
    except DraftValidationError as exc:
        st.error(f"초안 검증 실패: {exc}")
    except Exception as exc:  # noqa: BLE001
        st.exception(exc)


# ---------------------------------------------------------------- 화면 2

def _status_badge(status: str) -> str:
    color = {STATUS_APPROVED: "green", STATUS_HOLD: "gray", STATUS_EDITING: "orange", STATUS_DRAFT: "blue"}.get(status, "violet")
    return f":{color}[{STATUS_LABELS.get(status, status)}]"


def render_results() -> None:
    st.subheader("2. 결과 패널")
    projects = db.list_projects()
    if not projects:
        st.info("아직 프로젝트가 없습니다. '새 프로젝트' 탭에서 만들어 주세요.")
        return
    ids = [p["id"] for p in projects]
    labels = {p["id"]: f"{p['name']} · {AUDIENCE_LABELS.get(p['audience_mode'], '')} · {p['goal_cta']} · {p['created_at'][:10]}" for p in projects}
    default = st.session_state.get("ecozin_project_id") or ids[0]
    pid = st.selectbox("프로젝트", ids, index=ids.index(default) if default in ids else 0, format_func=lambda i: labels[i])
    st.session_state["ecozin_project_id"] = pid
    project = db.get_project(pid)
    assets = db.list_assets(pid)
    files = [a for a in assets if a.type == "image"]

    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.markdown(f"**업종** {template_loader.get_template(project.industry)['name']}")
        c2.markdown(f"**시청자** {AUDIENCE_LABELS.get(project.audience_mode)}")
        c3.markdown(f"**타깃** {project.target_audience}")
        c4.markdown(f"**CTA** {project.goal_cta}")
        c5.markdown(f"**실사 자료** {len(files)}개")
        with st.expander("원본 텍스트 보기"):
            st.write(project.source_text)
            if project.source_notes:
                st.caption("이미지 메모"); st.text(project.source_notes)
        if st.button("다시 생성 (새 세대 추가)", key="regen"):
            _generate(project)
            st.rerun()

    drafts_all = db.list_drafts(pid)
    if not drafts_all:
        st.warning("초안이 없습니다. '다시 생성'을 누르세요.")
        return
    gens = sorted({d.generation for d in drafts_all}, reverse=True)
    gen = st.selectbox("세대", gens, format_func=lambda g: f"{g}세대", key=f"gen_{pid}")
    drafts = [d for d in drafts_all if d.generation == gen]

    # 렌더링 중인 초안의 상태를 동기화
    for d in drafts:
        if d.approval_status.endswith("_generating"):
            bridge.sync_render_result(d.id)
    drafts = db.list_drafts(pid, gen)

    cols = st.columns(len(drafts))
    for col, d in zip(cols, drafts):
        with col:
            _render_card(d, project)


def _render_card(d, project: Project) -> None:
    pkg = d.effective()
    with st.container(border=True):
        st.markdown(f"### {d.angle}  {_status_badge(d.approval_status)}")
        sev = severity_summary(d.quality_flags)
        if d.quality_flags:
            with st.expander(f"품질 검사 ⚠️{sev['warn']} ⛔{sev['block']} ℹ️{sev['info']}", expanded=sev["block"] > 0):
                for f in d.quality_flags:
                    st.write(f"{SEVERITY_ICON.get(f.severity, '')} **{f.field}** · {f.message}")
        else:
            st.caption("품질 검사: 경고 없음")

        st.markdown("**훅**"); st.info(pkg["hook"])
        st.markdown("**대본**"); st.code(pkg["script"], language=None)
        st.markdown("**장면 계획**")
        for s in d.scene_plan:
            st.write(f"- {s.as_line()}")
        for key, label in FIELD_LABELS:
            if key in ("hook", "script", "scene_plan"):
                continue
            value = pkg[key]
            _copy_button(label, value if isinstance(value, str) else "\n".join(value), key=f"{d.id}_{key}")
        with st.expander("전체 JSON 복사"):
            st.code(json.dumps(pkg, ensure_ascii=False, indent=2), language="json")

        st.markdown("**검수 상태**")
        b1, b2, b3 = st.columns(3)
        if b1.button("승인", key=f"ap_{d.id}", type="primary", use_container_width=True):
            db.update_draft_status(d.id, STATUS_APPROVED); st.toast("승인 저장"); st.rerun()
        if b2.button("수정중", key=f"ed_{d.id}", use_container_width=True):
            db.update_draft_status(d.id, STATUS_EDITING); st.toast("수정중 저장"); st.rerun()
        if b3.button("보류", key=f"ho_{d.id}", use_container_width=True):
            db.update_draft_status(d.id, STATUS_HOLD); st.toast("보류 저장"); st.rerun()

        with st.expander("문구 직접 수정 (원본은 보존됩니다)"):
            edited = {}
            for key in ("hook", "script", "title", "thumbnail_copy", "description", "pinned_comment"):
                edited[key] = st.text_area(key, value=pkg[key], key=f"edit_{d.id}_{key}", height=80 if key != "script" else 160)
            if st.button("수정본 저장", key=f"save_edit_{d.id}"):
                db.update_draft_edit(d.id, edited)
                if d.approval_status == STATUS_DRAFT:
                    db.update_draft_status(d.id, STATUS_EDITING)
                st.toast("수정본 저장"); st.rerun()

        _render_render_controls(d)


def _render_render_controls(d) -> None:
    st.markdown("**렌더링 (MoneyPrinterTurbo)**")
    status = d.approval_status
    r1, r2 = st.columns(2)
    can_preview = status in (STATUS_APPROVED, STATUS_PREVIEW_READY, STATUS_SCENES_LOCKED, STATUS_FINAL_READY)
    can_lock = status == STATUS_PREVIEW_READY
    can_final = status in (STATUS_SCENES_LOCKED, STATUS_FINAL_READY)
    if r1.button("프리뷰 생성", key=f"pv_{d.id}", disabled=not can_preview, use_container_width=True,
                 help="승인된 초안만. 실사 자료 + 무료 한국어 음성으로 렌더링합니다."):
        try:
            task_id, warnings = bridge.submit_render(d.id, "preview")
            for w in warnings:
                st.warning(w)
            st.toast(f"프리뷰 작업 제출: {task_id[:8]}"); st.rerun()
        except bridge.BridgeError as exc:
            st.error(str(exc))
    if r2.button("최종 생성", key=f"fn_{d.id}", disabled=not can_final, use_container_width=True,
                 help="프리뷰를 확인하고 장면을 확정한 뒤에만 가능합니다."):
        try:
            task_id, warnings = bridge.submit_render(d.id, "final")
            for w in warnings:
                st.warning(w)
            st.toast(f"최종 작업 제출: {task_id[:8]}"); st.rerun()
        except bridge.BridgeError as exc:
            st.error(str(exc))
    if can_lock and st.button("프리뷰 확인 완료 → 장면 확정", key=f"lock_{d.id}", use_container_width=True):
        db.update_draft_status(d.id, STATUS_SCENES_LOCKED); st.rerun()

    for kind in ("preview", "final"):
        task_id = d.render_task_ids.get(kind)
        if not task_id:
            continue
        st_ = bridge.render_status(task_id)
        if not st_:
            st.caption(f"{kind}: 작업 {task_id[:8]} 상태를 찾을 수 없음 (서버 재시작됨)")
            continue
        st.caption(f"{kind}: {st_['label']} {st_['progress']}%")
        if st_["error"]:
            st.error(f"{kind} 실패 ({st_['failed_stage']}): {st_['error']}")
        for v in st_["videos"]:
            if os.path.isfile(v):
                st.video(v)
                st.caption(v)
    if status.endswith("_generating"):
        if st.button("상태 새로고침", key=f"rf_{d.id}"):
            bridge.sync_render_result(d.id); st.rerun()


# ---------------------------------------------------------------- 화면 3

def render_history() -> None:
    st.subheader("3. 이력")
    rows = db.list_projects()
    if rows:
        table = [{
            "생성일": r["created_at"][:16].replace("T", " "), "프로젝트": r["name"],
            "시청자": AUDIENCE_LABELS.get(r["audience_mode"], r["audience_mode"]), "CTA": r["goal_cta"],
            "세대": r["generations"], "초안": r["draft_count"], "승인": r["approved_count"], "id": r["id"],
        } for r in rows]
        st.dataframe(table, use_container_width=True, hide_index=True, column_config={"id": None})
        pick = st.selectbox("결과 패널로 열기", [r["id"] for r in rows], format_func=lambda i: next(r["name"] for r in rows if r["id"] == i))
        if st.button("열기"):
            st.session_state["ecozin_project_id"] = pick
            st.session_state["ecozin_tab"] = "결과 패널"
            st.rerun()
    else:
        st.info("프로젝트가 없습니다.")

    st.markdown("**최근 이벤트 50건**")
    events = db.list_events(50)
    if events:
        st.dataframe([{
            "시각": e["created_at"][:19].replace("T", " "), "프로젝트": e.get("project_name") or e["project_id"][:8],
            "이벤트": e["event_type"], "내용": json.dumps(e["payload"], ensure_ascii=False)[:120],
        } for e in events], use_container_width=True, hide_index=True)


# ---------------------------------------------------------------- 진입점

def main() -> None:
    st.title("🎬 기획 워크벤치")
    st.caption("원본 자료 → 초안 3세트 → 사람 검수 → 프리뷰 → 장면 확정 → 최종 생성. 자동 업로드는 하지 않습니다.")
    try:
        db.init_db()
        template_loader.load_all()
    except Exception as exc:  # noqa: BLE001
        st.error(f"초기화 실패: {exc}")
        return
    tabs = ["새 프로젝트", "결과 패널", "이력"]
    current = _ss("ecozin_tab", "새 프로젝트")
    choice = st.radio("화면", tabs, index=tabs.index(current), horizontal=True, label_visibility="collapsed")
    st.session_state["ecozin_tab"] = choice
    if choice == "새 프로젝트":
        render_new_project()
    elif choice == "결과 패널":
        render_results()
    else:
        render_history()


main()
