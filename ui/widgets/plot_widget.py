"""
Widget base para gráficas matplotlib en PyQt5.

Corrección de layout: usa subplots_adjust manual en lugar de tight_layout
para evitar el warning y las superposiciones en el layout 2×3 de 3D.

Layout:
    2D (is_3d=False) → 2×2 paneles
    3D (is_3d=True)  → 2×3 paneles con heatmap de vista en planta
"""
from __future__ import annotations
import numpy as np
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSizePolicy
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg, NavigationToolbar2QT,
)
from matplotlib.figure import Figure


class PlotWidget(QWidget):
    def __init__(self, figsize=(10., 6.), show_toolbar=True, parent=None):
        super().__init__(parent)
        # NO usar tight_layout en la figura — lo manejamos manualmente
        self.figure = Figure(figsize=figsize)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        if show_toolbar:
            self.toolbar = NavigationToolbar2QT(self.canvas, self)
            lay.addWidget(self.toolbar)
        else:
            self.toolbar = None
        lay.addWidget(self.canvas)

    def clear(self):
        self.figure.clear()
        self.canvas.draw()

    def redraw(self):
        """Redibuja sin tight_layout (el ajuste se hace en render_plot_data)."""
        self.canvas.draw()

    def get_axes(self, nrows=1, ncols=1, **kwargs):
        self.figure.clear()
        if nrows == 1 and ncols == 1:
            return self.figure.add_subplot(1, 1, 1, **kwargs)
        return self.figure.subplots(nrows, ncols, **kwargs)

    def save_png(self, path, dpi=150):
        self.figure.savefig(path, dpi=dpi, bbox_inches="tight")

    def render_plot_data(self, plot_data: dict) -> None:
        ptype = plot_data.get("type", "single")
        if ptype == "single":
            self._render_single(plot_data)
        elif ptype == "comparison":
            self._render_comparison(plot_data)
        self.canvas.draw()

    # ── Layout adaptativo ─────────────────────────────────────────────────────

    def _render_single(self, data: dict) -> None:
        panels  = data.get("panels", {})
        cfg     = data.get("plot_config", {})
        is_3d   = data.get("is_3d", False)
        title   = data.get("title", "")

        self.figure.clear()

        if is_3d:
            # 2×3: 6 paneles para simulación 3D
            axes = self.figure.subplots(2, 3)
            # Márgenes amplios para evitar solapamiento de etiquetas
            self.figure.subplots_adjust(
                left=0.07, right=0.97,
                top=0.88,  bottom=0.10,
                hspace=0.55, wspace=0.42,
            )
            panel_order = [
                "front_position", "front_velocity",
                "fluid_volume",   "height_profile",
                "plan_view",      "transversal",
            ]
            fs_title = 8    # fontsize reducido para 6 paneles
            fs_label = 7
            fs_tick  = 6
            fs_leg   = 6
            lw       = 1.5
            ms       = 3.0
        else:
            # 2×2: 4 paneles para simulación 2D
            axes = self.figure.subplots(2, 2)
            self.figure.subplots_adjust(
                left=0.09, right=0.97,
                top=0.90,  bottom=0.10,
                hspace=0.45, wspace=0.38,
            )
            panel_order = [
                "front_position", "front_velocity",
                "fluid_volume",   "height_profile",
            ]
            fs_title = 9
            fs_label = 8
            fs_tick  = 7
            fs_leg   = 7
            lw       = cfg.get("line_width", 2.0)
            ms       = cfg.get("marker_size", 4.0)

        # Título general
        self.figure.suptitle(title, fontsize=10, fontweight="bold", y=0.98)

        for ax, key in zip(axes.ravel(), panel_order):
            panel = panels.get(key, {})
            if not panel:
                ax.set_visible(False)
                continue

            # Heatmap (vista en planta)
            if panel.get("type") == "heatmap":
                self._render_heatmap(ax, panel, fs_title, fs_label, fs_tick)
                continue

            # No mostrar paneles 3D sin datos en modo 2D
            if panel.get("is_3d") and not is_3d:
                ax.set_visible(False)
                continue

            # Series de líneas
            series = panel.get("series", [])
            if not series:
                ax.set_visible(False)
                continue

            for s in series:
                if not s:
                    continue
                xd = s.get("x", [])
                yd = s.get("y", [])
                if not xd or not yd or len(xd) != len(yd):
                    continue
                ax.plot(
                    xd, yd,
                    s.get("style", "-"),
                    color      = s.get("color", "#2C5F8A"),
                    linewidth  = lw,
                    markersize = ms,
                    label      = s.get("label", ""),
                    alpha      = s.get("alpha", 1.0),
                )
                if s.get("fill"):
                    ax.fill_between(xd, yd, alpha=0.2,
                                    color=s.get("color", "#2C5F8A"))

            ax.set_title(panel.get("title", key), fontsize=fs_title, pad=3)
            ax.set_xlabel(panel.get("xlabel", ""), fontsize=fs_label, labelpad=2)
            ax.set_ylabel(panel.get("ylabel", ""), fontsize=fs_label, labelpad=2)
            ax.tick_params(labelsize=fs_tick)

            if cfg.get("show_grid", True):
                ax.grid(True, alpha=0.3, linestyle="--", linewidth=0.5)

            # Leyenda solo si hay etiquetas y no son demasiadas
            if cfg.get("show_legend", True) and series:
                labeled = [s for s in series if s.get("label")]
                if 0 < len(labeled) <= 6:
                    ax.legend(fontsize=fs_leg, loc="best",
                              framealpha=0.7, handlelength=1.2)
                elif len(labeled) > 6:
                    # Demasiadas curvas: mostrar solo la primera y última
                    ax.legend(fontsize=fs_leg, loc="best",
                              framealpha=0.7, handlelength=1.2,
                              ncol=2)

    def _render_heatmap(
        self,
        ax,
        panel: dict,
        fs_title: int,
        fs_label: int,
        fs_tick:  int,
    ) -> None:
        """Renderiza la vista en planta como heatmap pcolormesh(x,z)."""
        plan_data = panel.get("data")
        ax.set_title(panel.get("title", "Vista en planta"),
                     fontsize=fs_title, pad=3)

        if not plan_data:
            ax.text(0.5, 0.5,
                    "Sin datos 3D\n(requiere nz ≥ 2)",
                    ha="center", va="center", fontsize=8, color="#AAA",
                    transform=ax.transAxes)
            ax.axis("off")
            return

        arr     = np.array(plan_data["array"])          # (nz, nx)
        x_edges = np.array(plan_data["x_edges"])        # (nx+1,)
        z_edges = np.array(plan_data["z_edges"])        # (nz+1,)

        mesh = ax.pcolormesh(
            x_edges, z_edges, arr,
            cmap    = "Blues",
            vmin    = 0.0,
            vmax    = 1.0,
            shading = "flat",
        )
        # Colorbar compacta
        cbar = self.figure.colorbar(mesh, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label("α", fontsize=fs_tick + 1)
        cbar.ax.tick_params(labelsize=fs_tick - 1)

        L = plan_data.get("domain_length", x_edges[-1])
        W = plan_data.get("domain_width",  z_edges[-1])
        t = plan_data.get("time", 0)

        ax.set_xlabel("x [m]", fontsize=fs_label, labelpad=2)
        ax.set_ylabel("z [m]", fontsize=fs_label, labelpad=2)
        ax.tick_params(labelsize=fs_tick)
        ax.set_xlim(0, L)
        ax.set_ylim(0, W)
        ax.set_aspect("auto")
        ax.text(
            0.97, 0.96, f"t={t:.2f}s",
            transform   = ax.transAxes,
            ha          = "right",
            va          = "top",
            fontsize    = fs_tick + 1,
            bbox        = dict(boxstyle="round,pad=0.2",
                               facecolor="white",
                               edgecolor="#CCC",
                               alpha=0.85),
        )

    def _render_comparison(self, data: dict) -> None:
        self.figure.clear()
        ax  = self.figure.add_subplot(1, 1, 1)
        self.figure.subplots_adjust(
            left=0.09, right=0.97, top=0.90, bottom=0.10
        )
        cfg = data.get("plot_config", {})

        ax.set_title(data.get("title", ""), fontsize=10, fontweight="bold")
        ax.set_xlabel(data.get("xlabel", "Tiempo [s]"), fontsize=9)
        ax.set_ylabel(data.get("ylabel", ""), fontsize=9)

        for s in data.get("series", []):
            xd, yd = s.get("x", []), s.get("y", [])
            if not xd or not yd:
                continue
            ax.plot(
                xd, yd,
                s.get("style", "-o"),
                color      = s.get("color", "#2C5F8A"),
                linewidth  = cfg.get("line_width", 2.0),
                markersize = cfg.get("marker_size", 4.0),
                label      = s.get("label", ""),
                alpha      = 0.85 if s.get("type") == "experimental" else 1.0,
            )

        if cfg.get("show_grid", True):
            ax.grid(True, alpha=0.3, linestyle="--")
        if cfg.get("show_legend", True):
            ax.legend(fontsize=8)

    # ── Panel único (modo selector de la pestaña Resultados) ──────────────────

    def render_single_panel(
        self,
        panel_key:  str,
        panel_data: dict,
        cfg:        dict,
        is_3d:      bool = False,
        supertitle: str  = "",
    ) -> None:
        """
        Renderiza UN solo panel ocupando toda la figura.

        Llamado desde ResultsTab cuando el usuario cambia el combo selector.

        Args:
            panel_key:  Clave del panel ('front_position', 'plan_view', etc.)
            panel_data: Dict con 'series', 'title', 'xlabel', 'ylabel' o
                        'type'='heatmap' para la vista en planta.
            cfg:        Dict de configuración visual (grid, legend, lw, ms).
            is_3d:      Si la simulación es 3D (afecta al heatmap).
            supertitle: Título general de la simulación (nombre + fluido).
        """
        self.figure.clear()

        if not panel_data:
            ax = self.figure.add_subplot(1, 1, 1)
            ax.text(0.5, 0.5, "Sin datos para esta gráfica",
                    ha="center", va="center", fontsize=11,
                    color="#AAAAAA", transform=ax.transAxes)
            ax.axis("off")
            self.canvas.draw()
            return

        ax = self.figure.add_subplot(1, 1, 1)
        self.figure.subplots_adjust(
            left=0.09, right=0.97, top=0.88, bottom=0.10
        )

        if supertitle:
            self.figure.suptitle(supertitle, fontsize=10,
                                 fontweight="bold", y=0.97)

        # ── Heatmap (vista en planta) ─────────────────────────────────────────
        if panel_data.get("type") == "heatmap":
            plan_data = panel_data.get("data")
            ax.set_title(panel_data.get("title", "Vista en planta"),
                         fontsize=10, pad=6)

            if not plan_data:
                ax.text(0.5, 0.5, "Sin datos 3D\n(requiere nz ≥ 2)",
                        ha="center", va="center", fontsize=11,
                        color="#AAAAAA", transform=ax.transAxes)
                ax.axis("off")
                self.canvas.draw()
                return

            arr     = np.array(plan_data["array"])
            x_edges = np.array(plan_data["x_edges"])
            z_edges = np.array(plan_data["z_edges"])

            mesh = ax.pcolormesh(x_edges, z_edges, arr,
                                 cmap="Blues", vmin=0, vmax=1,
                                 shading="flat")
            cbar = self.figure.colorbar(mesh, ax=ax, fraction=0.03, pad=0.02)
            cbar.set_label("α (fracción volumétrica)", fontsize=9)
            cbar.ax.tick_params(labelsize=8)

            L = plan_data.get("domain_length", x_edges[-1])
            W = plan_data.get("domain_width",  z_edges[-1])
            t = plan_data.get("time", 0)

            ax.set_xlabel("Posición x [m]", fontsize=9, labelpad=4)
            ax.set_ylabel("Posición z [m]", fontsize=9, labelpad=4)
            ax.tick_params(labelsize=8)
            ax.set_xlim(0, L); ax.set_ylim(0, W)
            ax.set_aspect("auto")
            ax.text(0.98, 0.96, f"t = {t:.4f} s",
                    transform=ax.transAxes, ha="right", va="top",
                    fontsize=9,
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                              edgecolor="#CCC", alpha=0.9))
            if cfg.get("show_grid", True):
                ax.grid(True, alpha=0.2, linestyle="--", linewidth=0.5)
            self.canvas.draw()
            return

        # ── Series de líneas ──────────────────────────────────────────────────
        series = panel_data.get("series", [])
        lw = cfg.get("line_width",  2.0)
        ms = cfg.get("marker_size", 4.0)

        n_series = len([s for s in series if s and s.get("x")])

        for s in series:
            if not s:
                continue
            xd = s.get("x", [])
            yd = s.get("y", [])
            if not xd or not yd or len(xd) != len(yd):
                continue
            ax.plot(
                xd, yd,
                s.get("style", "-"),
                color      = s.get("color", "#2C5F8A"),
                linewidth  = lw,
                markersize = ms,
                label      = s.get("label", ""),
                alpha      = s.get("alpha", 1.0),
            )
            if s.get("fill"):
                ax.fill_between(xd, yd, alpha=0.15,
                                color=s.get("color", "#2C5F8A"))

        ax.set_title(panel_data.get("title", panel_key),
                     fontsize=10, pad=6)
        ax.set_xlabel(panel_data.get("xlabel", ""), fontsize=9, labelpad=4)
        ax.set_ylabel(panel_data.get("ylabel", ""), fontsize=9, labelpad=4)
        ax.tick_params(labelsize=8)

        if cfg.get("show_grid", True):
            ax.grid(True, alpha=0.3, linestyle="--", linewidth=0.6)

        # Leyenda: mostrar solo si hay pocas curvas o con scroll de ncol
        if cfg.get("show_legend", True) and n_series > 0:
            labeled = [s for s in series if s and s.get("label")]
            if 0 < len(labeled) <= 8:
                ax.legend(fontsize=8, loc="best",
                          framealpha=0.8, handlelength=1.5)
            elif len(labeled) > 8:
                # Muchas curvas (perfiles temporales): leyenda exterior derecha
                ax.legend(fontsize=7, loc="upper left",
                          bbox_to_anchor=(1.01, 1), borderaxespad=0,
                          framealpha=0.8, handlelength=1.2, ncol=1)
                self.figure.subplots_adjust(right=0.82)

        self.canvas.draw()
