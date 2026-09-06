# -*- coding: utf-8 -*-
"""Ecozin 기획 워크벤치 테스트. PRD 15장 검증 기준을 그대로 옮겼다."""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.ecozin import bridge, db, template_loader  # noqa: E402
from app.ecozin.generators import DraftValidationError, generate_drafts  # noqa: E402
from app.ecozin.generators.quality_checker import soften  # noqa: E402
from app.ecozin.models import REQUIRED_DRAFT_FIELDS, STATUS_APPROVED, STATUS_HOLD, Project, SourceAsset  # noqa: E402
from app.ecozin.template_loader import TemplateError, validate_template  # noqa: E402

SRC = ("경기도 A공장 설치 전후 계측. 역률 0.82에서 0.96으로 개선, 기본요금 가산 해소. "
       "월 사용량 기준 약 8% 절감 확인(3개월 평균). 설치 2시간, 생산라인 중단 없음. 설치 전후 계측 리포트 제공.")


@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    db.use_db_path(str(tmp_path / "t.db"))
    db.init_db()
    yield
    db.use_db_path(None)


def make_project(mode="end_customer", cta="견적요청", **kw):
    data = {"name": "테스트 쇼츠", "industry": "energy-saving-device", "audience_mode": mode,
            "target_audience": "공장 전기 담당자", "goal_cta": cta, "tone": "전문적이지만 쉬운 설명",
            "source_text": SRC, "source_notes": "before_after_meter.jpg (계측기 화면 비교)\ninstall_site.jpg (배전반 설치 현장)",
            "banned_phrases": "반값", "required_phrases": "계측 리포트"}
    data.update(kw)
    p = Project.from_form(data)
    assert p.validate() == {}
    return db.save_project(p)


# 1·2. 프로젝트 생성/저장, source_text 검증
def test_project_roundtrip_and_validation():
    p = make_project()
    got = db.get_project(p.id)
    assert got.source_text == SRC and got.banned_phrases == ["반값"] and got.audience_mode == "end_customer"
    short = Project.from_form({"name": "x", "industry": "energy-saving-device", "audience_mode": "partner",
                               "target_audience": "y", "goal_cta": "대리점문의", "source_text": "짧다"})
    assert "source_text" in short.validate()


# 3. 템플릿 로드 + 잘못된 템플릿 거부
def test_template_loads_and_rejects_invalid():
    t = template_loader.get_template("energy-saving-device")
    assert {"end_customer", "partner"} <= set(t["audiences"])
    assert len(t["angles"]) >= 3
    bad = dict(t)
    bad["audiences"] = {"end_customer": t["audiences"]["end_customer"]}
    with pytest.raises(TemplateError):
        validate_template(bad, "bad")


# 4·5. 초안 3세트, angle 다름, 필수 10필드
def test_generate_three_drafts_with_all_fields():
    p = make_project()
    drafts = generate_drafts(p)
    assert len(drafts) == 3
    assert len({d.angle_key for d in drafts}) == 3
    for d in drafts:
        assert d.missing_fields() == []
        for f in REQUIRED_DRAFT_FIELDS:
            assert getattr(d, f)
        assert 100 <= len(d.script) <= 220
        assert d.cta == "견적요청"
        assert len(d.scene_plan) == 4
    # 저장·재조회
    again = db.list_drafts(p.id, 1)
    assert [x.angle_key for x in again] == [x.angle_key for x in drafts]
    assert again[0].scene_plan[0].asset_ref == "before_after_meter.jpg"


# 6. 승인/보류 저장 + 이벤트 로그
def test_status_change_persists_and_logs():
    p = make_project()
    d = generate_drafts(p)[0]
    db.update_draft_status(d.id, STATUS_APPROVED)
    assert db.get_draft(d.id).approval_status == STATUS_APPROVED
    db.update_draft_status(d.id, STATUS_HOLD)
    assert db.get_draft(d.id).approval_status == STATUS_HOLD
    types = [e["event_type"] for e in db.list_events(20, p.id)]
    assert types.count("draft.status_changed") == 2 and "draft.generated" in types


# 7. 재조회 (이력)
def test_history_lists_projects_with_counts():
    p = make_project()
    generate_drafts(p)
    db.update_draft_status(db.list_drafts(p.id)[0].id, STATUS_APPROVED)
    rows = db.list_projects()
    assert rows[0]["draft_count"] == 3 and rows[0]["approved_count"] == 1 and rows[0]["generations"] == 1
    generate_drafts(db.get_project(p.id))
    assert db.list_projects()[0]["generations"] == 2


# + 과장어: 대본에 들어가면 완화·경고, 원본에만 있으면 안내
def test_exaggeration_softened_or_flagged():
    from app.ecozin.generators.quality_checker import check_and_fix, unquoted_text
    p = make_project(source_text=SRC + " 무조건 100% 절감 보장합니다.")
    t = template_loader.get_template("energy-saving-device")
    drafts = generate_drafts(p)
    assert all(any(f.type == "source_exaggeration" for f in d.quality_flags) for d in drafts)
    d = drafts[0]
    d.script = d.script + "\n무조건 절감됩니다. 100% 보장합니다."
    check_and_fix(d, p, t, [])
    assert "무조건" not in unquoted_text(d.script)
    assert any(f.type == "exaggeration_softened" for f in d.quality_flags)


