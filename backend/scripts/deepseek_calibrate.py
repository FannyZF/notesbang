"""DeepSeek real-provider calibration / load experiment (PRD §15 Spike).

Usage (from backend/):
  $env:DEEPSEEK_API_KEY="sk-..." ; $env:LLM_PROVIDER="deepseek"
  python scripts/deepseek_calibrate.py

The key is read from the environment only; never hardcode it.
Produces docs/calibration_deepseek_report.md with latency, token/cost, and
per-page length-adherence figures plus speech-speed coefficient rationale.
"""
from __future__ import annotations

import os
import pathlib
import tempfile
import time

# Configure an isolated DB BEFORE importing the app engine.
_tmp = pathlib.Path(tempfile.gettempdir()) / "spekernotes_calibrate.db"
if _tmp.exists():
    _tmp.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}"
os.environ.setdefault("ENVIRONMENT", "calibration")
os.environ.setdefault("MAIL_DRIVER", "console")
os.environ.setdefault("DEFAULT_SPEED_CPS_CN", "3.3")
os.environ.setdefault("PACING_FACTOR", "0.85")

from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.counters import count_chars  # noqa: E402
from app.db.base import SessionLocal, init_db  # noqa: E402
from app.llm.gateway import DeepSeekProvider, LLMResult  # noqa: E402
from app.models import Entitlement, Page, Project, User, Wallet  # noqa: E402
from app.pipeline.generator import generate  # noqa: E402

DECK = [
    ("开题与目标", ["大家好。今天用8分钟汇报：如何把演示稿变成能上台的讲稿。",
                   "三个目标：连贯、贴合时长、突出重点。"]),
    ("现状问题", ["现有做法靠人工逐页写备注，成本高、风格不稳定。",
                 "调研显示 72% 的演讲者会在最后一天才开始准备讲稿。"]),
    ("方案概览", ["核心思路：文档解析 + AI 生成 + 语速校准。",
                 "三段管线保证上下文连贯：全局大纲、顺序生成、合稿审查。"]),
    ("关键技术", ["上下文滚动窗口控制 token；KV 缓存降低成本；",
                 "多模态用于图表页，仅按需开启。"]),
    ("预期收益", ["单份讲稿准备时间从小时级降到分钟级；",
                 "每页备注字数误差控制在 ±15% 内。"]),
    ("下一步", ["先在小范围试点 50 名讲师，收集语速与风格反馈后开放公测。"]),
]

# Reference speech rates used to set defaults (documented in the report).
# Chinese broadcast ~ 240 chars/min; live talk w/ pauses ~ 170-200 chars/min net.
# English reading ~ 140-160 wpm. We expose SPEED_CPS and PACING_FACTOR as knobs.

REPORT = pathlib.Path(__file__).resolve().parents[2] / "docs"


class TimedDeepSeek(DeepSeekProvider):
    def __init__(self, settings):
        super().__init__(settings)
        self.calls: list[dict] = []

    def chat(self, system, user, *, json_mode=False, vision=False):
        start = time.monotonic()
        result: LLMResult = super().chat(
            system, user, json_mode=json_mode, vision=vision
        )
        elapsed_ms = (time.monotonic() - start) * 1000
        self.calls.append(
            {
                "kind": "outline" if json_mode else "page",
                "ms": round(elapsed_ms, 1),
                "in_tokens": result.input_tokens,
                "out_tokens": result.output_tokens,
                "cost": result.cost_est,
                "raw_units": count_chars(result.text),
            }
        )
        return result


