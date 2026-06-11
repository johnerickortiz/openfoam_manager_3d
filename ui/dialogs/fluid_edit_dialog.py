"""Diálogo de edición del fluido — con curva reológica en tiempo real."""
from __future__ import annotations
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QComboBox, QDoubleSpinBox, QGroupBox, QPushButton,
    QDialogButtonBox, QFrame, QSizePolicy,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from core.models import FluidModel, NewtonianFluid, HerschelBulkleyFluid
from ui.widgets.plot_widget import PlotWidget
import numpy as np


class FluidEditDialog(QDialog):
    """
    Diálogo modal para editar los parámetros del fluido.
    result_fluid contiene el FluidModel resultante si se aceptó.
    """
    def __init__(self, fluid: FluidModel, parent=None) -> None:
        super().__init__(parent)
        self.result_fluid: FluidModel | None = None
        self._building = False
        self._timer = QTimer(); self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._update_curve)
        self.setWindowTitle("Editar fluido")
        self.setMinimumSize(680, 480)
        self._setup_ui()
        self.set_fluid(fluid)

    def _setup_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setSpacing(12); root.setContentsMargins(14,14,14,14)

        # ── Izquierda: formulario ─────────────────────────────────────────────
        left = QVBoxLayout(); left.setSpacing(10)

        # Selector de modelo
        g_model = QGroupBox("Modelo reológico")
        g_model.setFont(QFont("Arial",9,QFont.Bold))
        fl_m = QFormLayout(g_model); fl_m.setSpacing(8)
        self._combo_model = QComboBox()
        self._combo_model.addItem("Herschel-Bulkley (viscoplástico)", "hb")
        self._combo_model.addItem("Newtoniano (viscosidad constante)", "newton")
        self._combo_model.currentIndexChanged.connect(self._on_model_changed)
        fl_m.addRow("Modelo:", self._combo_model)
        left.addWidget(g_model)

        # Parámetros físicos
        g_params = QGroupBox("Parámetros físicos")
        g_params.setFont(QFont("Arial",9,QFont.Bold))
        self._fl_params = QFormLayout(g_params)
        self._fl_params.setSpacing(8)
        self._fl_params.setLabelAlignment(Qt.AlignRight)
        left.addWidget(g_params)

        # Presets
        g_pre = QGroupBox("Presets")
        g_pre.setFont(QFont("Arial",9,QFont.Bold))
        row_pre = QHBoxLayout(g_pre)
        for label, fn in [("Lodo (lit.)", self._preset_mud),
                           ("Agua", self._preset_water)]:
            b = QPushButton(label); b.setFixedHeight(26)
            b.clicked.connect(fn); row_pre.addWidget(b)
        left.addWidget(g_pre)

        # Validación
        self._lbl_valid = QLabel("✓ Parámetros válidos")
        self._lbl_valid.setStyleSheet("font-size:11px; color:#1AA870;")
        left.addWidget(self._lbl_valid)
        left.addStretch()

        # Botones
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Aplicar cambios")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        left.addWidget(btns)

        root.addLayout(left, stretch=1)

        # Separador
        sep = QFrame(); sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color:#DDD;"); root.addWidget(sep)

        # ── Derecha: gráfica ─────────────────────────────────────────────────
        right = QVBoxLayout(); right.setSpacing(6)
        lbl = QLabel("Curva de viscosidad efectiva ν(γ̇)")
        lbl.setFont(QFont("Arial",9,QFont.Bold))
        right.addWidget(lbl)
        self._plot = PlotWidget(figsize=(4.5,3.5), show_toolbar=False)
        right.addWidget(self._plot)
        note = QLabel("ν₀: viscosidad plateau (regularización numérica,\n"
                      "no forma parte del modelo clásico HB)")
        note.setStyleSheet("color:#888; font-size:10px; font-style:italic;")
        note.setWordWrap(True); right.addWidget(note)
        right.addStretch()
        root.addLayout(right, stretch=1)

    def _make_spin(self, val, lo, hi, dec, suffix, tip="") -> QDoubleSpinBox:
        sb = QDoubleSpinBox()
        sb.setRange(lo, hi); sb.setDecimals(dec)
        sb.setValue(val); sb.setSuffix(f"  {suffix}")
        sb.setToolTip(tip)
        sb.valueChanged.connect(self._schedule_curve)
        return sb

    def _rebuild_form(self, key: str) -> None:
        self._building = True
        while self._fl_params.count():
            item = self._fl_params.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self._spins = {}

        if key == "hb":
            specs = [
                ("rho",  "Densidad ρ",           1800, 100, 5000, 1, "kg/m³"),
                ("tau0", "Esfuerzo fluencia τ₀",   50,   0, 5000, 2, "Pa"),
                ("k",    "Consistencia k",          10, 0.01,1000, 3, "Pa·sⁿ"),
                ("n",    "Índice de flujo n",       0.4, 0.01, 3, 3, "—"),
                ("nu0",  "Viscosidad plateau ν₀",   1.0, 0.001,100, 3, "m²/s"),
                ("sigma","Tensión superficial σ",   0.0,   0,  1, 4, "N/m"),
            ]
        else:
            specs = [
                ("rho",  "Densidad ρ",    1000, 100, 5000, 1, "kg/m³"),
                ("nu",   "Viscosidad ν",  1e-6, 1e-9,  1, 8, "m²/s"),
                ("sigma","Tensión σ",     0.07,    0,  1, 4, "N/m"),
            ]

        for key_p, label, default, lo, hi, dec, suf in specs:
            sb = self._make_spin(default, lo, hi, dec, suf)
            self._spins[key_p] = sb
            self._fl_params.addRow(f"{label}:", sb)

        self._building = False
        self._update_curve()

    def _on_model_changed(self, _) -> None:
        self._rebuild_form(self._combo_model.currentData())

    def _schedule_curve(self) -> None:
        if not self._building:
            self._timer.start(120)
            self._validate()

    def _validate(self) -> None:
        f = self.get_fluid()
        if f:
            r = f.validate()
            if r.is_valid:
                self._lbl_valid.setText("✓ Parámetros válidos")
                self._lbl_valid.setStyleSheet("font-size:11px; color:#1AA870;")
            else:
                self._lbl_valid.setText("⚠ " + r.errors[0])
                self._lbl_valid.setStyleSheet("font-size:11px; color:#E85A30;")

    def _update_curve(self) -> None:
        f = self.get_fluid(); 
        if f is None: return
        self._plot.figure.clear()
        ax = self._plot.figure.add_subplot(1,1,1)
        g  = np.logspace(-3, 3, 200)
        if isinstance(f, HerschelBulkleyFluid):
            nu = [f.get_kinematic_viscosity_at_shear_rate(gi) for gi in g]
            ax.loglog(g, nu, color="#2C5F8A", lw=2)
            ax.axhline(y=f.nu0, color="#E85A30", lw=1, ls="--",
                       label=f"ν₀={f.nu0:.2f}")
            ax.legend(fontsize=8)
        else:
            ax.loglog(g, [f.nu]*len(g), color="#1AA870", lw=2)
        ax.set_xlabel("γ̇ [1/s]", fontsize=8)
        ax.set_ylabel("ν_eff [m²/s]", fontsize=8)
        ax.grid(True, which="both", alpha=0.3); ax.tick_params(labelsize=7)
        self._plot.redraw()

    def _on_accept(self) -> None:
        f = self.get_fluid()
        if f:
            r = f.validate()
            if r.is_valid:
                self.result_fluid = f; self.accept()
            else:
                self._lbl_valid.setText("⚠ " + r.errors[0])

    def get_fluid(self) -> FluidModel | None:
        if not hasattr(self, "_spins"): return None
        s = self._spins; k = self._combo_model.currentData()
        try:
            if k == "hb":
                return HerschelBulkleyFluid(
                    rho=s["rho"].value(), tau0=s["tau0"].value(),
                    k=s["k"].value(),   n=s["n"].value(),
                    nu0=s["nu0"].value(), sigma=s["sigma"].value())
            else:
                return NewtonianFluid(
                    rho=s["rho"].value(), nu=s["nu"].value(),
                    sigma=s["sigma"].value())
        except: return None

    def set_fluid(self, fluid: FluidModel) -> None:
        self._building = True
        if isinstance(fluid, HerschelBulkleyFluid):
            self._combo_model.setCurrentIndex(0)
            self._rebuild_form("hb")
            s = self._spins
            s["rho"].setValue(fluid.rho); s["tau0"].setValue(fluid.tau0)
            s["k"].setValue(fluid.k);     s["n"].setValue(fluid.n)
            s["nu0"].setValue(fluid.nu0); s["sigma"].setValue(fluid.sigma)
        else:
            self._combo_model.setCurrentIndex(1)
            self._rebuild_form("newton")
            s = self._spins
            s["rho"].setValue(fluid.rho); s["nu"].setValue(fluid.nu)
            s["sigma"].setValue(fluid.sigma)
        self._building = False
        self._update_curve(); self._validate()

    def _preset_mud(self) -> None:
        self.set_fluid(HerschelBulkleyFluid.from_literature_mud())

    def _preset_water(self) -> None:
        self.set_fluid(NewtonianFluid.water())
