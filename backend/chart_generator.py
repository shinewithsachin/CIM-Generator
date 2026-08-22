"""
Generate matplotlib charts from chart_data dicts.
Returns path to saved PNG image.
"""
import os
import uuid
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from typing import Dict, Any, Optional

from config import settings

COLORS = [
    "#2563EB", "#10B981", "#F59E0B", "#EF4444",
    "#8B5CF6", "#06B6D4", "#F97316", "#EC4899",
    "#14B8A6", "#84CC16",
]


def generate_chart(chart_data: Dict[str, Any], output_dir: Optional[str] = None) -> Optional[str]:
    """Generate a chart PNG from chart_data dict. Returns the file path or None on error."""
    try:
        output_dir = output_dir or settings.output_dir
        os.makedirs(output_dir, exist_ok=True)
        chart_id = chart_data.get("id", str(uuid.uuid4())[:8])
        output_path = os.path.join(output_dir, f"chart_{chart_id}.png")

        chart_type = chart_data.get("type", "bar").lower()

        if chart_type in ("bar", "grouped_bar"):
            _bar_chart(chart_data, output_path)
        elif chart_type == "line":
            _line_chart(chart_data, output_path)
        elif chart_type == "area":
            _area_chart(chart_data, output_path)
        elif chart_type in ("pie", "donut"):
            _pie_chart(chart_data, output_path, donut=(chart_type == "donut"))
        elif chart_type == "waterfall":
            _waterfall_chart(chart_data, output_path)
        elif chart_type == "horizontal_bar":
            _horizontal_bar_chart(chart_data, output_path)
        else:
            _bar_chart(chart_data, output_path)

        return output_path if os.path.exists(output_path) else None
    except Exception as e:
        print(f"Chart generation error: {e}")
        return None


def _setup_fig(title: str, figsize=(10, 6)):
    fig, ax = plt.subplots(figsize=figsize, facecolor="white")
    ax.set_facecolor("#F8FAFC")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#CBD5E1")
    ax.spines["bottom"].set_color("#CBD5E1")
    ax.tick_params(colors="#64748B", labelsize=10)
    if title:
        ax.set_title(title, fontsize=13, fontweight="bold", color="#1E293B", pad=15)
    return fig, ax


