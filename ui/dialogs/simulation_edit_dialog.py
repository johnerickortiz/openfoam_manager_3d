"""Diálogo de edición de parámetros de simulación."""
from __future__ import annotations
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QLabel, QLineEdit,
    QDoubleSpinBox, QComboBox, QPushButton, QDialogButtonBox,
    QFileDialog, QHBoxLayout, QGroupBox,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from core.simulation.simulation_config import TurbulenceMode
from core.models import HerschelBulkleyFluid


class SimulationEditDialog(QDialog):
    """
    Diálogo modal para editar los parámetros de simulación.
    result_params contiene el dict de parámetros si se aceptó.
    """
    def __init__(self, params: dict, fluid=None, parent=None) -> None:
        super().__init__(parent)
        self.result_params: dict | None = None
        self._fluid = fluid
        self.setWindowTitle("Editar configuración de simulación")
        self.setMinimumWidth(480)
        self._setup_ui()
        self.set_params(params)

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12); root.setContentsMargins(16,16,16,16)

        # ── Identificación ─────────────────────────────────────────────────
        g_id = QGroupBox("Identificación del caso")
        g_id.setFont(QFont("Arial",9,QFont.Bold))
        grid_id = QGridLayout(g_id); grid_id.setSpacing(8)

        grid_id.addWidget(QLabel("Nombre del caso:"), 0, 0, Qt.AlignRight)
        self._edit_name = QLineEdit("damBreakLodo3D")
        grid_id.addWidget(self._edit_name, 0, 1)

        grid_id.addWidget(QLabel("Directorio de salida:"), 1, 0, Qt.AlignRight)
        dir_row = QHBoxLayout()
        self._edit_dir = QLineEdit("~/openfoam_cases")
        btn_browse = QPushButton("..."); btn_browse.setFixedWidth(30)
        btn_browse.clicked.connect(self._browse)
        dir_row.addWidget(self._edit_dir); dir_row.addWidget(btn_browse)
        grid_id.addLayout(dir_row, 1, 1)
        root.addWidget(g_id)

        # ── Control de tiempo ──────────────────────────────────────────────
        g_time = QGroupBox("Control de tiempo")
        g_time.setFont(QFont("Arial",9,QFont.Bold))
        grid_t = QGridLayout(g_time); grid_t.setSpacing(8)

        def dspin(v, lo, hi, dec, suf):
            sb = QDoubleSpinBox(); sb.setRange(lo,hi); sb.setDecimals(dec)
            sb.setValue(v); sb.setSuffix(f"  {suf}")
            sb.valueChanged.connect(self._update_steps)
            return sb

        self._sb_tend  = dspin(5.0,  0.01, 3600, 2, "s")
        self._sb_write = dspin(0.05, 0.001, 100, 3, "s")
        self._sb_co    = dspin(0.5,  0.01,  2.0, 2, "")
        self._lbl_steps = QLabel("→ 100 pasos de escritura")
        self._lbl_steps.setStyleSheet("color:#666; font-size:10px;")

        grid_t.addWidget(QLabel("Tiempo final:"),        0, 0, Qt.AlignRight)
        grid_t.addWidget(self._sb_tend,                  0, 1)
        grid_t.addWidget(QLabel("Intervalo escritura:"), 1, 0, Qt.AlignRight)
        grid_t.addWidget(self._sb_write,                 1, 1)
        grid_t.addWidget(QLabel("Courant máximo:"),      2, 0, Qt.AlignRight)
        grid_t.addWidget(self._sb_co,                    2, 1)
        grid_t.addWidget(QLabel(""),                     3, 0)
        grid_t.addWidget(self._lbl_steps,                3, 1)
        root.addWidget(g_time)

        # ── Turbulencia ────────────────────────────────────────────────────
        g_turb = QGroupBox("Modelo de turbulencia")
        g_turb.setFont(QFont("Arial",9,QFont.Bold))
        grid_tr = QGridLayout(g_turb); grid_tr.setSpacing(8)

        self._combo_turb = QComboBox()
        for mode in TurbulenceMode:
            self._combo_turb.addItem(mode.display_name, mode)
        self._combo_turb.currentIndexChanged.connect(self._update_turb_info)

        self._lbl_turb_eff = QLabel("")
        self._lbl_turb_eff.setStyleSheet("color:#2C5F8A; font-size:10px;")

        grid_tr.addWidget(QLabel("Modo:"),    0, 0, Qt.AlignRight)
        grid_tr.addWidget(self._combo_turb,   0, 1)
        grid_tr.addWidget(QLabel("Efectivo:"),1, 0, Qt.AlignRight)
        grid_tr.addWidget(self._lbl_turb_eff, 1, 1)
        root.addWidget(g_turb)

        # Botones
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Aplicar cambios")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Directorio de salida", self._edit_dir.text())
        if path: self._edit_dir.setText(path)

    def _update_steps(self) -> None:
        t, dt = self._sb_tend.value(), self._sb_write.value()
        n = max(1, int(t / dt)) if dt > 0 else 1
        self._lbl_steps.setText(f"→ {n} pasos de escritura")

    def _update_turb_info(self) -> None:
        mode = self._combo_turb.currentData()
        if mode == TurbulenceMode.AUTO:
            if isinstance(self._fluid, HerschelBulkleyFluid):
                eff = "laminar (HB → laminar automáticamente)"
            else:
                eff = "kEpsilon (agua → kEpsilon automáticamente)"
        else:
            eff = mode.value
        self._lbl_turb_eff.setText(eff)

    def _on_accept(self) -> None:
        self.result_params = self.get_params(); self.accept()

    def get_params(self) -> dict:
        return {
            "name":             self._edit_name.text().strip() or "damBreak3D",
            "output_dir":       self._edit_dir.text().strip() or "~/openfoam_cases",
            "end_time":         self._sb_tend.value(),
            "write_interval":   self._sb_write.value(),
            "max_courant":      self._sb_co.value(),
            "turbulence_mode":  self._combo_turb.currentData(),
        }

    def set_params(self, params: dict) -> None:
        if "name" in params:
            self._edit_name.setText(params["name"])
        if "output_dir" in params:
            self._edit_dir.setText(params["output_dir"])
        if "end_time" in params:
            self._sb_tend.setValue(params["end_time"])
        if "write_interval" in params:
            self._sb_write.setValue(params["write_interval"])
        if "max_courant" in params:
            self._sb_co.setValue(params["max_courant"])
        if "turbulence_mode" in params:
            mode = params["turbulence_mode"]
            for i in range(self._combo_turb.count()):
                if self._combo_turb.itemData(i) == mode:
                    self._combo_turb.setCurrentIndex(i); break
        self._update_steps(); self._update_turb_info()
