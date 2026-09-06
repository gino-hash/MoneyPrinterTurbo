"""업종 템플릿 로더. app/ecozin/templates/*.json 을 읽고 필수 구조를 검증한다."""

from __future__ import annotations

import glob
import json
import os
from typing import Any, Optional

from app.ecozin.models import AUDIENCE_MODES

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "templates")

_REQUIRED_TOP = (
    "industry", "name", "version", "audiences", "angles", "cta_patterns",
    "banned_claims", "required_disclaimers", "scene_plan_template", "vocabulary",
)
_REQUIRED_AUDIENCE = ("label", "audience_defaults", "pain_points", "hook_patterns", "default_ctas")
_REQUIRED_ANGLE = ("key", "label", "script_beats")


class TemplateError(ValueError):
    pass


def validate_template(cfg: dict[str, Any], source: str = "<memory>") -> None:
    missing = [k for k in _REQUIRED_TOP if k not in cfg]
    if missing:
        raise TemplateError(f"{source}: 필수 키 누락 {missing}")
    for mode in AUDIENCE_MODES:
        if mode not in cfg["audiences"]:
            raise TemplateError(f"{source}: audiences.{mode} 가 없습니다")
        aud = cfg["audiences"][mode]
        miss = [k for k in _REQUIRED_AUDIENCE if k not in aud]
        if miss:
            raise TemplateError(f"{source}: audiences.{mode} 필수 키 누락 {miss}")
        for p in aud["pain_points"]:
            if isinstance(p, dict) and not p.get("text"):
                raise TemplateError(f"{source}: audiences.{mode}.pain_points 항목에 text 가 없습니다")
    angles = cfg["angles"]
    if not isinstance(angles, list) or len(angles) < 3:
        raise TemplateError(f"{source}: angles 는 3개 이상이어야 합니다")
    keys = set()
    for a in angles:
        miss = [k for k in _REQUIRED_ANGLE if k not in a]
        if miss:
            raise TemplateError(f"{source}: angle 필수 키 누락 {miss}")
        if a["key"] in keys:
            raise TemplateError(f"{source}: angle key 중복 {a['key']}")
        keys.add(a["key"])
        for mode in AUDIENCE_MODES:
            hp = cfg["audiences"][mode]["hook_patterns"]
            if a["key"] not in hp or not hp[a["key"]]:
                raise TemplateError(f"{source}: audiences.{mode}.hook_patterns.{a['key']} 가 비어 있습니다")
    if len(cfg["scene_plan_template"]) < 3:
        raise TemplateError(f"{source}: scene_plan_template 은 3장면 이상이어야 합니다")


def load_template_file(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    validate_template(cfg, source=os.path.basename(path))
    return cfg


_cache: dict[str, dict[str, Any]] = {}


def load_all(force: bool = False) -> dict[str, dict[str, Any]]:
    """industry 키 → 템플릿. 잘못된 파일이 하나라도 있으면 예외로 기동을 막는다."""
    global _cache
    if _cache and not force:
        return _cache
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(glob.glob(os.path.join(TEMPLATES_DIR, "*.json"))):
        cfg = load_template_file(path)
        result[cfg["industry"]] = cfg
    if not result:
        raise TemplateError(f"템플릿 파일이 없습니다: {TEMPLATES_DIR}")
    _cache = result
    return result


def get_template(industry: str) -> dict[str, Any]:
    templates = load_all()
    if industry not in templates:
        raise TemplateError(f"알 수 없는 업종: {industry} (사용 가능: {list(templates)})")
    return templates[industry]


def list_industries() -> list[tuple[str, str]]:
    return [(k, v["name"]) for k, v in load_all().items()]


def audience_section(template: dict[str, Any], audience_mode: str) -> dict[str, Any]:
    if audience_mode not in template["audiences"]:
        raise TemplateError(f"템플릿에 시청자 유형 {audience_mode} 가 없습니다")
    return template["audiences"][audience_mode]


def default_ctas(template: dict[str, Any], audience_mode: str) -> list[str]:
    aud = audience_section(template, audience_mode)
    primary = list(aud.get("default_ctas", []))
    others = [c for c in template.get("cta_patterns", {}) if c not in primary]
    return primary + others


def angle_by_key(template: dict[str, Any], key: str) -> Optional[dict[str, Any]]:
    for a in template["angles"]:
        if a["key"] == key:
            return a
    return None
