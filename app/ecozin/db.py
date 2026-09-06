"""SQLite 저장소. MPT의 task 상태 저장소와 분리된 storage/ecozin/ecozin.db 를 쓴다."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterator, Optional

from app.ecozin.models import Draft, Event, Project, SourceAsset, now_iso
from app.utils import utils

_SCHEMA = """
CREATE TABLE IF NOT EXISTS project (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  industry TEXT NOT NULL,
  audience_mode TEXT NOT NULL,
  target_audience TEXT NOT NULL,
  goal_cta TEXT NOT NULL,
  tone TEXT,
  source_text TEXT NOT NULL,
  source_notes TEXT,
  banned_phrases_json TEXT,
  required_phrases_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source_asset (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  type TEXT NOT NULL,
  path_or_content TEXT NOT NULL,
  note TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS template_profile (
  id TEXT PRIMARY KEY,
  industry TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  version INTEGER NOT NULL,
  config_json TEXT NOT NULL,
  loaded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shorts_draft (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  generation INTEGER NOT NULL,
  draft_index INTEGER NOT NULL,
  audience_mode TEXT NOT NULL,
  angle TEXT NOT NULL,
  angle_key TEXT NOT NULL,
  hook TEXT NOT NULL,
  script TEXT NOT NULL,
  scene_plan_json TEXT NOT NULL,
  video_prompt TEXT NOT NULL,
  title TEXT NOT NULL,
  thumbnail_copy TEXT NOT NULL,
  description TEXT NOT NULL,
  pinned_comment TEXT NOT NULL,
  cta TEXT NOT NULL,
  approval_status TEXT NOT NULL,
  quality_flags_json TEXT,
  edited_version_json TEXT,
  generator TEXT NOT NULL,
  render_task_ids_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_draft_project ON shorts_draft(project_id, generation, draft_index);
CREATE TABLE IF NOT EXISTS event_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL,
  draft_id TEXT,
  event_type TEXT NOT NULL,
  payload_json TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_event_created ON event_log(created_at DESC);
"""

_lock = threading.RLock()
_db_path_override: Optional[str] = None


def db_path() -> str:
    if _db_path_override:
        return _db_path_override
    d = utils.storage_dir("ecozin", create=True)
    return os.path.join(d, "ecozin.db")


def use_db_path(path: Optional[str]) -> None:
    """테스트용: DB 파일 경로를 바꾼다. None 이면 기본 경로."""
    global _db_path_override
    _db_path_override = path


def assets_dir(project_id: str) -> str:
    """업로드 자산 폴더. MPT 의 local 소재 보안 규칙상 storage/local_videos 아래에 있어야 렌더링에 쓸 수 있다."""
    d = os.path.join(utils.storage_dir("local_videos", create=True), "ecozin", project_id)
    os.makedirs(d, exist_ok=True)
    return d


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    with _lock:
        conn = sqlite3.connect(db_path(), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(_SCHEMA)


# ---------- project ----------

def save_project(project: Project) -> Project:
    init_db()
    row = project.to_row()
    with connect() as conn:
        conn.execute(
            """INSERT INTO project (id,name,industry,audience_mode,target_audience,goal_cta,tone,
               source_text,source_notes,banned_phrases_json,required_phrases_json,created_at,updated_at)
               VALUES (:id,:name,:industry,:audience_mode,:target_audience,:goal_cta,:tone,
               :source_text,:source_notes,:banned_phrases_json,:required_phrases_json,:created_at,:updated_at)
               ON CONFLICT(id) DO UPDATE SET name=excluded.name, industry=excluded.industry,
               audience_mode=excluded.audience_mode, target_audience=excluded.target_audience,
               goal_cta=excluded.goal_cta, tone=excluded.tone, source_text=excluded.source_text,
               source_notes=excluded.source_notes, banned_phrases_json=excluded.banned_phrases_json,
               required_phrases_json=excluded.required_phrases_json, updated_at=excluded.updated_at""",
            row,
        )
    return project


def get_project(project_id: str) -> Optional[Project]:
    init_db()
    with connect() as conn:
        row = conn.execute("SELECT * FROM project WHERE id=?", (project_id,)).fetchone()
    return Project.from_row(dict(row)) if row else None


def list_projects(limit: int = 200) -> list[dict[str, Any]]:
    """이력 화면용 요약 목록: 초안 수 / 승인 수 포함."""
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """SELECT p.*,
                 (SELECT COUNT(*) FROM shorts_draft d WHERE d.project_id=p.id) AS draft_count,
                 (SELECT COUNT(*) FROM shorts_draft d WHERE d.project_id=p.id AND d.approval_status='approved') AS approved_count,
                 (SELECT COALESCE(MAX(generation),0) FROM shorts_draft d WHERE d.project_id=p.id) AS generations
               FROM project p ORDER BY p.created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["project"] = Project.from_row(d)
        out.append(d)
    return out


def delete_project(project_id: str) -> None:
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM project WHERE id=?", (project_id,))


# ---------- assets ----------

def save_asset(asset: SourceAsset) -> SourceAsset:
    init_db()
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO source_asset (id,project_id,type,path_or_content,note,created_at) VALUES (?,?,?,?,?,?)",
            (asset.id, asset.project_id, asset.type, asset.path_or_content, asset.note, asset.created_at),
        )
    return asset


def list_assets(project_id: str) -> list[SourceAsset]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM source_asset WHERE project_id=? ORDER BY created_at", (project_id,)
        ).fetchall()
    return [SourceAsset(**{k: r[k] for k in r.keys()}) for r in rows]


def delete_assets(project_id: str, asset_type: Optional[str] = None) -> None:
    init_db()
    with connect() as conn:
        if asset_type:
            conn.execute("DELETE FROM source_asset WHERE project_id=? AND type=?", (project_id, asset_type))
        else:
            conn.execute("DELETE FROM source_asset WHERE project_id=?", (project_id,))


# ---------- template snapshot ----------

def save_template_snapshot(industry: str, name: str, version: int, config: dict[str, Any]) -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            """INSERT INTO template_profile (id,industry,name,version,config_json,loaded_at)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(industry) DO UPDATE SET name=excluded.name, version=excluded.version,
               config_json=excluded.config_json, loaded_at=excluded.loaded_at""",
            (f"tpl-{industry}", industry, name, version, json.dumps(config, ensure_ascii=False), now_iso()),
        )


# ---------- drafts ----------

def next_generation(project_id: str) -> int:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(generation),0) AS g FROM shorts_draft WHERE project_id=?", (project_id,)
        ).fetchone()
    return int(row["g"]) + 1