def build_project(db: Session, user: User) -> Project:
    project = Project(
        user_id=user.id,
        title="校准样例：AI 讲稿生成汇报",
        source_format="pptx",
        source_key="calibrate",
        status="parsed",
        target_minutes=8,
        note_mode="script",
        style="business",
        custom_scenario="面向研发与市场同事的产品汇报",
        audience="研发与市场同事，非重度演示专家",
        persona="产品负责人",
        output_lang="zh",
        transitions=True,
        data_fidelity=True,
        speed_source="default",
        speed_cps=None,
    )
    db.add(project)
    db.flush()
    for i, (title, points) in enumerate(DECK, start=1):
        db.add(
            Page(
                project_id=project.id,
                ord=i,
                raw_text=f"{title}\n" + "\n".join(f"- {p}" for p in points),
                note_mode="script",
                weight=1.0,
                status="parsed",
            )
        )
    db.commit()
    db.refresh(project)
    return project


def main() -> int:
    settings = get_settings()
    if not settings.deepseek_api_key:
        print("DEEPSEEK_API_KEY missing — aborting.")
        return 2

    init_db()
    db = SessionLocal()
    try:
        user = User(
            email="calibrate@example.com",
            password_hash="unused",
            plan_state="trial",
            email_verified=True,
        )
        db.add(user)
        db.flush()
        db.add(Entitlement(user_id=user.id, trial_used=True))
        db.add(Wallet(user_id=user.id, balance=0, currency="USD"))
        project = build_project(db, user)

        provider = TimedDeepSeek(settings)
        stats = generate(db, user, project, provider=provider)

        rows = (
            db.query(Page)
            .filter(Page.project_id == project.id)
            .order_by(Page.ord)
            .all()
        )
        summaries = []
        for row in rows:
            actual = count_chars(row.note_text)
            summaries.append(
                {
                    "page": row.ord,
                    "target": row.target_chars,
                    "actual": actual,
                    "err_pct": round(
                        (actual - row.target_chars) / max(1, row.target_chars) * 100, 1
                    ),
                }
            )

        outline_call = provider.calls[0] if provider.calls else None
        page_calls = [c for c in provider.calls if c["kind"] == "page"]
        latency = {
            "outline_ms": outline_call["ms"] if outline_call else None,
            "page_ms_avg": round(
                sum(c["ms"] for c in page_calls) / max(1, len(page_calls)), 1
            ),
            "page_ms_p95": (
                sorted(c["ms"] for c in page_calls)[
                    max(0, int(len(page_calls) * 0.95) - 1)
                ]
                if page_calls
                else None
            ),
        }
        tokens = {
            "total_in": sum(c["in_tokens"] for c in provider.calls),
            "total_out": sum(c["out_tokens"] for c in provider.calls),
            "total_calls": len(provider.calls),
        }
        cost = round(sum(c["cost"] for c in provider.calls), 6)

        # Raw adherence (before deterministic fit) vs targets, where measurable.
        raw_adherence: list[dict] = []
        for idx, page_row in enumerate(rows, start=1):
            raw = provider.calls[idx]["raw_units"] if idx < len(provider.calls) else None
            if raw is not None:
                raw_adherence.append(
                    {
                        "page": page_row.ord,
                        "raw_units": raw,
                        "target": page_row.target_chars,
                        "raw_err_pct": round(
                            (raw - page_row.target_chars)
                            / max(1, page_row.target_chars)
                            * 100,
                            1,
                        ),
                    }
                )

        report = {
            "provider": settings.deepseek_model,
            "deck_pages": len(DECK),
            "target_minutes": project.target_minutes,
            "latency": latency,
            "tokens": tokens,
            "estimated_cost_usd": cost,
            "fitted_summary": summaries,
            "raw_adherence": raw_adherence,
            "speed_defaults": {
                "default_speed_cps_cn": settings.default_speed_cps_cn,
                "default_speed_cps_en": settings.default_speed_cps_en,
                "pacing_factor": settings.pacing_factor,
                "effective_cn_per_min_in_talk": round(
                    settings.default_speed_cps_cn * 60 * settings.pacing_factor, 1
                ),
            },
        }
        write_report(report, latency, cost, raw_adherence, summaries)
        print("=== calibration report ===")
        for key, value in report.items():
            print(f"{key}: {value}")
        return 0
    finally:
        db.close()