def test_soften_keeps_quoted_claims():
    text, replaced = soften("첫째, '절감 보장'이라는 말. 우리는 절감 보장을 하지 않습니다.", {"절감 보장": "계측으로 확인된 절감"})
    assert "'절감 보장'" in text and "계측으로 확인된 절감을" in text and replaced == ["절감 보장"]


# + 절감률 보장 표현 감지
def test_claim_guarantee_flag():
    from app.ecozin.generators.quality_checker import check_and_fix
    p = make_project()
    t = template_loader.get_template("energy-saving-device")
    d = generate_drafts(p)[0]
    d.hook = "전기요금 30% 절감을 반드시 보장합니다."
    check_and_fix(d, p, t, [])
    assert any(f.type == "claim_guarantee" and f.severity == "block" for f in d.quality_flags)
    assert "절감 효과는 설비 부하" in d.description


# + 금지어 / 필수어
def test_banned_and_required_phrases():
    from app.ecozin.generators.quality_checker import check_and_fix
    p = make_project()
    t = template_loader.get_template("energy-saving-device")
    drafts = generate_drafts(p)
    for d in drafts:
        assert "계측 리포트" in " ".join([d.script, d.description, d.hook, d.pinned_comment])
    d = drafts[0]
    d.title = "전기요금 반값 만들기"
    check_and_fix(d, p, t, [])
    assert any(f.type == "banned_phrase" and f.match == "반값" and f.severity == "block" for f in d.quality_flags)


# + 시청자 유형 분기
def test_audience_mode_branching():
    end = generate_drafts(make_project("end_customer", "견적요청"))
    partner = generate_drafts(make_project("partner", "대리점문의"))
    for e, pd in zip(end, partner):
        assert e.hook != pd.hook
        assert pd.cta == "대리점문의"
        text = " ".join([pd.hook, pd.script, pd.description, pd.pinned_comment])
        assert ("대리점" in text) or ("파트너" in text)


# + CTA 정합성
def test_cta_consistency():
    for d in generate_drafts(make_project(cta="현장진단신청")):
        assert d.cta == "현장진단신청"
        assert "진단" in d.script.split("\n")[-1]
        assert not any(f.type == "cta_mismatch" for f in d.quality_flags)


# bridge: VideoParams 변환
def test_bridge_builds_local_params(tmp_path):
    p = make_project()
    img = tmp_path / "before_after_meter.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0fake")
    db.save_asset(SourceAsset(project_id=p.id, type="image", path_or_content=str(img), note="계측"))
    d = generate_drafts(p, assets=db.list_assets(p.id))[0]
    params = bridge.build_video_params(d, p, db.list_assets(p.id), "preview")
    assert params.video_source == "local" and params.video_script == d.script
    assert params.video_materials[0].url == str(img)
    assert params.voice_name.startswith("ko-KR") and params.subtitle_enabled
    assert params.bgm_type == ""
    final = bridge.build_video_params(d, p, db.list_assets(p.id), "final")
    assert final.bgm_type == "random"


def test_bridge_refuses_without_assets():
    p = make_project()
    d = generate_drafts(p)[0]
    with pytest.raises(bridge.BridgeError):
        bridge.build_video_params(d, p, [], "preview")


def test_bridge_requires_approval(monkeypatch):
    p = make_project()
    d = generate_drafts(p)[0]
    with pytest.raises(bridge.BridgeError):
        bridge.submit_render(d.id, "preview")


# + 실증 시작 단계(전후 숫자 없음) → 전후비교형 대신 현장 실증형, 빈 자리표시자 없음
def test_baseline_stage_uses_proof_angle():
    src = ("호주 풍력발전 단지 47호기 현장. 발전기 하부 2500A 기중차단기 배전반에 HIOKI 전력계측기를 설치했습니다. "
           "설치 전 기준 데이터를 먼저 확보한 뒤 절감 장치를 설치하고 같은 계측기로 전후를 비교하는 실증을 진행할 예정입니다. 결과는 계측 리포트로 공개합니다.")
    p = make_project(source_text=src, target_audience="풍력·태양광 발전단지 운영사", goal_cta="상담문의",
                     source_notes="turbine_47.jpg (풍력발전기 47호기 외관)\nmeter_panel.jpg (계측기 화면)\ninstall_work.jpg (엔지니어가 계측기 설치 중)")
    drafts = generate_drafts(p)
    keys = [d.angle_key for d in drafts]
    assert "proof" in keys and "before_after" not in keys
    for d in drafts:
        assert " ," not in d.hook and " ." not in d.hook and "{" not in d.hook
    proof = next(d for d in drafts if d.angle_key == "proof")
    assert "호주 풍력발전 단지 47호기" in proof.hook or "호주 풍력발전 단지 47호기" in proof.script
    assert proof.scene_plan[0].asset_ref == "turbine_47.jpg" and proof.scene_plan[0].visual_source == "photo"
    # 설치 작업 사진은 화면 캡처가 아니라 실사로 분류
    from app.ecozin.generators.source_analyzer import classify_asset_visual
    assert classify_asset_visual({"ref": "install_work.jpg", "note": "엔지니어가 계측기 설치 중"}) == "photo"


def test_upload_is_downscaled(tmp_path):
    from io import BytesIO
    from PIL import Image
    from app.ecozin import assets as asset_store
    buf = BytesIO(); Image.new("RGB", (4000, 3000), (10, 20, 30)).save(buf, format="JPEG")
    path = asset_store.save_upload(str(tmp_path), "big.jpg", buf.getvalue())
    assert Image.open(path).size == (1920, 1440)
