"""Genera un reporte HTML autocontenido (gráficas SVG embebidas, sin dependencias externas)."""

from __future__ import annotations

import html
from pathlib import Path

import pandas as pd

from fleet_analytics import charts
from fleet_analytics.cleaning import to_long
from fleet_analytics.emissions import EMISSION_FACTORS_KG_PER_UNIT, FACTOR_NOTES
from fleet_analytics.metrics import (
    add_co2e,
    co2e_by_fuel,
    fuel_share,
    headline,
    monthly_trend,
    segment_summary,
)
from fleet_analytics.validation import validate

CSS = """
:root{--bg:#f6f5f2;--card:#fcfcfb;--text:#0b0b0b;--muted:#52514e;--line:#e4e3df;--accent:#2a78d6;
--warn-bg:#fff4d6;--warn-line:#c98500;--err:#b42318;--info:#2a78d6}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);
font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1000px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:1.7rem;margin:0 0 4px}h2{font-size:1.15rem;margin:36px 0 12px}
.sub{color:var(--muted);margin:0 0 20px}
.banner{border-left:4px solid var(--warn-line);background:var(--warn-bg);padding:12px 16px;border-radius:6px;margin:16px 0}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px}
.kpi .v{font-size:1.4rem;font-weight:650}.kpi .l{color:var(--muted);font-size:.82rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;margin:12px 0;overflow-x:auto}
.card svg{max-width:100%;height:auto;display:block}
table{border-collapse:collapse;width:100%;font-size:.85rem}
th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th:first-child,td:first-child,td.t{text-align:left}th{color:var(--muted);font-weight:600}
td.msg{text-align:left;white-space:normal}
.sev{font-weight:600;text-transform:uppercase;font-size:.72rem}.sev.error{color:var(--err)}
.sev.warning{color:var(--warn-line)}.sev.info{color:var(--info)}
details summary{cursor:pointer;color:var(--muted)}
footer{color:var(--muted);font-size:.8rem;margin-top:40px}
"""

FUEL_LABELS = charts.FUEL_LABELS


def _fmt(v, d=0, prefix="", suffix=""):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return f"{prefix}{v:,.{d}f}{suffix}"


