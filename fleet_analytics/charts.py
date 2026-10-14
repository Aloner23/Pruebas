"""Gráficas con matplotlib. Colores fijos por entidad (combustible / segmento), nunca por rango."""

from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "fleet-analytics"  # IDs estables -> reportes reproducibles
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mticker  # noqa: E402
import pandas as pd  # noqa: E402

# Paleta categórica validada (orden fijo). Cada combustible tiene SIEMPRE el mismo color.
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
FUEL_COLORS = {
    "diesel": PALETTE[0],
    "gasoline": PALETTE[1],
    "electric": PALETTE[2],
    "cng": PALETTE[3],
    "lpg": PALETTE[4],
    "ethanol": PALETTE[5],
}
FUEL_LABELS = {
    "diesel": "Diésel",
    "gasoline": "Gasolina",
    "electric": "Eléctrico",
    "cng": "GNC",
    "lpg": "GLP",
    "ethanol": "Etanol",
}
MONTH_ABBR = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

TEXT = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e4e3df"
SURFACE = "#fcfcfb"


def _style(ax, title: str, ylabel: str = "") -> None:
    ax.set_title(title, loc="left", fontsize=12, color=TEXT, fontweight="bold", pad=10)
    ax.set_ylabel(ylabel, color=MUTED, fontsize=9)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_facecolor(SURFACE)


def _fig(width: float = 8, height: float = 3.6):
    fig, ax = plt.subplots(figsize=(width, height), dpi=110)
    fig.patch.set_facecolor(SURFACE)
    return fig, ax


def segment_label(ownership: str, vehicle_type: str) -> str:
    short = {
        "Independent Operators": "Op. independientes",
        "Logistic Operators (3PL)": "3PL",
        "owned, leased or renting": "Propia/arrendada",
    }.get(ownership, ownership)
    return f"{short} · {vehicle_type}"


def monthly_by_fuel(trend: pd.DataFrame, value: str, title: str, ylabel: str, fmt: str = "{x:,.0f}"):
    """Líneas mensuales, una por combustible (trend agregado por fuel)."""
    fig, ax = _fig()
    fuels = [f for f in FUEL_COLORS if f in set(trend["fuel"])]
    for fuel in fuels:
        g = trend[trend["fuel"] == fuel].sort_values("month")
        ax.plot(
            g["month"],
            g[value],
            color=FUEL_COLORS[fuel],
            linewidth=2,
            marker="o",
            markersize=4,
            label=FUEL_LABELS[fuel],
        )
        last = g.iloc[-1]
        if len(fuels) <= 4:
            ax.annotate(
                FUEL_LABELS[fuel],
                (last["month"], last[value]),
                xytext=(6, 0),
                textcoords="offset points",
                va="center",
                fontsize=8,
                color=TEXT,
            )
    ax.set_xticks(range(1, 13), MONTH_ABBR)
    ax.set_xlim(0.6, 12.9)
    ax.yaxis.set_major_formatter(mticker.StrMethodFormatter(fmt))
    _style(ax, title, ylabel)
    if len(fuels) > 1:
        ax.legend(frameon=False, fontsize=8, ncol=min(len(fuels), 6), loc="upper left", bbox_to_anchor=(0, -0.1))
    fig.tight_layout()
    return fig


def monthly_by_segment(trend: pd.DataFrame, value: str, title: str, ylabel: str, fmt: str = "{x:,.0f}"):
    """Líneas mensuales por segmento (útil cuando hay pocos segmentos, p. ej. datos reales)."""
    fig, ax = _fig()
    segs = trend[["ownership", "vehicle_type"]].drop_duplicates().values.tolist()
    for i, (own, vt) in enumerate(segs[: len(PALETTE)]):
        g = trend[(trend["ownership"] == own) & (trend["vehicle_type"] == vt)].sort_values("month")
        label = segment_label(own, vt)
        ax.plot(g["month"], g[value], color=PALETTE[i], linewidth=2, marker="o", markersize=4, label=label)
        if len(segs) <= 4:
            last = g.iloc[-1]
            ax.annotate(
                label,
                (last["month"], last[value]),
                xytext=(6, 0),
                textcoords="offset points",
                va="center",
                fontsize=8,
                color=TEXT,
            )
    ax.set_xticks(range(1, 13), MONTH_ABBR)
    ax.set_xlim(0.6, 12.9 if len(segs) > 4 else 14.8)
    ax.yaxis.set_major_formatter(mticker.StrMethodFormatter(fmt))
    _style(ax, title, ylabel)
    ax.legend(frameon=False, fontsize=8, ncol=2, loc="upper left", bbox_to_anchor=(0, -0.1))
    fig.tight_layout()
    return fig


