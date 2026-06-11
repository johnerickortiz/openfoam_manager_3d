"""Diálogo de edición de geometría — dimensiones de presa en metros con validación."""
from __future__ import annotations
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QDoubleSpinBox, QSpinBox, QGroupBox, QPushButton,
    QDialogButtonBox, QFrame,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from core.simulation import GeometryConfig
from ui.widgets.geometry_preview_widget import GeometryPreviewWidget


class GeometryEditDialog(QDialog):
    """
    Diálogo modal para editar la geometría del canal 3D.

    Las dimensiones de la presa se ingresan en metros (no en porcentaje)
    y se validan en tiempo real para garantizar que no excedan el canal.

    result_geometry contiene la GeometryConfig resultante si se aceptó.
    """
    def __init__(self, geo: GeometryConfig, parent=None) -> None:
        super().__init__(parent)
        self.result_geometry: GeometryConfig | None = None
        self._timer = QTimer(); self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._update_preview)
        self.setWindowTitle("Editar geometría del canal 3D")
        self.setMinimumSize(840, 540)
        self._setup_ui()
        self.set_geometry(geo)

    def _setup_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setSpacing(12); root.setContentsMargins(14, 14, 14, 14)

        # ── Izquierda: formulario ─────────────────────────────────────────────
        left = QVBoxLayout(); left.setSpacing(10)

        # ── Dimensiones del canal ─────────────────────────────────────────────
        g_dim = QGroupBox("Dimensiones del canal")
        g_dim.setFont(QFont("Arial", 9, QFont.Bold))
        fl = QFormLayout(g_dim); fl.setSpacing(8)
        fl.setLabelAlignment(Qt.AlignRight)

        self._sb_L = self._dspin(1.6,  0.1, 50,  3, " m", "Longitud en dirección x [m]")
        self._sb_H = self._dspin(0.6,  0.05, 20, 3, " m", "Altura en dirección y [m]")
        self._sb_W = self._dspin(0.15, 0.01, 10, 3, " m", "Ancho en dirección z [m]")
        fl.addRow("Longitud L:", self._sb_L)
        fl.addRow("Altura H:",   self._sb_H)
        fl.addRow("Ancho W:",    self._sb_W)
        left.addWidget(g_dim)

        # ── Resolución de malla ───────────────────────────────────────────────
        g_mesh = QGroupBox("Resolución de malla 3D")
        g_mesh.setFont(QFont("Arial", 9, QFont.Bold))
        fm = QFormLayout(g_mesh); fm.setSpacing(8)
        fm.setLabelAlignment(Qt.AlignRight)

        self._sb_nx = self._ispin(80,  4, 1000, "Celdas en x (dirección del flujo)")
        self._sb_ny = self._ispin(30,  4, 500,  "Celdas en y (vertical)")
        self._sb_nz = self._ispin(8,   2, 200,  "Celdas en z (transversal) — mínimo 2")
        fm.addRow("nx (x):", self._sb_nx)
        fm.addRow("ny (y):", self._sb_ny)
        fm.addRow("nz (z):", self._sb_nz)

        self._lbl_cells = QLabel("19,200 celdas")
        self._lbl_cells.setStyleSheet(
            "color:#2C5F8A; font-weight:bold; font-size:11px;")
        self._lbl_dx = QLabel("Δx=20mm  Δy=20mm  Δz=18.8mm")
        self._lbl_dx.setStyleSheet("color:#666; font-size:10px;")
        fm.addRow("Total:",   self._lbl_cells)
        fm.addRow("Tamaño:", self._lbl_dx)
        left.addWidget(g_mesh)

        # ── Presa en metros ───────────────────────────────────────────────────
        g_dam = QGroupBox("Columna inicial de fluido (presa)")
        g_dam.setFont(QFont("Arial", 9, QFont.Bold))
        fd = QFormLayout(g_dam); fd.setSpacing(8)
        fd.setLabelAlignment(Qt.AlignRight)

        # Longitud de la presa en x [m] — range dinámico: (0, L)
        self._sb_dam_len = self._dspin(
            0.40, 0.01, 50.0, 3, " m",
            "Longitud de la presa en dirección x [m]\n"
            "Debe ser menor que la longitud del canal L"
        )
        # Altura de la presa en y [m] — range dinámico: (0, H)
        self._sb_dam_hei = self._dspin(
            0.30, 0.01, 20.0, 3, " m",
            "Altura de la presa en dirección y [m]\n"
            "Debe ser menor que la altura del canal H"
        )

        fd.addRow("Longitud presa (x):", self._sb_dam_len)
        fd.addRow("Altura presa (y):",   self._sb_dam_hei)

        # Indicadores de fracciones resultantes
        self._lbl_dam_frac = QLabel("= 25.0% de L  ×  50.0% de H")
        self._lbl_dam_frac.setStyleSheet("color:#2C5F8A; font-size:10px;")
        fd.addRow("", self._lbl_dam_frac)

        # Indicador de validación de la presa
        self._lbl_dam_warn = QLabel("")
        self._lbl_dam_warn.setStyleSheet("color:#E85A30; font-size:10px;")
        self._lbl_dam_warn.setWordWrap(True)
        fd.addRow("", self._lbl_dam_warn)

        note = QLabel(
            "El fluido ocupa el 100% del ancho W\n"
            "(paredes laterales físicas en ambos lados)"
        )
        note.setStyleSheet("color:#888; font-size:10px; font-style:italic;")
        note.setWordWrap(True)
        fd.addRow("", note)
        left.addWidget(g_dam)

        # ── Validación general ────────────────────────────────────────────────
        self._lbl_valid = QLabel("")
        self._lbl_valid.setStyleSheet("font-size:10px;")
        self._lbl_valid.setWordWrap(True)
        left.addWidget(self._lbl_valid)
        left.addStretch()

        # Botones
        btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Aplicar cambios")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        left.addWidget(btns)

        root.addLayout(left, stretch=1)

        # Separador
        sep = QFrame(); sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color:#DDD;")
        root.addWidget(sep)

        # ── Derecha: doble preview ────────────────────────────────────────────
        right = QVBoxLayout(); right.setSpacing(4)
        lbl_prev = QLabel(
            "Previsualización — vista lateral (x-y) y en planta (x-z)")
        lbl_prev.setFont(QFont("Arial", 9, QFont.Bold))
        right.addWidget(lbl_prev)
        self._preview = GeometryPreviewWidget()
        right.addWidget(self._preview)
        root.addLayout(right, stretch=2)

        # ── Conectar señales ──────────────────────────────────────────────────
        # Canal: al cambiar L o H, actualizar el máximo de la presa
        self._sb_L.valueChanged.connect(self._on_canal_changed)
        self._sb_H.valueChanged.connect(self._on_canal_changed)
        for w in [self._sb_W, self._sb_dam_len, self._sb_dam_hei]:
            w.valueChanged.connect(self._schedule)
        for w in [self._sb_nx, self._sb_ny, self._sb_nz]:
            w.valueChanged.connect(self._schedule)

    # ── Helpers de creación de spinboxes ──────────────────────────────────────

    @staticmethod
    def _dspin(v, lo, hi, dec, suf, tip="") -> QDoubleSpinBox:
        sb = QDoubleSpinBox()
        sb.setRange(lo, hi); sb.setDecimals(dec); sb.setValue(v)
        sb.setSuffix(suf); sb.setToolTip(tip)
        sb.setSingleStep(max(v * 0.05, 0.001))
        return sb

    @staticmethod
    def _ispin(v, lo, hi, tip="") -> QSpinBox:
        sb = QSpinBox(); sb.setRange(lo, hi); sb.setValue(v)
        sb.setToolTip(tip); sb.setSingleStep(5)
        return sb

    # ── Lógica de actualización ───────────────────────────────────────────────

    def _on_canal_changed(self) -> None:
        """
        Al cambiar L o H, ajusta el máximo permitido de los spinboxes
        de la presa y clampea si el valor actual excede el nuevo canal.
        """
        L = self._sb_L.value()
        H = self._sb_H.value()

        # Actualizar paso sugerido proporcional al canal
        self._sb_L.setSingleStep(max(L * 0.05, 0.01))
        self._sb_H.setSingleStep(max(H * 0.05, 0.01))

        # Limitar el rango de la presa sin emitir señales extra
        self._sb_dam_len.blockSignals(True)
        self._sb_dam_hei.blockSignals(True)

        # El máximo de la presa es 99% del canal (nunca igual)
        max_dam_len = round(L * 0.99, 3)
        max_dam_hei = round(H * 0.99, 3)
        self._sb_dam_len.setMaximum(max_dam_len)
        self._sb_dam_hei.setMaximum(max_dam_hei)

        # Clampear valores si exceden el nuevo canal
        if self._sb_dam_len.value() >= L:
            self._sb_dam_len.setValue(min(self._sb_dam_len.value(), max_dam_len))
        if self._sb_dam_hei.value() >= H:
            self._sb_dam_hei.setValue(min(self._sb_dam_hei.value(), max_dam_hei))

        self._sb_dam_len.blockSignals(False)
        self._sb_dam_hei.blockSignals(False)

        self._schedule()

    def _schedule(self) -> None:
        self._timer.start(150)

    def _update_preview(self) -> None:
        L   = self._sb_L.value()
        H   = self._sb_H.value()
        dam_l = self._sb_dam_len.value()
        dam_h = self._sb_dam_hei.value()

        # Calcular y mostrar fracciones resultantes
        frac_l = dam_l / L * 100 if L > 0 else 0
        frac_h = dam_h / H * 100 if H > 0 else 0
        self._lbl_dam_frac.setText(
            f"= {frac_l:.1f}% de L  ×  {frac_h:.1f}% de H"
        )

        # Advertencia en tiempo real si la presa excede el canal
        warnings = []
        if dam_l >= L:
            warnings.append(
                f"⚠ Longitud presa ({dam_l:.3f}m) ≥ canal ({L:.3f}m)"
            )
        if dam_h >= H:
            warnings.append(
                f"⚠ Altura presa ({dam_h:.3f}m) ≥ canal ({H:.3f}m)"
            )
        self._lbl_dam_warn.setText("\n".join(warnings))

        geo    = self.get_geometry()
        errors = geo.validate()
        preview = geo.compute_preview()

        self._lbl_cells.setText(f"{preview['cell_count']:,} celdas")
        self._lbl_dx.setText(
            f"Δx={preview['dx']*1000:.1f}mm  "
            f"Δy={preview['dy']*1000:.1f}mm  "
            f"Δz={preview['dz']*1000:.1f}mm"
        )

        all_errors = warnings + errors
        if all_errors:
            self._lbl_valid.setText("⚠ " + all_errors[0])
            self._lbl_valid.setStyleSheet("font-size:10px; color:#E85A30;")
        else:
            self._lbl_valid.setText("✓ Geometría válida")
            self._lbl_valid.setStyleSheet("font-size:10px; color:#1AA870;")

        self._preview.render_preview(preview)

    def _on_accept(self) -> None:
        geo = self.get_geometry()
        errors = geo.validate()
        L = self._sb_L.value()
        H = self._sb_H.value()
        dam_l = self._sb_dam_len.value()
        dam_h = self._sb_dam_hei.value()

        if dam_l >= L or dam_h >= H:
            self._update_preview()   # mostrar advertencias
            return                   # no aceptar

        if not errors:
            self.result_geometry = geo
            self.accept()
        else:
            self._update_preview()

    # ── API pública ───────────────────────────────────────────────────────────

    def get_geometry(self) -> GeometryConfig:
        """Construye GeometryConfig con las dimensiones actuales del diálogo."""
        L = self._sb_L.value()
        H = self._sb_H.value()
        dam_l = min(self._sb_dam_len.value(), L * 0.99)
        dam_h = min(self._sb_dam_hei.value(), H * 0.99)
        return GeometryConfig(
            length          = L,
            height          = H,
            width           = self._sb_W.value(),
            nx              = self._sb_nx.value(),
            ny              = self._sb_ny.value(),
            nz              = self._sb_nz.value(),
            dam_width_frac  = dam_l / L if L > 0 else 0.25,
            dam_height_frac = dam_h / H if H > 0 else 0.50,
        )

    def set_geometry(self, geo: GeometryConfig) -> None:
        """Carga una GeometryConfig existente en el formulario."""
        # Canal
        self._sb_L.setValue(geo.length)
        self._sb_H.setValue(geo.height)
        self._sb_W.setValue(geo.width)

        # Malla
        self._sb_nx.setValue(geo.nx)
        self._sb_ny.setValue(geo.ny)
        self._sb_nz.setValue(geo.nz)

        # Presa: convertir fracción → metros
        dam_len = geo.dam_width_frac  * geo.length
        dam_hei = geo.dam_height_frac * geo.height

        # Primero actualizar límites según el canal actual
        self._sb_dam_len.setMaximum(round(geo.length * 0.99, 3))
        self._sb_dam_hei.setMaximum(round(geo.height * 0.99, 3))

        self._sb_dam_len.setValue(dam_len)
        self._sb_dam_hei.setValue(dam_hei)

        self._update_preview()