def _bar_chart(data: dict, path: str):
    labels = data.get("labels", [])
    datasets = data.get("datasets", [])
    title = data.get("title", "")
    x_label = data.get("x_label", "")
    y_label = data.get("y_label", "")

    fig, ax = _setup_fig(title)
    n_groups = len(labels)
    n_series = len(datasets)
    bar_width = 0.8 / max(n_series, 1)
    x = np.arange(n_groups)

    for i, ds in enumerate(datasets):
        offset = (i - n_series / 2 + 0.5) * bar_width
        color = ds.get("color", COLORS[i % len(COLORS)])
        bars = ax.bar(x + offset, ds.get("data", []), bar_width * 0.9,
                      label=ds.get("label", ""), color=color, alpha=0.85, zorder=3)
        for bar in bars:
            h = bar.get_height()
            if h != 0:
                ax.text(bar.get_x() + bar.get_width() / 2., h + h * 0.01,
                        _fmt_val(h), ha="center", va="bottom", fontsize=8, color="#475569")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_xlabel(x_label, color="#475569", fontsize=10)
    ax.set_ylabel(y_label, color="#475569", fontsize=10)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: _fmt_val(v)))
    ax.grid(axis="y", alpha=0.4, zorder=0)
    if n_series > 1:
        ax.legend(fontsize=9, framealpha=0.7)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _line_chart(data: dict, path: str):
    labels = data.get("labels", [])
    datasets = data.get("datasets", [])
    title = data.get("title", "")
    x_label = data.get("x_label", "")
    y_label = data.get("y_label", "")

    fig, ax = _setup_fig(title)
    x = np.arange(len(labels))

    for i, ds in enumerate(datasets):
        color = ds.get("color", COLORS[i % len(COLORS)])
        vals = ds.get("data", [])
        ax.plot(x, vals, marker="o", linewidth=2.5, color=color,
                label=ds.get("label", ""), markersize=7, zorder=3)
        for xi, yi in zip(x, vals):
            ax.annotate(_fmt_val(yi), (xi, yi), textcoords="offset points",
                        xytext=(0, 8), ha="center", fontsize=8, color="#475569")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_xlabel(x_label, color="#475569", fontsize=10)
    ax.set_ylabel(y_label, color="#475569", fontsize=10)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: _fmt_val(v)))
    ax.grid(alpha=0.3, zorder=0)
    if len(datasets) > 1:
        ax.legend(fontsize=9, framealpha=0.7)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _area_chart(data: dict, path: str):
    labels = data.get("labels", [])
    datasets = data.get("datasets", [])
    title = data.get("title", "")

    fig, ax = _setup_fig(title)
    x = np.arange(len(labels))

    for i, ds in enumerate(datasets):
        color = ds.get("color", COLORS[i % len(COLORS)])
        vals = ds.get("data", [])
        ax.fill_between(x, vals, alpha=0.3, color=color)
        ax.plot(x, vals, linewidth=2, color=color, label=ds.get("label", ""))

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.grid(alpha=0.3)
    if len(datasets) > 1:
        ax.legend(fontsize=9)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _pie_chart(data: dict, path: str, donut: bool = False):
    labels = data.get("labels", [])
    datasets = data.get("datasets", [])
    title = data.get("title", "")
    values = datasets[0].get("data", []) if datasets else []
    colors_list = [COLORS[i % len(COLORS)] for i in range(len(labels))]

    fig, ax = plt.subplots(figsize=(9, 6), facecolor="white")
    wedge_props = {"linewidth": 2, "edgecolor": "white"}
    if donut:
        wedge_props["width"] = 0.45

    wedges, texts, autotexts = ax.pie(
        values, labels=None, colors=colors_list,
        autopct="%1.1f%%", startangle=90,
        wedgeprops=wedge_props, pctdistance=0.75 if donut else 0.6,
    )
    for at in autotexts:
        at.set_fontsize(9)
        at.set_color("white" if donut else "#1E293B")
        at.set_fontweight("bold")

    ax.legend(wedges, labels, loc="center left", bbox_to_anchor=(0.9, 0, 0.5, 1),
              fontsize=9, framealpha=0.7)
    if title:
        ax.set_title(title, fontsize=13, fontweight="bold", color="#1E293B", pad=15)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _waterfall_chart(data: dict, path: str):
    labels = data.get("labels", [])
    datasets = data.get("datasets", [])
    title = data.get("title", "")
    values = datasets[0].get("data", []) if datasets else []

    fig, ax = _setup_fig(title, figsize=(max(10, len(labels) * 1.2), 6))
    running_total = 0
    bottoms = []
    colors_wf = []

    for v in values:
        bottoms.append(running_total if v >= 0 else running_total + v)
        colors_wf.append("#10B981" if v >= 0 else "#EF4444")
        running_total += v

    x = np.arange(len(labels))
    bars = ax.bar(x, [abs(v) for v in values], bottom=bottoms, color=colors_wf, alpha=0.85, width=0.6)
    # connector lines
    for i in range(len(values) - 1):
        top = bottoms[i] + abs(values[i]) if values[i] >= 0 else bottoms[i]
        ax.plot([i + 0.3, i + 0.7], [top, top], "k-", linewidth=0.8, alpha=0.5)

    for bar, v in zip(bars, values):
        y = bar.get_y() + bar.get_height() + (0.3 if v >= 0 else -0.3)
        ax.text(bar.get_x() + bar.get_width() / 2., y, _fmt_val(v),
                ha="center", va="bottom" if v >= 0 else "top", fontsize=8, color="#475569")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: _fmt_val(v)))
    ax.grid(axis="y", alpha=0.3)
    pos_patch = mpatches.Patch(color="#10B981", label="Increase")
    neg_patch = mpatches.Patch(color="#EF4444", label="Decrease")
    ax.legend(handles=[pos_patch, neg_patch], fontsize=9)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _horizontal_bar_chart(data: dict, path: str):
    labels = data.get("labels", [])
    datasets = data.get("datasets", [])
    title = data.get("title", "")
    values = datasets[0].get("data", []) if datasets else []
    color = datasets[0].get("color", COLORS[0]) if datasets else COLORS[0]

    fig, ax = _setup_fig(title, figsize=(10, max(5, len(labels) * 0.5)))
    y = np.arange(len(labels))
    bars = ax.barh(y, values, color=color, alpha=0.85)
    for bar in bars:
        ax.text(bar.get_width() + bar.get_width() * 0.01, bar.get_y() + bar.get_height() / 2.,
                _fmt_val(bar.get_width()), va="center", fontsize=8, color="#475569")
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _fmt_val(v: float) -> str:
    if abs(v) >= 1_000_000_000:
        return f"{v/1_000_000_000:.1f}B"
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:.1f}M"
    if abs(v) >= 1_000:
        return f"{v/1_000:.1f}K"
    if v == int(v):
        return str(int(v))
    return f"{v:.1f}"
