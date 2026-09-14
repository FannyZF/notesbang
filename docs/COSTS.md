# NotesBang — Free-tier cost model

All figures are estimates based on measured values (real DeepSeek, English deck):
**full 4-stage generation ≈ $0.027 / generated slide** (incl. outline, 3 reviews,
consistency); **fast mode ≈ $0.008 / slide**. Add ~20% for regenerations/retries.

## Formula
```
annual_llm   = pages_per_year × cost_per_page
annual_infra = VPS + object storage + email + domain + monitoring
total        = annual_llm + annual_infra
```
Assumptions: average deck = 10 slides, generated once.

## Variable cost (LLM)
| Monthly decks | Slides/month | Slides/year | Full mode / yr | Fast mode / yr |
|---|---|---|---|---|
| 100 | 1,000 | 12,000 | ≈ $390 | ≈ $115 |
| 1,000 | 10,000 | 120,000 | ≈ $3,900 | ≈ $1,150 |
| 10,000 | 100,000 | 1,200,000 | ≈ $39,000 | ≈ $11,500 |

## Fixed infra (single VPS + Caddy)
| Scale | Spec | ≈ $/month | ≈ $/year |
|---|---|---|---|
| Small | 2 vCPU / 4 GB | $20 | $240 |
| Medium | 4 vCPU / 8 GB | $30–50 | $360–600 |
| Large | 8 vCPU / 16 GB (+ separate worker) | $100–300 | $1,200–3,600 |

Extras: domain ≈ $12/yr, TLS $0 (Caddy), email (Resend free / SES ≈ $0.10 per
1k) ≈ negligible, Sentry free tier, object storage (S3) ≈ $0.023/GB — with
30-day retention a busy month is tens of GB ≈ a few $/month.

## Total (free service) — indicative
| Monthly decks | Full mode / yr | Fast mode / yr |
|---|---|---|
| 100 | ≈ $650 | ≈ $380 |
| 1,000 | ≈ $4,500–5,000 | ≈ $1,700 |
| 10,000 | ≈ $41,000–43,000 | ≈ $13,000–15,000 |

## Cost levers
- **Fast mode** (skip the 3 reviews) → ~3× cheaper.
- **Cap free usage** (e.g. ≤5 slides / account / month) — the single biggest lever.
- **Only run reviews on request**; use the cheap model for the rules pass.
- **Vision** only on chart/key slides, with a per-deck budget (already enforced).
- Keep rate limits + email verification on (already implemented) to stop abuse.

## Bottom line
LLM cost, not servers, dominates. At **1,000 free decks/month** expect
**~$4–5k/year (full quality)** or **~$1.5–2k/year (fast)**; at 10k decks/month
it becomes a five-figure annual cost — so a free service is viable only with
usage caps, fast mode, or a paid export tier subsidising generation.
