"""
Pestaña de visualización 3D del campo alpha.

Tres modos de vista seleccionables:
    Vista lateral (x-y):   corte en un plano z específico → cámara lateral
    Vista en planta (x-z):  proyección sobre el plano y → cámara superior
    Vista transversal (y-z): corte en un plano x específico → vista de sección

Controles: selector de vista, slider de tiempo, slider de corte z/x, animación.
"""
from __future__ import annotations
import threading
from pathlib import Path
import numpy as np
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QGroupBox, QComboBox, QSizePolicy, QFrame,
    QCheckBox, QMessageBox, QSpinBox, QProgressBar,
)
from PyQt5.QtCore import pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QFont
from core.postprocessing import FoamReader
from core.simulation import SimulationConfig, GeometryConfig
from ui.widgets.plot_widget import PlotWidget


_CMAPS = {
    "Azul (lodo)":      "Blues",
    "Rojo-naranja":     "YlOrRd",
    "Viridis":          "viridis",
    "Grises":           "Greys",
}

_VIEWS = {
    "Vista lateral (x-y)  — cámara lateral":  "lateral",
    "Vista en planta (x-z) — cámara superior": "plan",
    "Corte transversal (y-z) — sección":       "transversal",
}


class FieldViewerWidget(PlotWidget):
    """Canvas matplotlib para visualizar el campo alpha en 3D."""
    def __init__(self, parent=None):
        super().__init__(figsize=(9.,7.), show_toolbar=True, parent=parent)
        self._geo: GeometryConfig | None = None
        self._draw_placeholder()

    def set_geometry(self, geo: GeometryConfig): self._geo = geo

    def render(self, alpha_3d: np.ndarray, time: float,
               view: str="lateral", slice_idx: int=0,
               cmap: str="Blues", show_contour: bool=True) -> None:
        if self._geo is None: return
        g = self._geo
        self.figure.clear()
        ax = self.figure.add_subplot(1,1,1)

        if view == "lateral":
            # Corte en z = slice_idx
            k   = max(0, min(slice_idx, g.nz-1))
            arr = alpha_3d[k, :, :]          # (ny, nx)
            xe  = np.linspace(0, g.length, g.nx+1)
            ye  = np.linspace(0, g.height, g.ny+1)
            mesh = ax.pcolormesh(xe, ye, arr, cmap=cmap, vmin=0, vmax=1, shading="flat")
            if show_contour:
                xc = (xe[:-1]+xe[1:])/2; yc = (ye[:-1]+ye[1:])/2
                try: ax.contour(xc,yc,arr,levels=[0.5],colors=["#FF6B35"],linewidths=[1.5])
                except: pass
            ax.set_xlabel("x [m]", fontsize=9); ax.set_ylabel("y [m]", fontsize=9)
            z_val = (k+0.5)*g.dz
            ax.set_title(f"Vista lateral (x-y)  |  t={time:.4f}s  |  z={z_val:.3f}m",
                         fontsize=9, fontweight="bold")
            ax.set_xlim(0,g.length); ax.set_ylim(0,g.height)
            # Etiquetas de paredes
            off = g.height*0.03
            for txt,x,y,rot in [
                ("lowerWall", g.length/2, -off*2, 0),
                ("atmosphere", g.length/2, g.height+off*0.6, 0),
                ("leftWall", -off*0.5, g.height/2, 90),
                ("rightWall", g.length+off*0.5, g.height/2, 90),
            ]:
                ax.text(x,y,txt,fontsize=6,color="#888",ha="center",rotation=rot)

        elif view == "plan":
            # Proyección: cualquier y tiene fluido → True
            arr = alpha_3d.any(axis=1).astype(float)  # (nz, nx)
            xe  = np.linspace(0, g.length, g.nx+1)
            ze  = np.linspace(0, g.width,  g.nz+1)
            mesh = ax.pcolormesh(xe, ze, arr, cmap=cmap, vmin=0, vmax=1, shading="flat")
            ax.set_xlabel("x [m]", fontsize=9); ax.set_ylabel("z [m]", fontsize=9)
            ax.set_title(f"Vista en planta (x-z) — cámara superior  |  t={time:.4f}s",
                         fontsize=9, fontweight="bold")
            ax.set_xlim(0,g.length); ax.set_ylim(0,g.width)

        elif view == "transversal":
            # Corte en x = slice_idx
            i   = max(0, min(slice_idx, g.nx-1))
            arr = alpha_3d[:, :, i].T      # (ny, nz) → transpose para x=z, y=y
            ze  = np.linspace(0, g.width,  g.nz+1)
            ye  = np.linspace(0, g.height, g.ny+1)
            mesh = ax.pcolormesh(ze, ye, arr, cmap=cmap, vmin=0, vmax=1, shading="flat")
            ax.set_xlabel("z [m]", fontsize=9); ax.set_ylabel("y [m]", fontsize=9)
            x_val = (i+0.5)*g.dx
            ax.set_title(f"Corte transversal (z-y)  |  t={time:.4f}s  |  x={x_val:.3f}m",
                         fontsize=9, fontweight="bold")
            ax.set_xlim(0,g.width); ax.set_ylim(0,g.height)

        cbar = self.figure.colorbar(mesh, ax=ax, fraction=0.03, pad=0.02)
        cbar.set_label("α (fracción volumétrica)", fontsize=8)
        cbar.ax.tick_params(labelsize=7)
        ax.set_aspect("auto"); ax.tick_params(labelsize=8)
        self.canvas.draw()

    def _draw_placeholder(self):
        self.figure.clear()
        ax = self.figure.add_subplot(1,1,1)
        ax.text(0.5,0.5,"Ejecute una simulación y presione\n'Cargar campos α'",
                ha="center",va="center",fontsize=11,color="#AAAAAA",
                transform=ax.transAxes)
        ax.axis("off"); self.canvas.draw()