def save_draft(draft: Draft) -> Draft:
    init_db()
    row = draft.to_row()
    cols = ",".join(row.keys())
    placeholders = ",".join(f":{k}" for k in row.keys())
    updates = ",".join(f"{k}=excluded.{k}" for k in row.keys() if k != "id")
    with connect() as conn:
        conn.execute(
            f"INSERT INTO shorts_draft ({cols}) VALUES ({placeholders}) ON CONFLICT(id) DO UPDATE SET {updates}",
            row,
        )
    return draft


def get_draft(draft_id: str) -> Optional[Draft]:
    init_db()
    with connect() as conn:
        row = conn.execute("SELECT * FROM shorts_draft WHERE id=?", (draft_id,)).fetchone()
    return Draft.from_row(dict(row)) if row else None


def list_drafts(project_id: str, generation: Optional[int] = None) -> list[Draft]:
    init_db()
    with connect() as conn:
        if generation is None:
            rows = conn.execute(
                "SELECT * FROM shorts_draft WHERE project_id=? ORDER BY generation DESC, draft_index",
                (project_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM shorts_draft WHERE project_id=? AND generation=? ORDER BY draft_index",
                (project_id, generation),
            ).fetchall()
    return [Draft.from_row(dict(r)) for r in rows]


def update_draft_status(draft_id: str, status: str) -> Optional[Draft]:
    draft = get_draft(draft_id)
    if not draft:
        return None
    previous = draft.approval_status
    draft.approval_status = status
    draft.updated_at = now_iso()
    save_draft(draft)
    log_event(Event(
        project_id=draft.project_id,
        draft_id=draft.id,
        event_type="draft.status_changed",
        payload={"from": previous, "to": status, "angle": draft.angle},
    ))
    return draft


def update_draft_edit(draft_id: str, edited: dict[str, Any]) -> Optional[Draft]:
    draft = get_draft(draft_id)
    if not draft:
        return None
    clean = {k: v for k, v in edited.items() if isinstance(v, str) and v.strip()}
    draft.edited_version = clean or None
    draft.updated_at = now_iso()
    save_draft(draft)
    log_event(Event(
        project_id=draft.project_id,
        draft_id=draft.id,
        event_type="draft.edited",
        payload={"fields": sorted(clean.keys())},
    ))
    return draft


def set_render_task(draft_id: str, kind: str, task_id: str) -> Optional[Draft]:
    draft = get_draft(draft_id)
    if not draft:
        return None
    draft.render_task_ids[kind] = task_id
    draft.updated_at = now_iso()
    save_draft(draft)
    return draft


# ---------- events ----------

def log_event(event: Event) -> Event:
    init_db()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO event_log (project_id,draft_id,event_type,payload_json,created_at) VALUES (?,?,?,?,?)",
            (event.project_id, event.draft_id, event.event_type,
             json.dumps(event.payload, ensure_ascii=False), event.created_at),
        )
        event.id = cur.lastrowid
    return event


def list_events(limit: int = 50, project_id: Optional[str] = None) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        if project_id:
            rows = conn.execute(
                """SELECT e.*, p.name AS project_name FROM event_log e
                   LEFT JOIN project p ON p.id=e.project_id
                   WHERE e.project_id=? ORDER BY e.id DESC LIMIT ?""",
                (project_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT e.*, p.name AS project_name FROM event_log e
                   LEFT JOIN project p ON p.id=e.project_id
                   ORDER BY e.id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["payload"] = json.loads(d.pop("payload_json") or "{}")
        out.append(d)
    return out