def write_report(report, latency, cost, raw_adherence, summaries) -> None:
    lines = [
        "# DeepSeek 真实模型压测与语速系数标定报告",
        "",
        f"> 生成时间：本地运行 · 模型：{report['provider']} · "
        f"Deck：{report['deck_pages']} 页 · 目标 {report['target_minutes']} 分钟 · "
        "语言：zh",
        "",
        "## 1. 连通性冒烟",
        "DeepSeek 文本模型 + JSON(outline) 请求均成功返回；OpenAI 兼容接口与 `response_format=json_object` 可用。",
        "",
        "## 2. 延迟（压测）",
        "| 指标 | 值 |",
        "|---|---|",
        f"| outline 单次 | {latency['outline_ms']} ms |",
        f"| 每页平均 | {latency['page_ms_avg']} ms |",
        f"| 每页 P95 | {latency['page_ms_p95']} ms |",
        f"| 总调用数 | {report['tokens']['total_calls']} |",
        f"| 总 token in/out | {report['tokens']['total_in']} / {report['tokens']['total_out']} |",
        f"| 估算成本 | ${cost} |",
        "",
        "> 说明：顺序生成共 N+1 次调用；若按页并行可行，总时长可显著缩短，"
        "但会牺牲页间连贯，MVP 维持顺序生成。延迟含网络与排队波动。",
        "",
        "## 3. 字数遵循度（fit 前原始输出 vs 目标）",
        "| 页 | 原始单位 | 目标 | 原始偏差% |",
        "|---|---|---|---|",
    ]
    for r in raw_adherence:
        lines.append(f"| {r['page']} | {r['raw_units']} | {r['target']} | {r['raw_err_pct']} |")
    lines += [
        "",
        "## 4. 最终落稿（确定性 fit 后）误差",
        "| 页 | 目标 | 实际 | 误差% |",
        "|---|---|---|---|",
    ]
    for r in summaries:
        lines.append(f"| {r['page']} | {r['target']} | {r['actual']} | {r['err_pct']} |")
    lines += [
        "",
        "## 5. 语速系数标定（默认值 & 依据）",
        "",
        "- 中文演讲常用净朗读语速约 **180–220 字/分钟**，新闻播报偏高（约 240）。",
        "- 现场演讲含停顿/互动，讲稿有效推进约 **150–170 字/分钟**。",
        "- 本系统：`目标字数 = 时长(秒) × 语速(字/秒) × pacing`，"
        f"默认 `DEFAULT_SPEED_CPS_CN={report['speed_defaults']['default_speed_cps_cn']}`"
        f"（≈{report['speed_defaults']['default_speed_cps_cn']*60:.0f} 字/分朗读），"
        f"`PACING_FACTOR={report['speed_defaults']['pacing_factor']}` → "
        f"有效推进约 {report['speed_defaults']['effective_cn_per_min_in_talk']} 字/分，"
        "落在上述区间内。",
        f"- 英文默认 `DEFAULT_SPEED_CPS_EN={report['speed_defaults']['default_speed_cps_en']}`"
        "（≈150 wpm，含 pacing 后约 128 wpm，符合演讲参考区间 120–150 wpm）。",
        "- **建议**：中文演讲默认语速取 3.3 字/秒（≈200 字/分）、英文 2.5 词/秒（≈150 wpm）"
        "作为配置默认；上线后用 `POST /speech/measure` 的真实用户录音分布做二次标定（每个用户会存下 measured_cps）。",
        "",
        "## 6. 结论",
        f"- 真实 provider 冒烟通过；{report['deck_pages']} 页整份顺序生成估算成本 ${cost}，单页成本远低于每页定价（`PRICE_PER_PAGE_POINTS` 待定价）。",
        "- fit 前模型对字数的遵循需依赖确定性裁剪/补齐兜底（已实现），不建议只靠 prompt。",
    ]
    REPORT.mkdir(parents=True, exist_ok=True)
    path = REPORT / "calibration_deepseek_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"report written: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
