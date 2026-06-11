"""
Pestañas de configuración geométrica y de simulación.

GeometryTab:   formulario + previsualización reactiva en tiempo real.
SimulationTab: parámetros de tiempo, solver y directorio de salida.
"""
from __future__ import annotations

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QDoubleSpinBox, QSpinBox, QGroupBox,
    QSizePolicy, QFrame, QComboBox, QLineEdit,
    QPushButton, QFileDialog, QSlider,
)
from PyQt5.QtCore import pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QFont

from core.simulation import GeometryConfig, SimulationConfig
from core.simulation.simulation_config import TurbulenceModel
from ui.widgets.geometry_preview_widget import GeometryPreviewWidget


# ── GeometryTab ───────────────────────────────────────────────────────────────

class GeometryTab(QWidget):
    """
    Pestaña de configuración geométrica con previsualización en tiempo real.

    Panel izquierdo: formulario de parámetros (L, H, espesor, nx, ny, presa).
    Panel derecho:   GeometryPreviewWidget que se actualiza reactivamente.

    La previsualización se actualiza directamente desde el formulario llamando
    a GeometryConfig.compute_preview() — sin pasar por el controlador.

    Señales:
        geometry_changed(GeometryConfig): Emitida cuando cambian los parámetros.
    """

    geometry_changed = pyqtSignal(object)  # GeometryConfig

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Timer para debounce (evitar recalcular en cada tecla)
        self._preview_timer = QTimer()
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._update_preview)
        self._setup_ui()
        self._update_preview()  # Preview inicial

    def _setup_ui(self) -> None:
        main = QHBoxLayout(self)
        main.setContentsMargins(16, 16, 16, 16)
        main.setSpacing(16)

        # ── Panel izquierdo: formulario ───────────────────────────────────────
        left = QVBoxLayout()
        left.setSpacing(12)

        # Dimensiones del dominio
        dim_group = QGroupBox("Dimensiones del dominio")
        dim_group.setFont(QFont("Arial", 9, QFont.Bold))
        dim_form = QFormLayout(dim_group)
        dim_form.setSpacing(8)
        dim_form.setLabelAlignment(Qt.AlignRight)

        self._sb_L = self._make_spin(0.584, 0.01, 50.0, 3, " m",
                                      "Longitud del canal [m]")
        self._sb_H = self._make_spin(0.584, 0.01, 20.0, 3, " m",
                                      "Altura del dominio [m]")
        self._sb_depth = self._make_spin(0.0146, 0.001, 1.0, 4, " m",
                                          "Espesor cuasi-2D [m]")

        dim_form.addRow("Longitud L:", self._sb_L)
        dim_form.addRow("Altura H:", self._sb_H)
        dim_form.addRow("Espesor (z):", self._sb_depth)
        left.addWidget(dim_group)

        # Resolución de malla
        mesh_group = QGroupBox("Resolución de malla")
        mesh_group.setFont(QFont("Arial", 9, QFont.Bold))
        mesh_form = QFormLayout(mesh_group)
        mesh_form.setSpacing(8)
        mesh_form.setLabelAlignment(Qt.AlignRight)

        self._sb_nx = self._make_int_spin(40, 4, 500, "Celdas en dirección X")
        self._sb_ny = self._make_int_spin(40, 4, 500, "Celdas en dirección Y")

        mesh_form.addRow("nx (celdas en x):", self._sb_nx)
        mesh_form.addRow("ny (celdas en y):", self._sb_ny)

        # Etiqueta de tamaño de celda (calculada automáticamente)
        self._lbl_cell_size = QLabel("Δx = 1.46 cm,  Δy = 1.46 cm")
        self._lbl_cell_size.setStyleSheet("color: #555; font-size: 10px;")
        mesh_form.addRow("Tamaño celda:", self._lbl_cell_size)

        # Etiqueta de total de celdas
        self._lbl_ncells = QLabel("Total: 1,600 celdas")
        self._lbl_ncells.setStyleSheet("color: #2C5F8A; font-size: 10px; font-weight: bold;")
        mesh_form.addRow("Total:", self._lbl_ncells)
        left.addWidget(mesh_group)

        # Posición inicial de la presa
        dam_group = QGroupBox("Columna inicial de fluido (presa)")
        dam_group.setFont(QFont("Arial", 9, QFont.Bold))
        dam_form = QFormLayout(dam_group)
        dam_form.setSpacing(8)
        dam_form.setLabelAlignment(Qt.AlignRight)

        self._sb_dam_w = self._make_spin(25.0, 1.0, 99.0, 1, " %",
                                          "Fracción del ancho ocupada por la presa")
        self._sb_dam_h = self._make_spin(50.0, 1.0, 99.0, 1, " %",
                                          "Fracción de la altura ocupada por la presa")

        dam_form.addRow("Ancho (% de L):", self._sb_dam_w)
        dam_form.addRow("Alto (% de H):", self._sb_dam_h)
        left.addWidget(dam_group)

        left.addStretch()
        main.addLayout(left, stretch=1)

        # ── Separador ─────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #DDD;")
        main.addWidget(sep)

        # ── Panel derecho: previsualización ───────────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(6)

        lbl = QLabel("Previsualización de geometría")
        lbl.setFont(QFont("Arial", 9, QFont.Bold))
        right.addWidget(lbl)

        self._preview = GeometryPreviewWidget()
        self._preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right.addWidget(self._preview)

        main.addLayout(right, stretch=1)

        # Conectar señales
        for sb in [self._sb_L, self._sb_H, self._sb_depth,
                   self._sb_dam_w, self._sb_dam_h]:
            sb.valueChanged.connect(self._schedule_preview)

        for sb in [self._sb_nx, self._sb_ny]:
            sb.valueChanged.connect(self._schedule_preview)

    # ── Helpers para crear spinboxes ──────────────────────────────────────────

    @staticmethod
    def _make_spin(val, min_v, max_v, dec, suffix, tooltip="") -> QDoubleSpinBox:
        sb = QDoubleSpinBox()
        sb.setDecimals(dec)
        sb.setRange(min_v, max_v)
        sb.setValue(val)
        sb.setSuffix(suffix)
        sb.setToolTip(tooltip)
        sb.setSingleStep(max(val * 0.05, 0.001))
        return sb

    @staticmethod
    def _make_int_spin(val, min_v, max_v, tooltip="") -> QSpinBox:
        sb = QSpinBox()
        sb.setRange(min_v, max_v)
        sb.setValue(val)
        sb.setToolTip(tooltip)
        sb.setSingleStep(10)
        return sb

    # ── Preview reactivo ──────────────────────────────────────────────────────

    def _schedule_preview(self) -> None:
        """Debounce: espera 150ms antes de actualizar el preview."""
        self._preview_timer.start(150)

    def _update_preview(self) -> None:
        """
        Actualiza la previsualización. Llama directamente a GeometryConfig.compute_preview()
        sin pasar por el controlador.
        """
        config  = self.get_geometry()
        preview = config.compute_preview()

        # Actualizar etiquetas informativas
        self._lbl_cell_size.setText(
            f"Δx = {preview['dx']*100:.2f} cm,  Δy = {preview['dy']*100:.2f} cm"
        )
        self._lbl_ncells.setText(f"Total: {preview['cell_count']:,} celdas")

        # Renderizar preview
        self._preview.render_preview(preview)

        # Emitir señal al controller (solo al ejecutar, no solo al cambiar)
        self.geometry_changed.emit(config)

    # ── API pública ───────────────────────────────────────────────────────────

    def get_geometry(self) -> GeometryConfig:
        """Retorna la GeometryConfig actual con los valores del formulario."""
        return GeometryConfig(
            length          = self._sb_L.value(),
            height          = self._sb_H.value(),
            depth           = self._sb_depth.value(),
            nx              = self._sb_nx.value(),
            ny              = self._sb_ny.value(),
            dam_width_frac  = self._sb_dam_w.value() / 100.0,
            dam_height_frac = self._sb_dam_h.value() / 100.0,
        )

    def set_geometry(self, geo: GeometryConfig) -> None:
        """Carga una GeometryConfig en el formulario."""
        self._sb_L.setValue(geo.length)
        self._sb_H.setValue(geo.height)
        self._sb_depth.setValue(geo.depth)
        self._sb_nx.setValue(geo.nx)
        self._sb_ny.setValue(geo.ny)
        self._sb_dam_w.setValue(geo.dam_width_frac * 100)
        self._sb_dam_h.setValue(geo.dam_height_frac * 100)


