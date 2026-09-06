"""승인된 초안 → MoneyPrinterTurbo 렌더링 작업.

- 대본은 우리 초안(편집본 우선)을 그대로 넣어 LLM 생성을 건너뛴다.
- 영상 소재는 항상 `local`: 프로젝트에 업로드된 실사 사진·화면 캡처만 쓴다. 스톡·AI 생성은 호출하지 않는다.
- 프리뷰(preview)와 최종(final) 두 종류. 1단계에서는 둘 다 무료 경로(Edge TTS + 로컬 소재)라 비용 차이가 없고,
  최종만 배경음악·전환 효과를 넣는다. 해상도 분리는 MPT 파이프라인이 지원하지 않아 후속 과제로 남긴다.
"""

from __future__ import annotations

import os
import uuid
from typing import Any, Optional

from loguru import logger

from app.config import config
from app.ecozin import db
from app.ecozin.models import (
    STATUS_APPROVED,
    STATUS_FINAL_GENERATING,
    STATUS_FINAL_READY,
    STATUS_PREVIEW_GENERATING,
    STATUS_PREVIEW_READY,
    STATUS_SCENES_LOCKED,
    Draft,
    Event,
    Project,
    SourceAsset,
)
from app.models import const
from app.models.schema import MaterialInfo, VideoAspect, VideoConcatMode, VideoParams, VideoTransitionMode
from app.services import state as sm
from app.utils import utils

DEFAULT_VOICE = "ko-KR-SunHiNeural-Female"
VOICE_CHOICES = ["ko-KR-SunHiNeural-Female", "ko-KR-InJoonNeural-Male", "ko-KR-HyunsuMultilingualNeural-Male"]
KOREAN_FONT_CANDIDATES = ["NanumGothic-ExtraBold.ttf", "NanumGothic-Bold.ttf", "NotoSansKR.ttf", "MicrosoftYaHeiBold.ttc"]
RENDER_KINDS = ("preview", "final")
_ALLOWED_FROM = {
    "preview": {STATUS_APPROVED, STATUS_PREVIEW_READY, STATUS_SCENES_LOCKED, STATUS_FINAL_READY},
    "final": {STATUS_SCENES_LOCKED, STATUS_PREVIEW_READY, STATUS_FINAL_READY},
}


class BridgeError(ValueError):
    pass


def korean_font() -> str:
    fonts = os.listdir(utils.font_dir()) if os.path.isdir(utils.font_dir()) else []
    for name in KOREAN_FONT_CANDIDATES:
        if name in fonts:
            return name
    return fonts[0] if fonts else "STHeitiMedium.ttc"


def voice_name() -> str:
    return str(config.app.get("ecozin_voice_name") or DEFAULT_VOICE)


def _asset_index(assets: list[SourceAsset]) -> dict[str, str]:
    """파일명 → 실제 경로 (존재하는 파일만)."""
    out = {}
    for a in assets:
        if a.type == "image" and a.path_or_content and os.path.isfile(a.path_or_content):
            out[os.path.basename(a.path_or_content)] = a.path_or_content
    return out


def materials_for(draft: Draft, assets: list[SourceAsset]) -> tuple[list[MaterialInfo], list[str]]:
    """장면 순서대로 로컬 소재를 만든다. 장면에 자산이 없으면 남은 파일로 채우고, 빠진 장면은 경고 목록에 담는다."""
    index = _asset_index(assets)
    used: list[str] = []
    warnings: list[str] = []
    for s in draft.scene_plan:
        if s.asset_ref and s.asset_ref in index and s.asset_ref not in used:
            used.append(s.asset_ref)
        else:
            warnings.append(f"{s.t} [{s.role}] 장면에 연결된 실사 자료가 없습니다 ({'AI 생성 예정' if s.visual_source == 'ai' else '자료 없음'}).")
    # 장면에 안 붙은 나머지 파일도 뒤에 붙여 소재가 모자라지 않게 한다
    for name in index:
        if name not in used:
            used.append(name)
    materials = [MaterialInfo(provider="local", url=index[n], duration=0) for n in used]
    return materials, warnings


