"""
Pestaña de configuración del fluido.

Permite seleccionar entre Newtoniano y Herschel-Bulkley,
y configurar los parámetros físicos correspondientes.
El formulario se adapta dinámicamente al modelo seleccionado.
"""
from __future__ import annotations

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QComboBox, QDoubleSpinBox, QGroupBox,
    QPushButton, QSizePolicy, QSpacerItem, QFrame,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QFont, QColor

from core.models import (
    FluidModel, NewtonianFluid, HerschelBulkleyFluid, FLUID_REGISTRY
)


class FluidTab(QWidget):
    """
    Pestaña de configuración del fluido principal.

    Señales:
        fluid_changed(FluidModel): Emitida cuando cambian los parámetros del fluido.

    Permite:
        - Seleccionar el modelo reológico (Newtoniano / Herschel-Bulkley)
        - Configurar todos los parámetros físicos
        - El formulario se adapta al modelo seleccionado
        - Validación visual en tiempo real
    """

    fluid_changed = pyqtSignal(object)  # FluidModel

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._building = False
        self._setup_ui()
        self._load_preset_mud()

    # ── Configuración de la UI ────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # ── Panel izquierdo: formulario ───────────────────────────────────────
        left = QVBoxLayout()
        left.setSpacing(12)

        # Selector de modelo
        model_group = QGroupBox("Modelo Reológico")
        model_group.setFont(QFont("Arial", 9, QFont.Bold))
        model_layout = QVBoxLayout(model_group)

        self._model_combo = QComboBox()
        self._model_combo.addItem("Herschel-Bulkley (Viscoplástico)", "herschel_bulkley")
        self._model_combo.addItem("Newtoniano (Viscosidad constante)", "newtonian")
        self._model_combo.currentIndexChanged.connect(self._on_model_changed)
        model_layout.addWidget(self._model_combo)

        # Descripción del modelo
        self._model_desc = QLabel()
        self._model_desc.setWordWrap(True)
        self._model_desc.setStyleSheet("color: #555; font-size: 11px;")
        model_layout.addWidget(self._model_desc)
        left.addWidget(model_group)

        # Parámetros del fluido
        params_group = QGroupBox("Parámetros Físicos")
        params_group.setFont(QFont("Arial", 9, QFont.Bold))
        self._params_layout = QFormLayout()
        self._params_layout.setSpacing(8)
        self._params_layout.setLabelAlignment(Qt.AlignRight)
        params_group.setLayout(self._params_layout)
        left.addWidget(params_group)

        # Preset buttons
        presets_group = QGroupBox("Presets")
        presets_group.setFont(QFont("Arial", 9, QFont.Bold))
        presets_layout = QHBoxLayout(presets_group)

        btn_mud = QPushButton("Lodo literatura")
        btn_mud.clicked.connect(self._load_preset_mud)
        btn_mud.setToolTip("Parámetros típicos de lodo volcánico (Ancey 2007)")

        btn_water = QPushButton("Agua")
        btn_water.clicked.connect(self._load_preset_water)
        btn_water.setToolTip("Agua a 20°C")

        presets_layout.addWidget(btn_mud)
        presets_layout.addWidget(btn_water)
        left.addWidget(presets_group)

        # Estado de validación
        self._validation_label = QLabel("")
        self._validation_label.setWordWrap(True)
        self._validation_label.setStyleSheet("font-size: 11px;")
        left.addWidget(self._validation_label)

        left.addStretch()
        main_layout.addLayout(left, stretch=1)

        # ── Separador ─────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #DDD;")
        main_layout.addWidget(sep)

        # ── Panel derecho: curva reológica ────────────────────────────────────
        from ui.widgets.plot_widget import PlotWidget
        right = QVBoxLayout()
        right.setSpacing(6)

        lbl_chart = QLabel("Curva de viscosidad efectiva ν(γ̇)")
        lbl_chart.setFont(QFont("Arial", 9, QFont.Bold))
        right.addWidget(lbl_chart)

        self._rheology_plot = PlotWidget(figsize=(5.5, 4.0), show_toolbar=False)
        right.addWidget(self._rheology_plot)

        lbl_hint = QLabel(
            "ν₀: viscosidad plateau (zona plug) — parámetro de regularización numérica\n"
            "No forma parte del modelo clásico Herschel-Bulkley."
        )
        lbl_hint.setWordWrap(True)
        lbl_hint.setStyleSheet("color: #888; font-size: 10px; font-style: italic;")
        right.addWidget(lbl_hint)

        main_layout.addLayout(right, stretch=1)

        # Construir campos iniciales
        self._rebuild_params_form("herschel_bulkley")

    # ── Construcción dinámica del formulario ──────────────────────────────────

    def _rebuild_params_form(self, model_key: str) -> None:
        """Reconstruye el formulario de parámetros según el modelo seleccionado."""
        self._building = True

        # Limpiar formulario anterior
        while self._params_layout.count():
            item = self._params_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._spinboxes = {}

        def _spin(val, min_v, max_v, dec, suffix, tooltip=""):
            sb = QDoubleSpinBox()
            sb.setDecimals(dec)
            sb.setRange(min_v, max_v)
            sb.setValue(val)
            sb.setSuffix(f"  {suffix}")
            sb.setToolTip(tooltip)
            sb.setSingleStep(val * 0.1 if val > 0 else 0.01)
            sb.valueChanged.connect(self._on_param_changed)
            return sb

        if model_key == "herschel_bulkley":
            self._model_desc.setText(
                "Fluido viscoplástico. Solo fluye cuando el esfuerzo "
                "cortante supera τ₀ (zona plug cuando τ ≤ τ₀)."
            )
            params = [
                ("rho",  "Densidad ρ",          1800.0, 100, 5000, 1, "kg/m³",
                 "Densidad del lodo [kg/m³]. Típico: 1500-2200."),
                ("tau0", "Esfuerzo fluencia τ₀", 50.0,    0, 5000, 2, "Pa",
                 "Umbral de esfuerzo mínimo para que el fluido fluya [Pa]."),
                ("k",    "Consistencia k",        10.0,  0.1, 1000, 3, "Pa·sⁿ",
                 "Resistencia al flujo [Pa·sⁿ]."),
                ("n",    "Índice de flujo n",      0.4,  0.01, 3.0, 3, "–",
                 "n<1: pseudoplástico, n=1: Bingham, n>1: dilatante."),
                ("nu0",  "Viscosidad plateau ν₀",  1.0,  0.01, 100, 3, "m²/s",
                 "Parámetro de regularización numérica (no físico).\n"
                 "Debe ser 2-3 órdenes mayor que ν_eff en zona de flujo."),
            ]
        else:
            self._model_desc.setText(
                "Fluido con relación lineal τ = μ·γ̇. "
                "Viscosidad constante, independiente del esfuerzo."
            )
            params = [
                ("rho", "Densidad ρ",           1000.0, 100, 5000, 1, "kg/m³",
                 "Densidad del fluido [kg/m³]. Agua: 1000."),
                ("nu",  "Viscosidad cinemática ν", 1e-6, 1e-9, 1.0, 8, "m²/s",
                 "Viscosidad cinemática [m²/s]. Agua 20°C: 1e-6."),
                ("sigma", "Tensión superficial σ", 0.07, 0.0, 1.0, 4, "N/m",
                 "Tensión superficial fluido-aire [N/m]. Agua: 0.07."),
            ]

        for key, label, default, min_v, max_v, dec, suffix, tooltip in params:
            sb = _spin(default, min_v, max_v, dec, suffix, tooltip)
            self._spinboxes[key] = sb
            self._params_layout.addRow(f"{label}:", sb)

        self._building = False
        self._update_rheology_plot()

    # ── Eventos ───────────────────────────────────────────────────────────────

    def _on_model_changed(self, index: int) -> None:
        key = self._model_combo.currentData()
        self._rebuild_params_form(key)
        self._emit_fluid()

    def _on_param_changed(self) -> None:
        if not self._building:
            self._update_rheology_plot()
            self._emit_fluid()

    def _emit_fluid(self) -> None:
        """Construye el FluidModel y emite la señal fluid_changed."""
        fluid = self.get_fluid()
        if fluid:
            result = fluid.validate()
            if result.is_valid:
                self._validation_label.setText("✓ Parámetros válidos")
                self._validation_label.setStyleSheet("color: #1AA870; font-size: 11px;")
            else:
                msgs = "\n".join(f"• {e}" for e in result.errors[:2])
                self._validation_label.setText(f"⚠ {msgs}")
                self._validation_label.setStyleSheet("color: #E85A30; font-size: 11px;")
            self.fluid_changed.emit(fluid)

    def _update_rheology_plot(self) -> None:
        """Actualiza la gráfica de la curva reológica."""
        fluid = self.get_fluid()
        if fluid is None:
            return

        import numpy as np
        self._rheology_plot.figure.clear()
        ax = self._rheology_plot.figure.add_subplot(1, 1, 1)

        gamma = np.logspace(-3, 3, 200)

        if isinstance(fluid, HerschelBulkleyFluid):
            nu_eff = [fluid.get_kinematic_viscosity_at_shear_rate(g) for g in gamma]
            ax.loglog(gamma, nu_eff, color="#2C5F8A", linewidth=2)

            # Línea de nu0 (plateau)
            ax.axhline(y=fluid.nu0, color="#E85A30", linewidth=1,
                       linestyle="--", label=f"ν₀ = {fluid.nu0:.2f} m²/s")
            ax.legend(fontsize=8)
            ax.set_ylabel("ν_eff [m²/s]")

        elif isinstance(fluid, NewtonianFluid):
            nu_arr = np.full_like(gamma, fluid.nu)
            ax.loglog(gamma, nu_arr, color="#1AA870", linewidth=2)
            ax.set_ylabel("ν [m²/s]")

        ax.set_xlabel("Tasa de deformación γ̇ [1/s]")
        ax.set_title("Viscosidad efectiva", fontsize=9)
        ax.grid(True, which="both", alpha=0.3)
        ax.tick_params(labelsize=8)

        self._rheology_plot.redraw()

    # ── API pública ───────────────────────────────────────────────────────────

    def get_fluid(self) -> FluidModel | None:
        """Retorna el FluidModel actual con los valores del formulario."""
        if not hasattr(self, "_spinboxes") or not self._spinboxes:
            return None

        sb  = self._spinboxes
        key = self._model_combo.currentData()

        try:
            if key == "herschel_bulkley":
                return HerschelBulkleyFluid(
                    rho  = sb["rho"].value(),
                    tau0 = sb["tau0"].value(),
                    k    = sb["k"].value(),
                    n    = sb["n"].value(),
                    nu0  = sb["nu0"].value(),
                )
            else:
                return NewtonianFluid(
                    rho   = sb["rho"].value(),
                    nu    = sb["nu"].value(),
                    sigma = sb["sigma"].value(),
                )
        except (KeyError, Exception):
            return None

    def set_fluid(self, fluid: FluidModel) -> None:
        """Carga un FluidModel en el formulario."""
        self._building = True

        if isinstance(fluid, HerschelBulkleyFluid):
            self._model_combo.setCurrentIndex(0)
            self._rebuild_params_form("herschel_bulkley")
            self._spinboxes["rho"].setValue(fluid.rho)
            self._spinboxes["tau0"].setValue(fluid.tau0)
            self._spinboxes["k"].setValue(fluid.k)
            self._spinboxes["n"].setValue(fluid.n)
            self._spinboxes["nu0"].setValue(fluid.nu0)
        elif isinstance(fluid, NewtonianFluid):
            self._model_combo.setCurrentIndex(1)
            self._rebuild_params_form("newtonian")
            self._spinboxes["rho"].setValue(fluid.rho)
            self._spinboxes["nu"].setValue(fluid.nu)
            self._spinboxes["sigma"].setValue(fluid.sigma)

        self._building = False
        self._update_rheology_plot()

    def _load_preset_mud(self) -> None:
        self.set_fluid(HerschelBulkleyFluid.from_literature_mud())

    def _load_preset_water(self) -> None:
        self.set_fluid(NewtonianFluid.water())