# ── SimulationTab ─────────────────────────────────────────────────────────────

class SimulationTab(QWidget):
    """
    Pestaña de parámetros de simulación.

    Configura: tiempo final, intervalo de escritura, Courant máximo,
    modelo de turbulencia, nombre del caso y directorio de salida.

    Señales:
        params_changed(): Emitida cuando cambia cualquier parámetro.
    """

    params_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        main = QVBoxLayout(self)
        main.setContentsMargins(16, 16, 16, 16)
        main.setSpacing(14)

        # ── Identificación del caso ───────────────────────────────────────────
        id_group = QGroupBox("Identificación")
        id_group.setFont(QFont("Arial", 9, QFont.Bold))
        id_form = QFormLayout(id_group)
        id_form.setSpacing(8)
        id_form.setLabelAlignment(Qt.AlignRight)

        self._edit_name = QLineEdit("damBreakLodo")
        self._edit_name.setToolTip("Nombre identificador del caso OpenFOAM")
        self._edit_name.textChanged.connect(self.params_changed)
        id_form.addRow("Nombre del caso:", self._edit_name)

        # Directorio de salida
        dir_row = QHBoxLayout()
        self._edit_outdir = QLineEdit("~/openfoam_cases")
        self._edit_outdir.setToolTip("Directorio donde se generarán los archivos del caso")
        btn_browse = QPushButton("...")
        btn_browse.setFixedWidth(30)
        btn_browse.clicked.connect(self._browse_output_dir)
        dir_row.addWidget(self._edit_outdir)
        dir_row.addWidget(btn_browse)
        id_form.addRow("Directorio de salida:", dir_row)
        main.addWidget(id_group)

        # ── Parámetros temporales ─────────────────────────────────────────────
        time_group = QGroupBox("Control de tiempo")
        time_group.setFont(QFont("Arial", 9, QFont.Bold))
        time_form = QFormLayout(time_group)
        time_form.setSpacing(8)
        time_form.setLabelAlignment(Qt.AlignRight)

        def _dspin(val, min_v, max_v, dec, suffix, tooltip=""):
            sb = QDoubleSpinBox()
            sb.setDecimals(dec)
            sb.setRange(min_v, max_v)
            sb.setValue(val)
            sb.setSuffix(f"  {suffix}")
            sb.setToolTip(tooltip)
            sb.valueChanged.connect(self.params_changed)
            return sb

        self._sb_end_time      = _dspin(1.0,  0.01, 3600.0, 2, "s",
                                         "Tiempo final de la simulación [s]")
        self._sb_write_int     = _dspin(0.05, 0.001, 100.0,  3, "s",
                                         "Intervalo de escritura de resultados [s]")
        self._sb_max_co        = _dspin(0.5,  0.01,   2.0,  2, "",
                                         "Número de Courant máximo (recomendado: 0.5 para VoF)")

        time_form.addRow("Tiempo final:", self._sb_end_time)
        time_form.addRow("Intervalo escritura:", self._sb_write_int)
        time_form.addRow("Courant máximo:", self._sb_max_co)

        # Etiqueta informativa
        self._lbl_steps = QLabel("→ 20 pasos de escritura")
        self._lbl_steps.setStyleSheet("color: #555; font-size: 10px;")
        time_form.addRow("", self._lbl_steps)

        self._sb_end_time.valueChanged.connect(self._update_steps_label)
        self._sb_write_int.valueChanged.connect(self._update_steps_label)
        main.addWidget(time_group)

        # ── Modelo de turbulencia ─────────────────────────────────────────────
        turb_group = QGroupBox("Turbulencia")
        turb_group.setFont(QFont("Arial", 9, QFont.Bold))
        turb_form = QFormLayout(turb_group)
        turb_form.setSpacing(8)
        turb_form.setLabelAlignment(Qt.AlignRight)

        self._combo_turb = QComboBox()
        for tm in TurbulenceModel:
            self._combo_turb.addItem(tm.display_name, tm)
        # Seleccionar k-epsilon por defecto
        for i in range(self._combo_turb.count()):
            if self._combo_turb.itemData(i) == TurbulenceModel.K_EPSILON:
                self._combo_turb.setCurrentIndex(i)
                break
        self._combo_turb.currentIndexChanged.connect(self.params_changed)
        turb_form.addRow("Modelo:", self._combo_turb)
        main.addWidget(turb_group)

        main.addStretch()
        self._update_steps_label()

    def _browse_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Seleccionar directorio de salida",
            self._edit_outdir.text()
        )
        if path:
            self._edit_outdir.setText(path)

    def _update_steps_label(self) -> None:
        t_end  = self._sb_end_time.value()
        t_int  = self._sb_write_int.value()
        n_steps = max(1, int(t_end / t_int)) if t_int > 0 else 1
        self._lbl_steps.setText(f"→ {n_steps} pasos de escritura")

    # ── API pública ───────────────────────────────────────────────────────────

    def get_params(self) -> dict:
        """Retorna los parámetros de simulación como dict."""
        return {
            "name":             self._edit_name.text().strip() or "damBreak",
            "output_dir":       self._edit_outdir.text().strip() or "~/openfoam_cases",
            "end_time":         self._sb_end_time.value(),
            "write_interval":   self._sb_write_int.value(),
            "max_courant":      self._sb_max_co.value(),
            "turbulence_model": self._combo_turb.currentData(),
        }

    def set_params(self, params: dict) -> None:
        """Carga parámetros en el formulario."""
        if "name" in params:
            self._edit_name.setText(params["name"])
        if "output_dir" in params:
            self._edit_outdir.setText(params["output_dir"])
        if "end_time" in params:
            self._sb_end_time.setValue(params["end_time"])
        if "write_interval" in params:
            self._sb_write_int.setValue(params["write_interval"])
        if "max_courant" in params:
            self._sb_max_co.setValue(params["max_courant"])
        if "turbulence_model" in params:
            tm = params["turbulence_model"]
            for i in range(self._combo_turb.count()):
                if self._combo_turb.itemData(i) == tm:
                    self._combo_turb.setCurrentIndex(i)
                    break