def build_video_params(draft: Draft, project: Project, assets: list[SourceAsset], kind: str = "preview") -> VideoParams:
    if kind not in RENDER_KINDS:
        raise BridgeError(f"알 수 없는 렌더링 종류: {kind}")
    materials, warnings = materials_for(draft, assets)
    if not materials:
        raise BridgeError("업로드된 실사 사진·화면 캡처가 없습니다. 스톡·AI 소재는 쓰지 않으니 자료를 먼저 올려주세요.")
    pkg = draft.effective()
    script = str(pkg["script"]).strip()
    if not script:
        raise BridgeError("대본이 비어 있습니다.")

    params = VideoParams(
        video_subject=project.name,
        video_script=script,
        video_terms=None,
        video_aspect=VideoAspect.portrait.value,
        video_concat_mode=VideoConcatMode.sequential.value,
        video_transition_mode=VideoTransitionMode.fade_in.value if kind == "final" else None,
        video_clip_duration=5,
        video_count=1,
        video_source="local",
        video_materials=materials,
        video_language="ko-KR",
        voice_name=voice_name(),
        voice_rate=1.0,
        bgm_type="random" if kind == "final" else "",
        bgm_volume=0.15,
        subtitle_enabled=True,
        subtitle_position="bottom",
        font_name=korean_font(),
        font_size=int(config.app.get("ecozin_font_size") or 62),
        text_fore_color="#FFFFFF",
        stroke_color="#000000",
        stroke_width=2.2,
        n_threads=2,
        paragraph_number=1,
    )
    params.__dict__["_ecozin_warnings"] = warnings  # 화면 표시용, 직렬화되지 않음
    return params


def submit_render(draft_id: str, kind: str = "preview") -> tuple[str, list[str]]:
    """렌더링 작업을 제출하고 (task_id, 경고목록) 을 돌려준다. Streamlit 세션 안에서 호출한다."""
    from app.services import webui_task  # Streamlit 의존 모듈은 지연 import

    draft = db.get_draft(draft_id)
    if not draft:
        raise BridgeError("초안을 찾을 수 없습니다.")
    if draft.approval_status not in _ALLOWED_FROM[kind]:
        need = "승인" if kind == "preview" else "프리뷰 확인(장면 확정)"
        raise BridgeError(f"{kind} 렌더링은 {need} 상태에서만 가능합니다. 현재: {draft.approval_status}")
    project = db.get_project(draft.project_id)
    assets = db.list_assets(draft.project_id)
    params = build_video_params(draft, project, assets, kind)
    warnings = list(params.__dict__.get("_ecozin_warnings", []))

    task_id = str(uuid.uuid4())
    webui_task.submit_generation(task_id=task_id, params=params, capture_logs=True)
    db.set_render_task(draft_id, kind, task_id)
    db.update_draft_status(draft_id, STATUS_PREVIEW_GENERATING if kind == "preview" else STATUS_FINAL_GENERATING)
    db.log_event(Event(project_id=draft.project_id, draft_id=draft.id, event_type=f"render.{kind}.submitted",
                       payload={"task_id": task_id, "materials": len(params.video_materials), "warnings": warnings}))
    logger.info(f"ecozin render submitted: draft={draft_id} kind={kind} task={task_id}")
    return task_id, warnings


def render_status(task_id: str) -> Optional[dict[str, Any]]:
    task = sm.state.get_task(task_id)
    if not task:
        return None
    state = task.get("state")
    return {
        "task_id": task_id,
        "state": state,
        "label": {const.TASK_STATE_COMPLETE: "완료", const.TASK_STATE_FAILED: "실패", const.TASK_STATE_PROCESSING: "진행중"}.get(state, str(state)),
        "progress": task.get("progress", 0),
        "videos": task.get("videos") or [],
        "error": task.get("error"),
        "failed_stage": task.get("failed_stage"),
    }


def sync_render_result(draft_id: str) -> Optional[Draft]:
    """작업 상태를 조회해 초안 상태를 preview_ready / final_ready 로 올린다. 실패면 이전 관문 상태로 되돌린다."""
    draft = db.get_draft(draft_id)
    if not draft:
        return None
    for kind, waiting, done, back in (
        ("preview", STATUS_PREVIEW_GENERATING, STATUS_PREVIEW_READY, STATUS_APPROVED),
        ("final", STATUS_FINAL_GENERATING, STATUS_FINAL_READY, STATUS_SCENES_LOCKED),
    ):
        task_id = draft.render_task_ids.get(kind)
        if draft.approval_status != waiting or not task_id:
            continue
        st = render_status(task_id)
        if not st:
            continue
        if st["state"] == const.TASK_STATE_COMPLETE:
            draft = db.update_draft_status(draft_id, done)
            db.log_event(Event(project_id=draft.project_id, draft_id=draft.id, event_type=f"render.{kind}.done",
                               payload={"task_id": task_id, "videos": st["videos"]}))
        elif st["state"] == const.TASK_STATE_FAILED:
            draft = db.update_draft_status(draft_id, back)
            db.log_event(Event(project_id=draft.project_id, draft_id=draft.id, event_type=f"render.{kind}.failed",
                               payload={"task_id": task_id, "error": st.get("error"), "stage": st.get("failed_stage")}))
    return draft
