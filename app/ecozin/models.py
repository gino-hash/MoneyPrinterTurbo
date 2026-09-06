"""데이터 모델. DB 행과 생성기 입출력을 같은 형태로 다룬다."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

AUDIENCE_MODES = ("end_customer", "partner")
AUDIENCE_LABELS = {"end_customer": "최종고객", "partner": "파트너 모집"}

# 상태는 CHECK 제약 대신 코드 상수로 관리한다 (2·3단계 확장 대비).
STATUS_DRAFT = "draft"
STATUS_APPROVED = "approved"
STATUS_EDITING = "editing"
STATUS_HOLD = "hold"
STATUS_PREVIEW_GENERATING = "preview_generating"
STATUS_PREVIEW_READY = "preview_ready"
STATUS_SCENES_LOCKED = "scenes_locked"
STATUS_FINAL_GENERATING = "final_generating"
STATUS_FINAL_READY = "final_ready"

STATUS_LABELS = {
    STATUS_DRAFT: "초안",
    STATUS_APPROVED: "승인",
    STATUS_EDITING: "수정중",
    STATUS_HOLD: "보류",
    STATUS_PREVIEW_GENERATING: "프리뷰 생성중",
    STATUS_PREVIEW_READY: "프리뷰 완료",
    STATUS_SCENES_LOCKED: "장면 확정",
    STATUS_FINAL_GENERATING: "최종 생성중",
    STATUS_FINAL_READY: "최종 완료",
}

REQUIRED_DRAFT_FIELDS = (
    "angle",
    "hook",
    "script",
    "scene_plan",
    "video_prompt",
    "title",
    "thumbnail_copy",
    "description",
    "pinned_comment",
    "cta",
)

VISUAL_SOURCES = ("photo", "screen", "ai")
VISUAL_SOURCE_LABELS = {"photo": "실사 사진", "screen": "화면 캡처", "ai": "AI 생성"}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id() -> str:
    return str(uuid4())


def _split_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value)
    parts = [p.strip() for p in text.replace("\n", ",").split(",")]
    return [p for p in parts if p]


@dataclass
class Project:
    name: str
    industry: str
    audience_mode: str
    target_audience: str
    goal_cta: str
    tone: str
    source_text: str
    source_notes: str = ""
    banned_phrases: list[str] = field(default_factory=list)
    required_phrases: list[str] = field(default_factory=list)
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    @classmethod
    def from_form(cls, data: dict[str, Any]) -> "Project":
        return cls(
            name=str(data.get("name", "")).strip(),
            industry=str(data.get("industry", "")).strip(),
            audience_mode=str(data.get("audience_mode", "end_customer")).strip(),
            target_audience=str(data.get("target_audience", "")).strip(),
            goal_cta=str(data.get("goal_cta", "")).strip(),
            tone=str(data.get("tone", "")).strip(),
            source_text=str(data.get("source_text", "")).strip(),
            source_notes=str(data.get("source_notes", "")).strip(),
            banned_phrases=_split_list(data.get("banned_phrases")),
            required_phrases=_split_list(data.get("required_phrases")),
        )

    def validate(self) -> dict[str, str]:
        errors: dict[str, str] = {}
        if not self.name:
            errors["name"] = "프로젝트명은 필수입니다."
        if not self.industry:
            errors["industry"] = "업종을 선택하세요."
        if self.audience_mode not in AUDIENCE_MODES:
            errors["audience_mode"] = "시청자 유형은 최종고객 또는 파트너 모집이어야 합니다."
        if not self.target_audience:
            errors["target_audience"] = "타깃 고객은 필수입니다."
        if not self.goal_cta:
            errors["goal_cta"] = "목표 CTA는 필수입니다."
        if len(self.source_text) < 30:
            errors["source_text"] = "원본 텍스트는 30자 이상 입력하세요."
        return errors

    def to_row(self) -> dict[str, Any]:
        d = asdict(self)
        d["banned_phrases_json"] = json.dumps(d.pop("banned_phrases"), ensure_ascii=False)
        d["required_phrases_json"] = json.dumps(d.pop("required_phrases"), ensure_ascii=False)
        return d

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Project":
        return cls(
            id=row["id"],
            name=row["name"],
            industry=row["industry"],
            audience_mode=row["audience_mode"],
            target_audience=row["target_audience"],
            goal_cta=row["goal_cta"],
            tone=row["tone"] or "",
            source_text=row["source_text"],
            source_notes=row["source_notes"] or "",
            banned_phrases=json.loads(row["banned_phrases_json"] or "[]"),
            required_phrases=json.loads(row["required_phrases_json"] or "[]"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class SourceAsset:
    project_id: str
    type: str  # text | image | note
    path_or_content: str
    note: str = ""
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=now_iso)

    @property
    def is_file(self) -> bool:
        return self.type == "image" and bool(self.path_or_content)


@dataclass
class Scene:
    t: str
    role: str  # hook | problem | solution | cta
    text: str
    visual_source: str = "screen"  # photo | screen | ai
    asset_ref: Optional[str] = None
    visual_note: str = ""

    def as_line(self) -> str:
        tag = VISUAL_SOURCE_LABELS.get(self.visual_source, self.visual_source)
        ref = f" (자료: {self.asset_ref})" if self.asset_ref else ""
        return f"{self.t}: {self.text} [{tag}{ref}]"


@dataclass
class QualityFlag:
    type: str
    field: str
    match: str
    message: str
    severity: str = "warn"  # info | warn | block


@dataclass
class Draft:
    project_id: str
    generation: int
    draft_index: int
    audience_mode: str
    angle: str
    angle_key: str
    hook: str
    script: str
    scene_plan: list[Scene]
    video_prompt: str
    title: str
    thumbnail_copy: str
    description: str
    pinned_comment: str
    cta: str
    approval_status: str = STATUS_DRAFT
    quality_flags: list[QualityFlag] = field(default_factory=list)
    edited_version: Optional[dict[str, Any]] = None
    generator: str = "rule"
    render_task_ids: dict[str, str] = field(default_factory=dict)
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def missing_fields(self) -> list[str]:
        missing = []
        for name in REQUIRED_DRAFT_FIELDS:
            value = getattr(self, name)
            if value is None or (isinstance(value, (str, list)) and len(value) == 0):
                missing.append(name)
        return missing

    def effective(self) -> dict[str, Any]:
        """카드에 표시·복사할 값. 편집본이 있으면 편집본 우선."""
        base = self.to_package()
        if self.edited_version:
            for k, v in self.edited_version.items():
                if v not in (None, ""):
                    base[k] = v
        return base

    def to_package(self) -> dict[str, Any]:
        return {
            "angle": self.angle,
            "hook": self.hook,
            "script": self.script,
            "scene_plan": [s.as_line() for s in self.scene_plan],
            "video_prompt": self.video_prompt,
            "title": self.title,
            "thumbnail_copy": self.thumbnail_copy,
            "description": self.description,
            "pinned_comment": self.pinned_comment,
            "cta": self.cta,
        }

    def to_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "generation": self.generation,
            "draft_index": self.draft_index,
            "audience_mode": self.audience_mode,
            "angle": self.angle,
            "angle_key": self.angle_key,
            "hook": self.hook,
            "script": self.script,
            "scene_plan_json": json.dumps([asdict(s) for s in self.scene_plan], ensure_ascii=False),
            "video_prompt": self.video_prompt,
            "title": self.title,
            "thumbnail_copy": self.thumbnail_copy,
            "description": self.description,
            "pinned_comment": self.pinned_comment,
            "cta": self.cta,
            "approval_status": self.approval_status,
            "quality_flags_json": json.dumps([asdict(f) for f in self.quality_flags], ensure_ascii=False),
            "edited_version_json": json.dumps(self.edited_version, ensure_ascii=False) if self.edited_version else None,
            "generator": self.generator,
            "render_task_ids_json": json.dumps(self.render_task_ids, ensure_ascii=False),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Draft":
        scenes = [Scene(**s) for s in json.loads(row["scene_plan_json"] or "[]")]
        flags = [QualityFlag(**f) for f in json.loads(row["quality_flags_json"] or "[]")]
        edited = json.loads(row["edited_version_json"]) if row.get("edited_version_json") else None
        return cls(
            id=row["id"],
            project_id=row["project_id"],
            generation=row["generation"],
            draft_index=row["draft_index"],
            audience_mode=row["audience_mode"],
            angle=row["angle"],
            angle_key=row["angle_key"],
            hook=row["hook"],
            script=row["script"],
            scene_plan=scenes,
            video_prompt=row["video_prompt"],
            title=row["title"],
            thumbnail_copy=row["thumbnail_copy"],
            description=row["description"],
            pinned_comment=row["pinned_comment"],
            cta=row["cta"],
            approval_status=row["approval_status"],
            quality_flags=flags,
            edited_version=edited,
            generator=row["generator"],
            render_task_ids=json.loads(row.get("render_task_ids_json") or "{}"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class Event:
    project_id: str
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    draft_id: Optional[str] = None
    created_at: str = field(default_factory=now_iso)
    id: Optional[int] = None
