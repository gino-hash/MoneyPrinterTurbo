"""생성기 인터페이스. generate_drafts(project, ...) → Draft[3].

규칙 기반 생성기가 기본이며, 같은 인터페이스로 LLM 생성기를 나중에 붙일 수 있다.
결과는 어떤 생성기든 동일한 품질 검사를 거친다.
"""

from __future__ import annotations

from typing import Any, Optional

from app.ecozin import db, template_loader
from app.ecozin.generators import quality_checker, rule_generator, source_analyzer
from app.ecozin.models import Draft, Event, Project, SourceAsset


class DraftValidationError(ValueError):
    pass


def generate_drafts(project: Project, template: Optional[dict[str, Any]] = None,
                    assets: Optional[list[SourceAsset]] = None, generation: Optional[int] = None,
                    generator: str = "rule", persist: bool = True) -> list[Draft]:
    template = template or template_loader.get_template(project.industry)
    audience = template_loader.audience_section(template, project.audience_mode)
    analysis = source_analyzer.analyze(project.source_text, project.source_notes, template, audience, assets)
    gen = generation if generation is not None else (db.next_generation(project.id) if persist else 1)

    if generator != "rule":
        raise NotImplementedError(f"generator '{generator}' 는 아직 없습니다. 'rule' 을 쓰세요.")
    drafts = rule_generator.generate(project, template, audience, analysis, gen)

    for d in drafts:
        quality_checker.check_and_fix(d, project, template, analysis.key_sentences)
        missing = d.missing_fields()
        if missing:
            raise DraftValidationError(f"초안 {d.draft_index} 필수 필드 누락: {missing}")

    angles = {d.angle_key for d in drafts}
    if len(angles) != len(drafts):
        raise DraftValidationError("초안의 angle 이 서로 달라야 합니다.")

    if persist:
        for d in drafts:
            db.save_draft(d)
        db.save_template_snapshot(template["industry"], template["name"], template.get("version", 1), template)
        db.log_event(Event(project_id=project.id, event_type="draft.generated",
                           payload={"generation": gen, "count": len(drafts), "generator": generator,
                                    "audience_mode": project.audience_mode}))
    return drafts


__all__ = ["generate_drafts", "DraftValidationError", "source_analyzer", "rule_generator", "quality_checker"]
