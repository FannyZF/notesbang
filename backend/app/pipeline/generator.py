"""4-stage generation pipeline (PRD §4.6, quality refinement).

1. Draft initial speaker notes per slide (rolling context).
2. Settings/rules review  — cover the slide, honor style/scenario/language & length.
3. Subject-matter review  — professional accuracy & logic, numbers faithful.
4. Audience review        — tailored to the audience & scenario, more engaging.

Every stage rewrites the note through the LLM, then the deterministic fitter
keeps it inside the target-length band. Progress reports a human step label
so the UI can show the notes being refined.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.length.allocator import allocate_targets
from app.length.char_checker import fit_notes
from app.llm.gateway import LLMError, LLMResult, Provider, get_provider
from app.llm.renderer import load_style, render_notes_system
from app.models import GenerationLog, Page, Project, StyleProfile, User
from app.pipeline.contexts import StoryTrace, build_user_context, first_hook
from app.pipeline.outline import build_deck_outline, summarize

PHASES = [
    ("Drafting initial notes", "draft"),
    ("Checking the notes against your settings", "rules"),
    ("Reviewing subject-matter accuracy", "expert"),
    ("Tuning the notes for your audience", "audience"),
]


class GenerationError(RuntimeError):
    pass


def resolve_speed_cps(user: User, project: Project) -> float:
    """PRD §4.4: default | manual | recording, per-language defaults."""
    settings = get_settings()
    if project.speed_source == "manual" and project.speed_cps:
        return float(project.speed_cps)
    if project.speed_source == "recording":
        if user.measured_speed_cps:
            return float(user.measured_speed_cps)
        return settings.default_speed_cps_cn
    return settings.default_speed_cps_cn


def _unit_name(project: Project) -> str:
    if project.output_lang and project.output_lang.lower() in ("en", "english", "英文"):
        return "words"
    return "字"


def _resolve_style_text(db: Session, project: Project) -> str:
    """Personal style profile overrides the preset style block (PRD §4.8)."""
    if project.style_profile_id:
        profile = db.get(StyleProfile, project.style_profile_id)
        if profile is not None and profile.profile_text:
            return profile.profile_text
    return load_style(project.style)


def _transitions_text(project: Project) -> str:
    return "要求自然承上启下、与前页衔接。" if project.transitions else "每页相对独立。"


def _data_text(project: Project) -> str:
    return (
        "必须照幻灯片数字核对，禁止臆造；重点页逐点解读。"
        if project.data_fidelity
        else "按常规处理数据。"
    )


def _output_lang_text(project: Project) -> str:
    lang = (project.output_lang or "auto").strip()
    if lang in ("auto", "跟随", ""):
        return "the same language as the document (follow the slides)"
    if lang in ("zh", "中文"):
        return "Chinese (简体中文)"
    if lang in ("en", "english", "英文"):
        return "English"
    return lang


@dataclass
class _Acc:
    model: str = ""
    in_tokens: int = 0
    out_tokens: int = 0
    cost: float = 0.0

    def add(self, result: LLMResult) -> None:
        self.model = result.model
        self.in_tokens += result.input_tokens
        self.out_tokens += result.output_tokens
        self.cost += result.cost_est


def _stage_system(
    stage: str,
    project: Project,
    target: int,
    unit_name: str,
    tolerance_pct: str,
    settings_text: str,
) -> str:
    if stage == "draft":
        return ""
    base = (
        f"场景约束（最高优先级）：{project.custom_scenario or '无'}\n"
        f"听众：{project.audience}\n视角：以“{project.persona}”第一人称。\n"
        f"输出语言：{_output_lang_text(project)}\n{_transitions_text(project)}\n"
        f"数据规则：{_data_text(project)}\n"
        f"长度：目标 {target}（{unit_name}），允许 ±{tolerance_pct}。\n"
        f"风格参考：\n{settings_text}"
    )
    if stage == "rules":
        return (
            "你是严格的设置规则复核员。检查草稿是否完整覆盖本页幻灯片内容、是否遵守风格与"
            "场景约束、语言正确、长度在目标范围内、没有遗漏或与设置冲突之处。"
            "按你的专业判断逐项核对后，重写这页 speaker notes 以修正任何问题。"
            f"只输出修正后的讲稿文本。\n{base}"
        )
    if stage == "expert":
        return (
            "你是本演示主题领域的资深专家。审查讲稿的专业内容与逻辑是否准确严谨：术语与表述"
            "是否恰当、数据是否与幻灯片一致（禁止臆造数字）、推理与结论是否站得住。发现问题即"
            "修正并重写为专业无误的讲稿。只输出讲稿文本。\n{base}"
        )
    return (
        "你代表目标听众（例如：学者/管理层/学生/投资人等）阅读这页讲稿。确保内容贴合听众的"
        "背景与关切、足够清晰与吸引人、语气合适、重点突出，让听众愿意听下去。按其口味微调并"
        "重写这页讲稿，只输出讲稿文本。\n{base}"
    )


def _refine_user(stage: str, page_text: str, current: str, target: int) -> str:
    head = {
        "rules": "请按设置与内容要求复核并重写以下这页讲稿",
        "expert": "请以领域专家视角审查并重写这页讲稿",
        "audience": "请以目标听众视角润色重写这页讲稿",
    }[stage]
    return (
        f"{head}（目标长度 {target} 单位）。\n\n"
        f"【本页幻灯片内容】\n{page_text or '(无文本)'}\n\n"
        f"【当前讲稿】\n{current}\n\n请输出修正后的 speaker notes："
    )


def generate(
    db: Session,
    user: User,
    project: Project,
    *,
    page_ids: list[int] | None = None,
    provider: Provider | None = None,
    on_progress: Callable[[int, str], None] | None = None,
) -> dict:
    """Generate all pages (or the subset) through the 4-stage pipeline."""
    pages = (
        db.query(Page)
        .filter(Page.project_id == project.id)
        .order_by(Page.ord)
        .all()
    )
    if not pages:
        raise GenerationError("no pages to generate")

    settings = get_settings()
    provider = provider or get_provider()

    texts = [p.raw_text for p in pages]
    weights = [p.weight or 1.0 for p in pages]
    cps = resolve_speed_cps(user, project)
    total_units = int(project.target_minutes * 60 * cps * settings.pacing_factor)
    targets = allocate_targets(texts, weights, total_units)
    for p, t in zip(pages, targets):
        p.target_chars = t

    target_ids = set(pages[i].id for i in range(len(pages)))
    if page_ids is not None:
        target_ids = set(page_ids)

    # Global outline pass (whole-deck generation only).
    if page_ids is None:
        outline = build_deck_outline(provider, texts)
        outline_text = outline.to_context()
        takeaways = outline.takeaways
    else:
        outline_text = ""
        takeaways = {}

    mode = project.note_mode
    settings_text = _resolve_style_text(db, project)
    unit_name = _unit_name(project)
    tolerance_pct = f"{int(settings.char_tolerance * 100)}%"

    phases = PHASES if (project.quality_mode or "full") != "fast" else PHASES[:1]

    current: dict[int, str] = {}
    acc: dict[int, _Acc] = {p.id: _Acc() for p in pages}
    N = len(pages)
    steps = len(phases) * N
    step = 0

    def progress(phase_label: str) -> None:
        nonlocal step
        step += 1
        if on_progress is not None:
            pct = 3 + int(93 * step / max(steps, 1))
            on_progress(min(pct, 97), phase_label)

    # ---- Phase 1: draft ----
    trace = StoryTrace()
    prev = ""
    for i, page in enumerate(pages):
        target = targets[i]
        if page.id not in target_ids:
            if page.note_text:
                prev = page.note_text
            continue

        next_hook = first_hook(pages[i + 1].raw_text) if i + 1 < N else ""
        system = render_notes_system(
            mode,
            {
                "style_text": settings_text,
                "custom_scenario": project.custom_scenario,
                "audience": project.audience,
                "persona": project.persona,
                "output_lang": _output_lang_text(project),
                "transitions_text": _transitions_text(project),
                "data_fidelity_text": _data_text(project),
                "page_char_target": target,
                "unit_name": unit_name,
                "tolerance_pct": tolerance_pct,
                "total_target": total_units,
                "story_done": total_units - sum(targets[i:]) + target,
            },
        )
        user_ctx = build_user_context(
            outline_text=outline_text,
            trace=trace,
            prev_notes=prev,
            next_hook=next_hook,
            page_no=page.ord,
            total_pages=N,
            section_name="演讲",
            takeaway=takeaways.get(page.ord, ""),
            page_text=page.raw_text,
        )
        try:
            result = provider.chat(system, user_ctx, vision=False)
        except LLMError as exc:
            raise GenerationError(str(exc)) from exc
        note = fit_notes(result.text.strip(), target, settings.char_tolerance)
        current[page.id] = note
        acc[page.id].add(result)
        prev = note
        trace.append(summarize(note))
        progress(PHASES[0][0])

    # ---- Phase 2-4: review passes (skipped entirely in fast mode) ----
    for phase_label, stage in phases[1:]:
        for i, page in enumerate(pages):
            if page.id not in target_ids:
                continue
            target = targets[i]
            system = _stage_system(
                stage, project, target, unit_name, tolerance_pct, settings_text
            )
            user_ctx = _refine_user(stage, page.raw_text, current[page.id], target)
            try:
                result = provider.chat(system, user_ctx, vision=False)
            except LLMError as exc:
                raise GenerationError(str(exc)) from exc
            improved = fit_notes(
                result.text.strip(), target, settings.char_tolerance
            )
            current[page.id] = improved
            acc[page.id].add(result)
            progress(phase_label)

    # ---- Persist refined notes ----
    for page in pages:
        if page.id not in target_ids:
            continue
        page.note_text = current[page.id]
        page.status = "generated"
        page.version = (page.version or 1) + 1
        record = acc[page.id]
        db.add(
            GenerationLog(
                project_id=project.id,
                page_id=page.id,
                model=record.model,
                input_tokens=record.in_tokens,
                output_tokens=record.out_tokens,
                cost_est=round(record.cost, 6),
            )
        )

    db.commit()
    return {"updated": len(target_ids), "total_units": total_units, "mode": mode}