def segment_bars(summary: pd.DataFrame, value: str, title: str, xlabel: str, fmt: str = "{:,.2f}"):
    """Barras horizontales por segmento-combustible, coloreadas por combustible."""
    df = summary.dropna(subset=[value]).sort_values(value)
    height = max(2.2, 0.45 * len(df) + 1.2)
    fig, ax = _fig(8, height)
    labels = [
        f"{segment_label(o, v)} · {FUEL_LABELS[f]}" for o, v, f in zip(df["ownership"], df["vehicle_type"], df["fuel"])
    ]
    colors = [FUEL_COLORS[f] for f in df["fuel"]]
    bars = ax.barh(labels, df[value], color=colors, height=0.6, edgecolor=SURFACE, linewidth=2)
    for bar, v in zip(bars, df[value]):
        ax.text(
            bar.get_width(),
            bar.get_y() + bar.get_height() / 2,
            " " + fmt.format(v),
            va="center",
            fontsize=8,
            color=TEXT,
        )
    _style(ax, title)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_xlabel(xlabel, color=MUTED, fontsize=9)
    ax.set_xlim(0, df[value].max() * 1.18 if len(df) else 1)
    fig.tight_layout()
    return fig


def fuel_bars(df: pd.DataFrame, value: str, title: str, xlabel: str, fmt: str = "{:,.0f}"):
    """Barras horizontales por combustible."""
    df = df.sort_values(value)
    fig, ax = _fig(8, max(2.0, 0.45 * len(df) + 1.2))
    bars = ax.barh(
        [FUEL_LABELS[f] for f in df["fuel"]], df[value], color=[FUEL_COLORS[f] for f in df["fuel"]], height=0.6
    )
    for bar, v in zip(bars, df[value]):
        ax.text(
            bar.get_width(),
            bar.get_y() + bar.get_height() / 2,
            " " + fmt.format(v),
            va="center",
            fontsize=8,
            color=TEXT,
        )
    _style(ax, title)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_xlabel(xlabel, color=MUTED, fontsize=9)
    ax.set_xlim(0, df[value].max() * 1.2 if len(df) else 1)
    fig.tight_layout()
    return fig


def to_svg(fig) -> str:
    buf = io.StringIO()
    fig.savefig(buf, format="svg", facecolor=fig.get_facecolor(), metadata={"Date": None})
    plt.close(fig)
    svg = buf.getvalue()
    return svg[svg.find("<svg") :]


def to_png(fig, path) -> None:
    fig.savefig(path, format="png", dpi=150, facecolor=fig.get_facecolor(), metadata={"Software": None})
    plt.close(fig)


def monthly_total(trend: pd.DataFrame, value: str, title: str, ylabel: str, fmt: str = "{x:,.0f}"):
    """Una sola serie mensual (total de la flotilla)."""
    fig, ax = _fig()
    g = trend.sort_values("month")
    ax.plot(g["month"], g[value], color=PALETTE[0], linewidth=2, marker="o", markersize=4)
    ax.set_xticks(range(1, 13), MONTH_ABBR)
    ax.set_xlim(0.6, 12.4)
    ax.yaxis.set_major_formatter(mticker.StrMethodFormatter(fmt))
    _style(ax, title, ylabel)
    fig.tight_layout()
    return fig
