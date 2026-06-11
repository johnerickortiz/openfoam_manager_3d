"""
Widget de previsualización 3D con dos vistas simultáneas.

Vista lateral (x-y): perfil del fluido — comparable con cámara lateral del experimento.
Vista en planta (x-z): distribución transversal — comparable con cámara superior.

Ambas vistas se actualizan simultáneamente con los mismos datos de PreviewData.
"""
from __future__ import annotations
import matplotlib.patches as mpatches
from ui.widgets.plot_widget import PlotWidget

CLR_DOMAIN = "#F0F4F8"
CLR_DOM_B  = "#2C5F8A"
CLR_DAM    = "#4A90D9"
CLR_DAM_B  = "#1A5A9A"
CLR_GRID   = "#D0D8E0"
CLR_ANNOT  = "#333333"


class GeometryPreviewWidget(PlotWidget):
    """
    Previsualización geométrica 3D con vista lateral (x-y) y en planta (x-z).
    """

    def __init__(self, parent=None) -> None:
        super().__init__(figsize=(10.0, 4.5), show_toolbar=False, parent=parent)
        self._draw_placeholder()

    def render_preview(self, preview_data: dict) -> None:
        self.figure.clear()
        axes = self.figure.subplots(1, 2)
        self._draw_lateral(axes[0], preview_data)
        self._draw_plan(axes[1], preview_data)
        self.figure.tight_layout(pad=1.5)
        self.canvas.draw()

    # ── Vista lateral (x-y) ───────────────────────────────────────────────────
    def _draw_lateral(self, ax, p: dict) -> None:
        L, H = p["domain_length"], p["domain_height"]
        dw, dh = p["dam_length"], p["dam_height"]

        ax.add_patch(mpatches.FancyBboxPatch(
            (0,0), L, H, boxstyle="square,pad=0",
            facecolor=CLR_DOMAIN, edgecolor=CLR_DOM_B, linewidth=1.5))

        for x in p.get("lateral_grid_x", []):
            ax.axvline(x=x, color=CLR_GRID, linewidth=0.4, zorder=1)
        for y in p.get("lateral_grid_y", []):
            ax.axhline(y=y, color=CLR_GRID, linewidth=0.4, zorder=1)

        ax.add_patch(mpatches.FancyBboxPatch(
            (0,0), dw, dh, boxstyle="square,pad=0",
            facecolor=CLR_DAM, edgecolor=CLR_DAM_B,
            linewidth=1.2, alpha=0.75, zorder=3))

        ax.text(dw/2, dh/2, "fluido", ha="center", va="center",
                fontsize=7, color="white", fontweight="bold", zorder=4)

        off = H * 0.07
        ax.annotate("", xy=(L,-off*0.5), xytext=(0,-off*0.5),
                    arrowprops=dict(arrowstyle="<->", color=CLR_ANNOT, lw=0.8))
        ax.text(L/2, -off*0.85, f"L={L:.3f}m", ha="center",
                va="top", fontsize=7, color=CLR_ANNOT)
        ax.annotate("", xy=(-off*0.5,H), xytext=(-off*0.5,0),
                    arrowprops=dict(arrowstyle="<->", color=CLR_ANNOT, lw=0.8))
        ax.text(-off*0.7, H/2, f"H={H:.3f}m", ha="right", va="center",
                fontsize=7, color=CLR_ANNOT, rotation=90)

        gi = p.get
        info = (f"nx={p['nx']} × ny={p['ny']}\n"
                f"Δx={p['dx']*1000:.1f}mm  Δy={p['dy']*1000:.1f}mm")
        ax.text(L*0.98, H*0.97, info, ha="right", va="top", fontsize=6.5,
                color=CLR_ANNOT,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                          edgecolor="#CCC", alpha=0.85), zorder=5)

        ax.set_xlim(-L*0.18, L*1.06)
        ax.set_ylim(-H*0.20, H*1.12)
        ax.set_aspect("auto")
        ax.axis("off")
        ax.set_title("Vista lateral (x-y)", fontsize=8, fontweight="bold",
                     color="#333", pad=3)

    # ── Vista en planta (x-z) ─────────────────────────────────────────────────
    def _draw_plan(self, ax, p: dict) -> None:
        L, W = p["domain_length"], p["domain_width"]
        dw   = p["dam_length"]

        ax.add_patch(mpatches.FancyBboxPatch(
            (0,0), L, W, boxstyle="square,pad=0",
            facecolor=CLR_DOMAIN, edgecolor=CLR_DOM_B, linewidth=1.5))

        for x in p.get("plan_grid_x", []):
            ax.axvline(x=x, color=CLR_GRID, linewidth=0.4, zorder=1)
        for z in p.get("plan_grid_z", []):
            ax.axhline(y=z, color=CLR_GRID, linewidth=0.4, zorder=1)

        ax.add_patch(mpatches.FancyBboxPatch(
            (0,0), dw, W, boxstyle="square,pad=0",
            facecolor=CLR_DAM, edgecolor=CLR_DAM_B,
            linewidth=1.2, alpha=0.75, zorder=3))

        ax.text(dw/2, W/2, "fluido\n(todo el ancho)",
                ha="center", va="center", fontsize=6.5,
                color="white", fontweight="bold", zorder=4)

        off_x = L * 0.07
        off_z = W * 0.15

        ax.annotate("", xy=(L,-off_z*0.5), xytext=(0,-off_z*0.5),
                    arrowprops=dict(arrowstyle="<->", color=CLR_ANNOT, lw=0.8))
        ax.text(L/2, -off_z*0.85, f"L={L:.3f}m", ha="center",
                va="top", fontsize=7, color=CLR_ANNOT)
        ax.annotate("", xy=(-off_x*0.5,W), xytext=(-off_x*0.5,0),
                    arrowprops=dict(arrowstyle="<->", color=CLR_ANNOT, lw=0.8))
        ax.text(-off_x*0.7, W/2, f"W={W:.3f}m", ha="right", va="center",
                fontsize=7, color=CLR_ANNOT, rotation=90)

        info = (f"nx={p['nx']} × nz={p['nz']}\n"
                f"Δx={p['dx']*1000:.1f}mm  Δz={p['dz']*1000:.1f}mm")
        ax.text(L*0.98, W*0.97, info, ha="right", va="top", fontsize=6.5,
                color=CLR_ANNOT,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                          edgecolor="#CCC", alpha=0.85), zorder=5)

        ax.set_xlim(-L*0.18, L*1.06)
        ax.set_ylim(-W*0.60, W*1.18)
        ax.set_aspect("auto")
        ax.axis("off")
        ax.set_title("Vista en planta (x-z) — cámara superior",
                     fontsize=8, fontweight="bold", color="#333", pad=3)

    def _draw_placeholder(self) -> None:
        self.figure.clear()
        ax = self.figure.add_subplot(1,1,1)
        ax.text(0.5, 0.5,
                "Configure los parámetros geométricos\n"
                "para ver la previsualización",
                ha="center", va="center", fontsize=10,
                color="#AAAAAA", transform=ax.transAxes)
        ax.axis("off")
        self.canvas.draw()