def _table(df: pd.DataFrame, columns: dict[str, tuple[str, int]], text_cols=()) -> str:
    head = "".join(f"<th>{html.escape(label)}</th>" for label, _ in columns.values())
    rows = []
    for _, r in df.iterrows():
        cells = []
        for col, (_, dec) in columns.items():
            v = r[col]
            if col in text_cols or not isinstance(v, (int, float)):
                cells.append(f'<td class="t">{html.escape(str(v))}</td>')
            else:
                cells.append(f"<td>{_fmt(float(v), dec)}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def _issues_table(issues: pd.DataFrame) -> str:
    if issues.empty:
        return "<p>Sin hallazgos.</p>"
    rows = "".join(
        f'<tr><td><span class="sev {r.severity}">{r.severity}</span></td><td class="t">{html.escape(r.rule)}</td>'
        f'<td class="t">{html.escape(r.segment)}</td><td class="msg">{html.escape(r.month)}</td>'
        f'<td class="msg">{html.escape(r.message)}</td></tr>'
        for r in issues.itertuples()
    )
    return (
        "<table><thead><tr><th>Severidad</th><th>Regla</th><th>Segmento</th><th>Mes</th><th>Detalle</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )


def build_report(raw: pd.DataFrame, source: str = "real", title: str | None = None) -> str:
    long = add_co2e(to_long(raw, source=source))
    if long.empty:
        raise ValueError("El archivo no contiene ningún dato numérico para reportar.")
    issues = validate(raw, long)
    kpi = headline(long)
    summary = segment_summary(long)
    by_seg_month = monthly_trend(long, by=["ownership", "vehicle_type"])
    shares = fuel_share(long, "cost_usd")
    co2 = co2e_by_fuel(long)
    is_synth = source == "synthetic"
    many_fuels = long["fuel"].nunique() > 1

    title = title or (
        "Reporte de energía de flotilla — DATOS SINTÉTICOS" if is_synth else "Reporte de energía de flotilla"
    )
    country = ", ".join(sorted(long["country"].unique()))
    years = ", ".join(str(y) for y in sorted(long["year"].unique()))

    banner = (
        '<div class="banner"><strong>Datos sintéticos.</strong> Estas cifras fueron generadas por '
        "<code>fleet_analytics.synthetic</code> para demostrar el reporte con un año completo y varios "
        "combustibles. No representan ninguna flotilla real.</div>"
        if is_synth
        else '<div class="banner"><strong>Datos reales, cobertura parcial.</strong> '
        f"Sólo {kpi['segments']} de {raw[['Ownership', 'Type']].drop_duplicates().shape[0]} segmentos del "
        "template tienen datos, y sólo diésel. Revise la sección de validación antes de interpretar.</div>"
    )

    kpis = [
        (_fmt(kpi["km"] / 1e6, 1, suffix=" M"), "km recorridos"),
        (_fmt(kpi["liters"] / 1e6, 2, suffix=" M"), "litros (combustibles líquidos)"),
        (_fmt(kpi["kwh"] / 1e3, 0, suffix=" MWh"), "energía eléctrica") if kpi["kwh"] else None,
        (_fmt(kpi["cost_usd"] / 1e6, 2, prefix="$", suffix=" M"), "gasto USD"),
        (_fmt(kpi["cost_per_km"], 3, prefix="$"), "USD por km (global)"),
        (_fmt(kpi["co2e_t"], 0, suffix=" t"), "CO2e estimado"),
    ]
    kpi_html = "".join(
        f'<div class="kpi"><div class="v">{v}</div><div class="l">{lbl}</div></div>' for v, lbl in filter(None, kpis)
    )

    # Gráficas: por combustible si hay varios; si no, por segmento.
    figs = []
    if many_fuels:
        total_month = monthly_trend(long, by=[])
        figs.append(
            charts.monthly_total(total_month, "cost_usd", "Gasto mensual total de la flotilla", "USD", "${x:,.0f}")
        )
        figs.append(
            charts.monthly_total(
                total_month, "cost_per_km", "Costo por km de la flotilla (mensual)", "USD/km", "${x:,.3f}"
            )
        )
        figs.append(charts.fuel_bars(co2, "co2e_t", "CO2e estimado anual por combustible", "t CO2e", "{:,.0f}"))
    else:
        figs.append(charts.monthly_by_segment(by_seg_month, "km", "Kilómetros mensuales por segmento", "km"))
        figs.append(
            charts.monthly_by_segment(
                by_seg_month, "cost_per_unit", "Precio pagado por litro (USD/L)", "USD/L", "${x:,.2f}"
            )
        )
    figs.append(
        charts.segment_bars(summary, "cost_per_km", "Costo por km por segmento y combustible", "USD/km", "${:,.3f}")
    )
    figs.append(
        charts.segment_bars(summary, "co2e_g_per_km", "Intensidad de emisiones (g CO2e/km)", "g CO2e/km", "{:,.0f}")
    )
    charts_html = "".join(f'<div class="card">{charts.to_svg(f)}</div>' for f in figs)

    summary_view = summary.assign(
        segmento=[charts.segment_label(o, v) for o, v in zip(summary["ownership"], summary["vehicle_type"])],
        combustible=summary["fuel"].map(FUEL_LABELS),
    )
    summary_html = _table(
        summary_view,
        {
            "segmento": ("Segmento", 0),
            "combustible": ("Combustible", 0),
            "unit": ("Unidad", 0),
            "months_reported": ("Meses", 0),
            "vehicles": ("Vehículos (máx.)", 0),
            "km": ("km", 0),
            "volume": ("Volumen", 0),
            "cost_usd": ("USD", 0),
            "efficiency": ("km/unidad", 2),
            "cost_per_km": ("USD/km", 3),
            "cost_per_unit": ("USD/unidad", 3),
            "km_per_vehicle": ("km/vehículo (año)", 0),
            "co2e_g_per_km": ("g CO2e/km", 0),
        },
        text_cols=("segmento", "combustible", "unit"),
    )
    share_html = _table(
        shares.assign(combustible=shares["fuel"].map(FUEL_LABELS), pct=shares["share"] * 100),
        {"combustible": ("Combustible", 0), "cost_usd": ("USD", 0), "pct": ("% del gasto", 1)},
        text_cols=("combustible",),
    )
    co2_html = _table(
        co2.assign(combustible=co2["fuel"].map(FUEL_LABELS)),
        {
            "combustible": ("Combustible", 0),
            "unit": ("Unidad", 0),
            "volume": ("Volumen", 0),
            "factor_kg_per_unit": ("kg CO2e/unidad", 4),
            "co2e_t": ("t CO2e", 1),
        },
        text_cols=("combustible", "unit"),
    )
    monthly_tbl = by_seg_month.assign(
        segmento=[charts.segment_label(o, v) for o, v in zip(by_seg_month["ownership"], by_seg_month["vehicle_type"])],
        mes=by_seg_month["month"].map(lambda m: charts.MONTH_ABBR[int(m) - 1]),
    )
    monthly_html = _table(
        monthly_tbl,
        {
            "mes": ("Mes", 0),
            "segmento": ("Segmento", 0),
            "km": ("km", 0),
            "volume": ("Volumen", 0),
            "cost_usd": ("USD", 0),
            "cost_per_km": ("USD/km", 3),
            "co2e_kg": ("kg CO2e", 0),
        },
        text_cols=("mes", "segmento"),
    )
    factors_html = "".join(
        f"<tr><td>{FUEL_LABELS[f]}</td><td>{v:g}</td><td class='msg'>{html.escape(FACTOR_NOTES[f])}</td></tr>"
        for f, v in EMISSION_FACTORS_KG_PER_UNIT.items()
    )
    counts = issues["severity"].value_counts().to_dict()
    counts_txt = ", ".join(f"{counts.get(s, 0)} {s}" for s in ("error", "warning", "info"))

    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{CSS}</style></head>
<body><main>
<h1>{html.escape(title)}</h1>
<p class="sub">{html.escape(country)} · {years} · fuente: <code>{"synthetic" if is_synth else "real"}</code> ·
{kpi["months"]} meses con datos</p>
{banner}
<div class="kpis">{kpi_html}</div>

<h2>Validación de datos</h2>
<p>{counts_txt}. Las reglas están documentadas en <code>fleet_analytics/validation.py</code>.</p>
<div class="card">{_issues_table(issues)}</div>

<h2>Tendencias y comparativos</h2>
{charts_html}

<h2>Resumen por segmento</h2>
<div class="card">{summary_html}</div>

<h2>Participación del gasto por combustible</h2>
<div class="card">{share_html}</div>

<h2>Emisiones estimadas (CO2e)</h2>
<div class="card">{co2_html}</div>
<details><summary>Factores de emisión usados (aproximados)</summary><div class="card"><table>
<thead><tr><th>Combustible</th><th>kg CO2e / unidad</th><th>Fuente / nota</th></tr></thead>
<tbody>{factors_html}</tbody></table></div></details>

<h2>Detalle mensual</h2>
<details><summary>Ver tabla mensual por segmento</summary><div class="card">{monthly_html}</div></details>

<footer>Generado con <code>fleet_analytics</code>. CO2e = volumen × factor; los factores son
aproximaciones de fuentes públicas (ECCC National Inventory Report, US EPA GHG Emission Factors Hub)
y no sustituyen un inventario oficial de GEI.</footer>
</main></body></html>
"""


def write_report(raw: pd.DataFrame, out_path: str | Path, source: str = "real") -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_report(raw, source=source), encoding="utf-8")
    return out
