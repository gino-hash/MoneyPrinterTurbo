# -*- coding: utf-8 -*-
"""Ecozin 명령줄 도구. 웹 화면 없이 한 번에: 프로젝트 생성 → 초안 생성 → 각도 선택·승인 → 렌더링.

사용 예 (프로젝트 루트에서):
  python -m app.ecozin.cli run --spec docs/ecozin/examples/wtg47.json --photos C:\\photos\\wtg47 --angle proof --kind final
  python -m app.ecozin.cli drafts --spec docs/ecozin/examples/wtg47.json     # 초안 3세트만 출력

spec JSON 키: name, audience_mode(end_customer|partner), target_audience, goal_cta, tone,
              source_text, source_notes(이미지 메모 줄바꿈 구분), banned_phrases, required_phrases
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.ecozin import assets as asset_store  # noqa: E402
from app.ecozin import bridge, db  # noqa: E402
from app.ecozin.generators import generate_drafts  # noqa: E402
from app.ecozin.models import STATUS_APPROVED, STATUS_SCENES_LOCKED, Event, Project, SourceAsset  # noqa: E402

_IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov")


def _load_spec(path: str) -> Project:
    with open(path, "r", encoding="utf-8") as f:
        spec = json.load(f)
    project = Project.from_form(spec)
    errors = project.validate()
    if errors:
        raise SystemExit("spec 오류: " + "; ".join(errors.values()))
    return project


def _import_photos(project: Project, folder: str) -> int:
    if not folder:
        return 0
    if not os.path.isdir(folder):
        raise SystemExit(f"사진 폴더가 없습니다: {folder}")
    dest = db.assets_dir(project.id)
    n = 0
    for name in sorted(os.listdir(folder)):
        if not name.lower().endswith(_IMAGE_EXT):
            continue
        with open(os.path.join(folder, name), "rb") as f:
            path = asset_store.save_upload(dest, name, f.read())
        db.save_asset(SourceAsset(project_id=project.id, type="image", path_or_content=path, note=""))
        n += 1
    return n


def _print_draft(d) -> None:
    print(f"\n=== [{d.angle}] ({d.angle_key}) {len(d.script)}자")
    print("훅:", d.hook)
    print("제목:", d.title, "| 썸네일:", d.thumbnail_copy)
    print("대본:")
    for line in d.script.split("\n"):
        print("  ", line)
    print("장면:")
    for s in d.scene_plan:
        print("  ", s.as_line())
    if d.quality_flags:
        print("품질:", "; ".join(f"[{f.severity}] {f.message}" for f in d.quality_flags))


def cmd_drafts(args) -> int:
    project = _load_spec(args.spec)
    db.save_project(project)
    n = _import_photos(project, args.photos)
    print(f"프로젝트 저장: {project.name} (사진 {n}장)")
    drafts = generate_drafts(project, assets=db.list_assets(project.id))
    for d in drafts:
        _print_draft(d)
    print("\n프로젝트 ID:", project.id)
    return 0


def cmd_run(args) -> int:
    from app.services import task as tm  # 무거운 의존성은 지연 import

    project = _load_spec(args.spec)
    db.save_project(project)
    db.log_event(Event(project_id=project.id, event_type="project.created", payload={"name": project.name, "via": "cli"}))
    n = _import_photos(project, args.photos)
    if n == 0:
        raise SystemExit("사진이 한 장도 없습니다. --photos 폴더에 jpg/png 를 넣어주세요. 스톡·AI 소재는 쓰지 않습니다.")
    print(f"프로젝트 저장: {project.name} (사진 {n}장)")

    assets = db.list_assets(project.id)
    drafts = generate_drafts(project, assets=assets)
    chosen = next((d for d in drafts if d.angle_key == args.angle), None)
    if not chosen:
        raise SystemExit(f"각도 '{args.angle}' 초안이 없습니다. 생성된 각도: {[d.angle_key for d in drafts]}")
    _print_draft(chosen)

    # 사람 검수 관문을 CLI 에서는 명시적 플래그로 대신한다
    db.update_draft_status(chosen.id, STATUS_SCENES_LOCKED if args.kind == "final" else STATUS_APPROVED)
    params = bridge.build_video_params(chosen, project, assets, args.kind)
    for w in params.__dict__.get("_ecozin_warnings", []):
        print("경고:", w)
    if args.voice:
        params.voice_name = args.voice

    task_id = str(uuid.uuid4())
    db.set_render_task(chosen.id, args.kind, task_id)
    print(f"\n렌더링 시작 ({args.kind}), 음성 {params.voice_name}, 폰트 {params.font_name}, 작업 {task_id[:8]} ...")
    t0 = time.time()
    result = tm.start(task_id, params, stop_at="video")
    elapsed = round(time.time() - t0)
    videos = (result or {}).get("videos") or []
    if videos:
        db.log_event(Event(project_id=project.id, draft_id=chosen.id, event_type=f"render.{args.kind}.done",
                           payload={"task_id": task_id, "videos": videos, "via": "cli"}))
        print(f"\n완료 ({elapsed}초). 결과 영상:")
        for v in videos:
            print("  ", os.path.abspath(v))
        return 0
    print(f"\n실패 ({elapsed}초): {(result or {}).get('error') or result}")
    return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.ecozin.cli", description="Ecozin 기획 워크벤치 CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("drafts", help="초안 3세트만 생성해 출력")
    p1.add_argument("--spec", required=True)
    p1.add_argument("--photos", default="")
    p1.set_defaults(func=cmd_drafts)
    p2 = sub.add_parser("run", help="생성 → 승인 → 렌더링까지 한 번에")
    p2.add_argument("--spec", required=True)
    p2.add_argument("--photos", required=True, help="실사 사진 폴더")
    p2.add_argument("--angle", default="proof", help="problem | before_after | proof | mistake")
    p2.add_argument("--kind", default="final", choices=["preview", "final"])
    p2.add_argument("--voice", default="", help="예: ko-KR-InJoonNeural-Male")
    p2.set_defaults(func=cmd_run)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
