"""
Panel de resumen de configuración — siempre visible a la izquierda.

Muestra un resumen compacto de Fluido, Geometría y Simulación,
cada uno con un botón "Editar" que abre el diálogo correspondiente.
"""
from __future__ import annotations
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QSizePolicy,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QFont
from core.simulation import SimulationConfig
from core.models import HerschelBulkleyFluid


class ConfigSummaryPanel(QWidget):
    """
    Panel lateral fijo con resumen de la configuración activa.

    Señales:
        run_requested()              — usuario pulsó "Ejecutar"
        clean_requested()            — usuario pulsó "Limpiar"
        edit_fluid_requested()
        edit_geometry_requested()
        edit_simulation_requested()
    """
    run_requested              = pyqtSignal()
    load_case_requested        = pyqtSignal()
    clean_requested            = pyqtSignal()
    edit_fluid_requested       = pyqtSignal()
    edit_geometry_requested    = pyqtSignal()
    edit_simulation_requested  = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedWidth(205)
        self.setStyleSheet("background: transparent;")
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sección Fluido ────────────────────────────────────────────────────
        self._fluid_labels = {}
        fluid_section = self._make_section(
            "Fluido", self.edit_fluid_requested,
            [("Modelo", "—"), ("ρ", "—"), ("τ₀ / k / n", "—"), ("Turbulencia", "—")],
            self._fluid_labels
        )
        root.addWidget(fluid_section)

        # ── Sección Geometría ─────────────────────────────────────────────────
        self._geo_labels = {}
        geo_section = self._make_section(
            "Geometría", self.edit_geometry_requested,
            [("L × H × W", "—"), ("Malla", "—"), ("Celdas", "—"), ("Presa", "—")],
            self._geo_labels
        )
        root.addWidget(geo_section)

        # ── Sección Simulación ────────────────────────────────────────────────
        self._sim_labels = {}
        sim_section = self._make_section(
            "Simulación", self.edit_simulation_requested,
            [("Caso", "—"), ("t_fin / Δt", "—"), ("Courant", "—"), ("Directorio", "—")],
            self._sim_labels
        )
        root.addWidget(sim_section)

        root.addStretch()

        # ── Botones de acción ─────────────────────────────────────────────────
        action_widget = QWidget()
        action_layout = QVBoxLayout(action_widget)
        action_layout.setContentsMargins(8, 8, 8, 8)
        action_layout.setSpacing(6)

        self._btn_run = QPushButton("▶  Ejecutar simulación")
        self._btn_run.setFixedHeight(34)
        self._btn_run.setFont(QFont("Arial", 10, QFont.Bold))
        self._btn_run.setStyleSheet(
            "QPushButton{background:#2C5F8A;color:white;border-radius:5px;}"
            "QPushButton:hover{background:#3A78B5;}"
            "QPushButton:disabled{background:#AAA;}")
        self._btn_run.clicked.connect(self.run_requested)
        action_layout.addWidget(self._btn_run)

        self._btn_load_case = QPushButton("📂  Cargar caso...")
        self._btn_load_case.setFixedHeight(30)
        self._btn_load_case.setFont(QFont("Arial", 9, QFont.Bold))
        self._btn_load_case.setStyleSheet(
            "QPushButton{background:#1AA870;color:white;border-radius:5px;}"
            "QPushButton:hover{background:#15906A;}"
            "QPushButton:disabled{background:#AAA;}")
        self._btn_load_case.clicked.connect(self.load_case_requested)
        action_layout.addWidget(self._btn_load_case)

        self._btn_clean = QPushButton("Limpiar resultados")
        self._btn_clean.setFixedHeight(26)
        self._btn_clean.setStyleSheet(
            "QPushButton{background:#F0F4F8;border:1px solid #CBD5E1;"
            "border-radius:4px;font-size:11px;}"
            "QPushButton:hover{background:#E2EAF5;}")
        self._btn_clean.clicked.connect(self.clean_requested)
        action_layout.addWidget(self._btn_clean)

        root.addWidget(action_widget)

    def _make_section(
        self,
        title:   str,
        signal,
        fields:  list[tuple[str,str]],
        storage: dict,
    ) -> QWidget:
        """Crea un bloque de sección con etiquetas de resumen y botón Editar."""
        section = QWidget()
        section.setStyleSheet(
            "QWidget { border-bottom: 0.5px solid #E0E0E0; }"
        )
        lay = QVBoxLayout(section)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(5)

        # Cabecera
        header = QHBoxLayout()
        lbl_title = QLabel(title.upper())
        lbl_title.setFont(QFont("Arial", 8, QFont.Bold))
        lbl_title.setStyleSheet("color:#666; letter-spacing:0.06em; border:none;")
        header.addWidget(lbl_title)
        header.addStretch()

        btn_edit = QPushButton("Editar")
        btn_edit.setFixedHeight(20)
        btn_edit.setFixedWidth(50)
        btn_edit.setStyleSheet(
            "QPushButton{font-size:10px;color:#2C5F8A;"
            "border:0.5px solid #2C5F8A;border-radius:3px;"
            "background:transparent;padding:1px 4px;}"
            "QPushButton:hover{background:#EEF4FC;}")
        btn_edit.clicked.connect(signal)
        header.addWidget(btn_edit)
        lay.addLayout(header)

        # Campos de resumen
        for field_key, default_val in fields:
            row = QHBoxLayout()
            row.setSpacing(4)
            lbl_key = QLabel(field_key + ":")
            lbl_key.setStyleSheet(
                "font-size:10px; color:#888; border:none;"
            )
            lbl_key.setFixedWidth(72)
            lbl_key.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            lbl_val = QLabel(default_val)
            lbl_val.setStyleSheet(
                "font-size:10px; color:#222; font-weight:500; border:none;"
            )
            lbl_val.setWordWrap(True)
            storage[field_key] = lbl_val

            row.addWidget(lbl_key)
            row.addWidget(lbl_val, stretch=1)
            lay.addLayout(row)

        return section

    # ── API pública ───────────────────────────────────────────────────────────

    def refresh(self, config: SimulationConfig) -> None:
        """Actualiza todas las etiquetas de resumen con el config actual."""
        fluid = config.fluid
        geo   = config.geometry
        turb  = config.effective_turbulence_model

        # Fluido
        fl = self._fluid_labels
        fl["Modelo"].setText(fluid.display_name)
        fl["ρ"].setText(f"{fluid.rho:.0f} kg/m³")
        if isinstance(fluid, HerschelBulkleyFluid):
            fl["τ₀ / k / n"].setText(
                f"{fluid.tau0:.1f} Pa / {fluid.k:.1f} / {fluid.n:.2f}"
            )
        else:
            nu = getattr(fluid, "nu", 0)
            fl["τ₀ / k / n"].setText(f"ν={nu:.2e} m²/s")
        fl["Turbulencia"].setText(turb.value)

        # Geometría
        gl = self._geo_labels
        gl["L × H × W"].setText(
            f"{geo.length:.2f} × {geo.height:.2f} × {geo.width:.3f} m"
        )
        gl["Malla"].setText(f"{geo.nx}×{geo.ny}×{geo.nz}")
        gl["Celdas"].setText(f"{geo.cell_count:,}")
        gl["Presa"].setText(
            f"{geo.dam_width_frac*100:.0f}% × {geo.dam_height_frac*100:.0f}%"
        )

        # Simulación
        sl = self._sim_labels
        sl["Caso"].setText(config.name)
        sl["t_fin / Δt"].setText(
            f"{config.end_time:.1f}s / {config.write_interval:.3f}s"
        )
        sl["Courant"].setText(f"{config.max_courant:.2f}")
        # Directorio: mostrar solo el último segmento
        from pathlib import Path
        outdir = Path(config.output_dir).expanduser()
        sl["Directorio"].setText(f"…/{outdir.name}")

    def set_run_enabled(self, enabled: bool) -> None:
        self._btn_run.setEnabled(enabled)

    def set_load_case_enabled(self, enabled: bool) -> None:
        self._btn_load_case.setEnabled(enabled)

    def set_running_state(self, running: bool) -> None:
        if running:
            self._btn_run.setText("⏳  Simulando...")
            self._btn_run.setEnabled(False)
        else:
            self._btn_run.setText("▶  Ejecutar simulación")
            self._btn_run.setEnabled(True)