class VisualizationTab(QWidget):
    log_message    = pyqtSignal(str)
    status_message = pyqtSignal(str)
    _sig_progress  = pyqtSignal(int)
    _sig_ready     = pyqtSignal()
    _sig_status    = pyqtSignal(str)
    _sig_pv_status = pyqtSignal(str)
    _sig_vtk_done  = pyqtSignal(bool, str)
    _sig_pv_err    = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._case_dir  = None
        self._config    = None
        self._times     = []
        self._cache: dict[float, np.ndarray] = {}  # {t → alpha_3d (nz,ny,nx)}
        self._is_playing = False
        self._play_timer = QTimer(); self._play_timer.timeout.connect(self._advance)
        self._setup_ui()
        self._connect_internal()
        self._check_pv_async()

    def _setup_ui(self):
        main = QHBoxLayout(self)
        main.setContentsMargins(8,8,8,8); main.setSpacing(10)

        # ── Panel izquierdo ───────────────────────────────────────────────────
        cw = QWidget(); cw.setFixedWidth(215)
        ctrl = QVBoxLayout(cw); ctrl.setSpacing(8); ctrl.setContentsMargins(0,0,0,0)

        # Carga
        g_load = QGroupBox("Resultados"); g_load.setFont(QFont("Arial",9,QFont.Bold))
        ll = QVBoxLayout(g_load)
        self._btn_load = QPushButton("⟳  Recargar campos α")
        self._btn_load.setFixedHeight(26)
        self._btn_load.setToolTip(
            "Recarga los campos alpha del caso activo.\n"
            "La carga es automática al cargar un caso o ejecutar una simulación."
        )
        self._btn_load.setStyleSheet(
            "QPushButton{background:#F0F4F8;border:1px solid #CBD5E1;"
            "border-radius:4px;font-size:11px;}"
            "QPushButton:hover{background:#E2EAF5;border-color:#2C5F8A;}"
            "QPushButton:disabled{background:#EEE;color:#AAA;}")
        self._btn_load.clicked.connect(self._load_fields)
        ll.addWidget(self._btn_load)
        self._lbl_status = QLabel("Sin resultados cargados")
        self._lbl_status.setWordWrap(True)
        self._lbl_status.setStyleSheet("color:#666;font-size:10px;")
        ll.addWidget(self._lbl_status)

        self._lbl_case_path = QLabel("—")
        self._lbl_case_path.setWordWrap(True)
        self._lbl_case_path.setStyleSheet(
            "color:#2C5F8A; font-size:9px; font-style:italic;")
        ll.addWidget(self._lbl_case_path)
        self._prog = QProgressBar(); self._prog.setRange(0,100); self._prog.setValue(0)
        self._prog.setFixedHeight(7); self._prog.setTextVisible(False)
        self._prog.setStyleSheet("QProgressBar{background:#EEE;border:none;border-radius:3px;}"
                                  "QProgressBar::chunk{background:#2C5F8A;border-radius:3px;}")
        ll.addWidget(self._prog)
        ctrl.addWidget(g_load)

        # Tiempo
        g_time = QGroupBox("Control de tiempo"); g_time.setFont(QFont("Arial",9,QFont.Bold))
        lt = QVBoxLayout(g_time)
        self._lbl_time = QLabel("t = — s")
        self._lbl_time.setAlignment(Qt.AlignCenter)
        self._lbl_time.setFont(QFont("Arial",12,QFont.Bold))
        self._lbl_time.setStyleSheet("color:#2C5F8A;")
        lt.addWidget(self._lbl_time)
        self._slider_t = QSlider(Qt.Horizontal); self._slider_t.setRange(0,0)
        self._slider_t.setEnabled(False); self._slider_t.valueChanged.connect(self._on_time_changed)
        lt.addWidget(self._slider_t)
        self._lbl_step = QLabel("Paso 0 / 0")
        self._lbl_step.setAlignment(Qt.AlignCenter)
        self._lbl_step.setStyleSheet("color:#888;font-size:10px;")
        lt.addWidget(self._lbl_step)
        pr = QHBoxLayout()
        self._btn_first = QPushButton("⏮"); self._btn_prev = QPushButton("◀")
        self._btn_play  = QPushButton("▶  Play")
        self._btn_next  = QPushButton("▶"); self._btn_last = QPushButton("⏭")
        for b in [self._btn_first,self._btn_prev,self._btn_next,self._btn_last]:
            b.setFixedSize(28,26); b.setEnabled(False)
        self._btn_play.setFixedHeight(26); self._btn_play.setEnabled(False)
        self._btn_play.setStyleSheet(
            "QPushButton{background:#1AA870;color:white;border-radius:4px;font-weight:bold;}"
            "QPushButton:hover{background:#15906A;}"
            "QPushButton:disabled{background:#AAA;}")
        self._btn_first.clicked.connect(lambda: self._goto(0))
        self._btn_prev.clicked.connect(lambda: self._goto(self._slider_t.value()-1))
        self._btn_next.clicked.connect(lambda: self._goto(self._slider_t.value()+1))
        self._btn_last.clicked.connect(lambda: self._goto(len(self._times)-1))
        self._btn_play.clicked.connect(self._toggle_play)
        pr.addWidget(self._btn_first); pr.addWidget(self._btn_prev)
        pr.addWidget(self._btn_play,stretch=1)
        pr.addWidget(self._btn_next); pr.addWidget(self._btn_last)
        lt.addLayout(pr)
        fps_row = QHBoxLayout()
        fps_row.addWidget(QLabel("FPS:"))
        self._sb_fps = QSpinBox(); self._sb_fps.setRange(1,30); self._sb_fps.setValue(4)
        self._sb_fps.setFixedWidth(50)
        fps_row.addWidget(self._sb_fps); fps_row.addStretch()
        lt.addLayout(fps_row)
        ctrl.addWidget(g_time)

        # Vista 3D
        g_view = QGroupBox("Vista 3D"); g_view.setFont(QFont("Arial",9,QFont.Bold))
        lv = QVBoxLayout(g_view)
        lv.addWidget(QLabel("Modo de vista:"))
        self._combo_view = QComboBox()
        for label in _VIEWS: self._combo_view.addItem(label, _VIEWS[label])
        self._combo_view.currentIndexChanged.connect(self._on_view_changed)
        lv.addWidget(self._combo_view)

        self._lbl_slice = QLabel("Corte z (capa lateral):")
        self._lbl_slice.setStyleSheet("font-size:10px;color:#666;")
        lv.addWidget(self._lbl_slice)
        self._slider_slice = QSlider(Qt.Horizontal); self._slider_slice.setRange(0,0)
        self._slider_slice.valueChanged.connect(self._refresh_frame)
        lv.addWidget(self._slider_slice)
        self._lbl_slice_val = QLabel("z = —")
        self._lbl_slice_val.setStyleSheet("font-size:10px;color:#2C5F8A;")
        lv.addWidget(self._lbl_slice_val)

        lv.addWidget(QLabel("Mapa de color:"))
        self._combo_cmap = QComboBox()
        for l in _CMAPS: self._combo_cmap.addItem(l, _CMAPS[l])
        self._combo_cmap.currentIndexChanged.connect(self._refresh_frame)
        lv.addWidget(self._combo_cmap)

        self._chk_contour = QCheckBox("Línea de interfaz (α=0.5)")
        self._chk_contour.setChecked(True)
        self._chk_contour.stateChanged.connect(self._refresh_frame)
        lv.addWidget(self._chk_contour)
        ctrl.addWidget(g_view)

        # ParaView
        g_pv = QGroupBox("ParaView"); g_pv.setFont(QFont("Arial",9,QFont.Bold))
        lpv = QVBoxLayout(g_pv)
        self._btn_pv = QPushButton("🔭  Abrir en ParaView")
        self._btn_pv.setFixedHeight(30); self._btn_pv.setEnabled(False)
        self._btn_pv.setStyleSheet(
            "QPushButton{background:#5C3D8F;color:white;border-radius:4px;font-weight:bold;}"
            "QPushButton:hover{background:#7A52B5;}"
            "QPushButton:disabled{background:#AAA;}")
        self._btn_pv.clicked.connect(self._open_pv)
        lpv.addWidget(self._btn_pv)
        self._btn_vtk = QPushButton("⚙  Generar VTK")
        self._btn_vtk.setFixedHeight(26); self._btn_vtk.setEnabled(False)
        self._btn_vtk.clicked.connect(self._run_vtk)
        lpv.addWidget(self._btn_vtk)
        self._btn_browse_pv = QPushButton("📂  Buscar ParaView...")
        self._btn_browse_pv.setFixedHeight(24)
        self._btn_browse_pv.clicked.connect(self._browse_pv)
        lpv.addWidget(self._btn_browse_pv)
        self._lbl_pv = QLabel("Verificando...")
        self._lbl_pv.setStyleSheet("font-size:10px;color:#666;")
        self._lbl_pv.setWordWrap(True)
        lpv.addWidget(self._lbl_pv)
        ctrl.addWidget(g_pv)

        ctrl.addStretch()
        main.addWidget(cw)

        # Separador
        sep = QFrame(); sep.setFrameShape(QFrame.VLine); sep.setStyleSheet("color:#DDD;")
        main.addWidget(sep)

        # Visor
        right = QVBoxLayout()
        lbl = QLabel("Visualización 3D del campo α — Rompimiento de presa")
        lbl.setFont(QFont("Arial",9,QFont.Bold))
        right.addWidget(lbl)
        self._viewer = FieldViewerWidget()
        self._viewer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right.addWidget(self._viewer)
        note = QLabel("α=1: fluido  ·  α=0: aire  ·  Línea naranja: interfaz α=0.5 (solo vista lateral)")
        note.setStyleSheet("color:#888;font-size:10px;font-style:italic;")
        note.setAlignment(Qt.AlignCenter); right.addWidget(note)
        main.addLayout(right, stretch=1)

    def _connect_internal(self):
        self._sig_progress.connect(self._prog.setValue)
        self._sig_ready.connect(self._on_ready)
        self._sig_status.connect(self._lbl_status.setText)
        self._sig_pv_status.connect(self._lbl_pv.setText)
        self._sig_vtk_done.connect(self._on_vtk_done)
        self._sig_pv_err.connect(self._show_pv_err)

    # ── API pública ───────────────────────────────────────────────────────────
    def set_case(self, config: SimulationConfig):
        self._config   = config
        self._case_dir = config.case_dir
        self._viewer.set_geometry(config.geometry)
        geo = config.geometry

        # Configurar slider de corte según la geometría
        self._slider_slice.setRange(0, max(0, geo.nz-1))

        # Habilitar botones
        self._btn_load.setEnabled(True)
        self._btn_pv.setEnabled(True)
        self._btn_vtk.setEnabled(True)

        # Mostrar información del caso
        self._lbl_status.setText(
            f"Caso: {config.name}\n"
            f"Malla: {geo.nx}×{geo.ny}×{geo.nz} = {geo.cell_count:,} celdas"
        )

        # Mostrar ruta completa del directorio
        from pathlib import Path
        path_str = str(self._case_dir)
        # Acortar rutas largas mostrando los últimos dos segmentos
        parts = Path(path_str).parts
        short = ("…/" + "/".join(parts[-2:])) if len(parts) > 2 else path_str
        self._lbl_case_path.setText(short)
        self._lbl_case_path.setToolTip(path_str)

        # Si no existen resultados aún, informar claramente
        if not self._case_dir.exists():
            self._lbl_status.setText(
                f"⚠ Sin resultados en disco\n"
                f"Ejecute la simulación primero."
            )
            self._lbl_status.setStyleSheet("color:#E85A30; font-size:10px;")
            self._btn_load.setEnabled(False)
        else:
            has_times = any(
                d.is_dir() and self._is_time_dir(d.name)
                for d in self._case_dir.iterdir()
            )
            if not has_times:
                self._lbl_status.setText(
                    f"Caso: {config.name}\n"
                    f"⚠ Sin pasos de tiempo — ejecute la simulación."
                )
                self._lbl_status.setStyleSheet("color:#E8A030; font-size:10px;")
                self._btn_load.setEnabled(False)
            else:
                self._lbl_status.setStyleSheet("color:#666; font-size:10px;")

    @staticmethod
    def _is_time_dir(name: str) -> bool:
        """Devuelve True si el nombre de directorio es un número de tiempo > 0."""
        try:
            return float(name) > 0
        except ValueError:
            return False

    # ── Carga ─────────────────────────────────────────────────────────────────
    def _load_fields(self):
        if not self._case_dir: return
        self._btn_load.setEnabled(False)
        self._btn_load.setText("Cargando...")
        self._cache.clear(); self._times = []
        self._sig_progress.emit(0)
        threading.Thread(target=self._load_worker, daemon=True).start()

    def _load_worker(self):
        try:
            cfg        = self._config
            field_name = cfg.alpha_field_name if cfg else "alpha.lodo"
            geo        = cfg.geometry if cfg else None
            reader     = FoamReader(self._case_dir)
            times      = reader.get_time_steps()
            if not times:
                self._sig_status.emit("Sin resultados en el directorio.")
                return

            total = len(times)
            cache: dict[float, np.ndarray] = {}
            for i, t in enumerate(times):
                field = reader.read_scalar_field(t, field_name)
                if field is not None and len(field.values) > 0:
                    alpha_flat = field.values
                    if geo:
                        n3d = geo.nx * geo.ny * geo.nz
                        if len(alpha_flat) == n3d:
                            cache[t] = alpha_flat.reshape(geo.nz, geo.ny, geo.nx)
                        elif len(alpha_flat) == geo.nx * geo.ny:
                            # Cuasi-2D: duplicar en z
                            a2d = alpha_flat.reshape(geo.ny, geo.nx)
                            cache[t] = np.stack([a2d]*geo.nz, axis=0)
                    else:
                        cache[t] = alpha_flat
                self._sig_progress.emit(int((i+1)/total*100))

            self._cache = cache
            self._times = sorted(cache.keys())
            self._sig_ready.emit()
        except Exception as e:
            self._sig_status.emit(f"Error: {e}")

    def _on_ready(self):
        n = len(self._times)
        self._btn_load.setEnabled(True)
        self._btn_load.setText("⟳  Cargar campos α")
        if n == 0:
            self._lbl_status.setText("No se encontraron campos."); return
        self._lbl_status.setText(
            f"✓ {n} pasos cargados\n"
            f"t: [{self._times[0]:.2f} → {self._times[-1]:.2f}] s"
        )
        self._slider_t.setRange(0, n-1); self._slider_t.setValue(0)
        self._slider_t.setEnabled(True)
        for b in [self._btn_first,self._btn_prev,self._btn_next,
                  self._btn_last,self._btn_play]:
            b.setEnabled(True)
        self._goto(0)
        self.log_message.emit(f"✓ Visualización 3D: {n} pasos cargados")

    # ── Navegación ────────────────────────────────────────────────────────────
    def _goto(self, idx):
        if not self._times: return
        idx = max(0, min(idx, len(self._times)-1))
        self._slider_t.setValue(idx)

    def _on_time_changed(self, idx):
        if not self._times or idx >= len(self._times): return
        t = self._times[idx]
        self._lbl_time.setText(f"t = {t:.4f} s")
        self._lbl_step.setText(f"Paso {idx+1} / {len(self._times)}")
        self._render_current(t)

    def _refresh_frame(self):
        self._on_time_changed(self._slider_t.value())

    def _on_view_changed(self, _):
        view = self._combo_view.currentData()
        geo  = self._config.geometry if self._config else None
        if geo:
            if view == "lateral":
                self._lbl_slice.setText(f"Corte z (0..{geo.nz-1}):")
                self._slider_slice.setRange(0, max(0, geo.nz-1))
            elif view == "transversal":
                self._lbl_slice.setText(f"Corte x (0..{geo.nx-1}):")
                self._slider_slice.setRange(0, max(0, geo.nx-1))
            else:
                self._lbl_slice.setText("(sin corte en vista planta)")
        self._refresh_frame()

    def _render_current(self, t: float):
        alpha_3d = self._cache.get(t)
        if alpha_3d is None: return
        view       = self._combo_view.currentData()
        slice_idx  = self._slider_slice.value()
        cmap       = self._combo_cmap.currentData() or "Blues"
        contour    = self._chk_contour.isChecked()

        # Actualizar etiqueta de corte
        geo = self._config.geometry if self._config else None
        if geo and view == "lateral":
            z_val = (slice_idx + 0.5) * geo.dz
            self._lbl_slice_val.setText(f"z = {z_val:.4f} m")
        elif geo and view == "transversal":
            x_val = (slice_idx + 0.5) * geo.dx
            self._lbl_slice_val.setText(f"x = {x_val:.4f} m")
        else:
            self._lbl_slice_val.setText("—")

        self._viewer.render(alpha_3d, t, view, slice_idx, cmap, contour)

    def _toggle_play(self):
        if self._is_playing:
            self._is_playing = False; self._play_timer.stop()
            self._btn_play.setText("▶  Play")
            self._btn_play.setStyleSheet(
                "QPushButton{background:#1AA870;color:white;border-radius:4px;font-weight:bold;}"
                "QPushButton:hover{background:#15906A;}")
        else:
            self._is_playing = True
            self._play_timer.start(1000 // max(1, self._sb_fps.value()))
            self._btn_play.setText("⏸  Pausar")
            self._btn_play.setStyleSheet(
                "QPushButton{background:#E85A30;color:white;border-radius:4px;font-weight:bold;}"
                "QPushButton:hover{background:#D04020;}")

    def _advance(self):
        cur = self._slider_t.value()
        self._goto(0 if cur >= len(self._times)-1 else cur+1)

    # ── ParaView ──────────────────────────────────────────────────────────────
    def _check_pv_async(self):
        def _w():
            from services.paraview_launcher import ParaViewLauncher
            pv = ParaViewLauncher().find_paraview()
            msg = f"✓ {Path(pv).parent.parent.name}" if pv else "⚠ No detectado\nUsa 'Buscar...'"
            self._sig_pv_status.emit(msg)
        threading.Thread(target=_w, daemon=True).start()

    def _open_pv(self):
        if not self._case_dir: return
        def _w():
            from services.paraview_launcher import ParaViewLauncher
            ok = ParaViewLauncher(log_callback=self.log_message.emit).launch(self._case_dir)
            if not ok: self._sig_pv_err.emit()
        threading.Thread(target=_w, daemon=True).start()

    def _run_vtk(self):
        if not self._case_dir: return
        self._btn_vtk.setEnabled(False); self._btn_vtk.setText("⏳ Convirtiendo...")
        def _w():
            from services.paraview_launcher import ParaViewLauncher
            ok = ParaViewLauncher(log_callback=self.log_message.emit).run_foam_to_vtk(
                self._case_dir, fields=["alpha.lodo","U","p_rgh"])
            self._sig_vtk_done.emit(ok, "✓ VTK en VTK/" if ok else "✗ Error VTK")
        threading.Thread(target=_w, daemon=True).start()

    def _on_vtk_done(self, ok, msg):
        self._btn_vtk.setEnabled(True); self._btn_vtk.setText("⚙  Generar VTK")
        self._lbl_pv.setText(msg)

    def _browse_pv(self):
        from PyQt5.QtWidgets import QFileDialog
        from services.paraview_launcher import ParaViewLauncher
        path, _ = QFileDialog.getOpenFileName(
            self, "Localizar ParaView", r"C:\Program Files",
            "ParaView (paraview.exe);;Todos los archivos (*)")
        if path and Path(path).exists():
            ParaViewLauncher.set_custom_path(path)
            self._lbl_pv.setText(f"✓ {Path(path).name}")
            self._lbl_pv.setStyleSheet("font-size:10px;color:#1AA870;font-weight:bold;")
            self.log_message.emit(f"✓ ParaView: {path}")

    def _show_pv_err(self):
        QMessageBox.warning(self, "ParaView no encontrado",
            "Use '📂 Buscar ParaView...' para localizarlo manualmente.")
