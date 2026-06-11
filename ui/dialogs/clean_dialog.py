"""
Diálogo de confirmación para limpiar resultados.

Presenta tres opciones:
    Limpiar resultados    — elimina solo los directorios de tiempo (0.05/, 0.10/ ...)
                            conserva la malla, condiciones iniciales y configuración.
    Eliminar caso completo — elimina toda la carpeta del caso en disco.
    Cancelar              — no hace nada.
"""
from __future__ import annotations
from pathlib import Path

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class CleanDialog(QDialog):
    """
    Diálogo de confirmación antes de limpiar un caso OpenFOAM.

    Resultado accesible via:
        dialog.action  →  "results" | "full" | "cancel"

    Uso:
        dlg = CleanDialog(case_dir=config.case_dir, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            if dlg.action == "results":
                runner.clean_results(case_dir)
            elif dlg.action == "full":
                runner.clean_full_case(case_dir)
    """

    def __init__(self, case_dir: Path, parent=None) -> None:
        super().__init__(parent)
        self.action = "cancel"
        self._case_dir = case_dir
        self.setWindowTitle("Limpiar caso")
        self.setMinimumWidth(500)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(20, 20, 20, 20)

        # ── Cabecera ──────────────────────────────────────────────────────────
        hdr = QHBoxLayout(); hdr.setSpacing(12)

        icon = QLabel("🗑")
        icon.setFont(QFont("Arial", 26))
        icon.setFixedWidth(40)
        icon.setAlignment(Qt.AlignTop)
        hdr.addWidget(icon)

        info = QVBoxLayout(); info.setSpacing(4)
        lbl_title = QLabel("¿Qué deseas limpiar?")
        lbl_title.setFont(QFont("Arial", 12, QFont.Bold))
        info.addWidget(lbl_title)

        lbl_path = QLabel(
            f"Caso: <code style='color:#2C5F8A;'>{self._case_dir.name}</code><br>"
            f"<span style='color:#888; font-size:11px;'>{self._case_dir}</span>"
        )
        lbl_path.setTextFormat(Qt.RichText)
        lbl_path.setWordWrap(True)
        info.addWidget(lbl_path)
        hdr.addLayout(info)
        root.addLayout(hdr)

        # Separador
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:#E5E7EB;")
        root.addWidget(sep)

        # ── Opción 1: Solo resultados ─────────────────────────────────────────
        root.addWidget(self._make_option(
            icon     = "⏱",
            title    = "Limpiar resultados",
            color    = "#E8A030",
            bg       = "#FFF8F0",
            border   = "#F0D0A0",
            desc     = (
                "Elimina los directorios de tiempo (<code>0.05/</code>, "
                "<code>0.10/</code>, …).<br>"
                "Conserva la malla (<code>constant/</code>), "
                "las condiciones iniciales (<code>0/</code>) "
                "y la configuración (<code>system/</code>).<br>"
                "<b>La simulación se puede volver a ejecutar sin regenerar el caso.</b>"
            ),
            btn_text = "Limpiar solo resultados",
            btn_clr  = "#E8A030",
            btn_hov  = "#D08020",
            action   = "results",
        ))

        # ── Opción 2: Caso completo ───────────────────────────────────────────
        root.addWidget(self._make_option(
            icon     = "💣",
            title    = "Eliminar caso completo",
            color    = "#DC2626",
            bg       = "#FFF5F5",
            border   = "#FCA5A5",
            desc     = (
                "Elimina <b>toda la carpeta</b> del caso en disco, "
                "incluyendo malla, condiciones iniciales, "
                "configuración y resultados.<br>"
                "<b>Esta acción no se puede deshacer.</b>"
            ),
            btn_text = "Eliminar caso completo",
            btn_clr  = "#DC2626",
            btn_hov  = "#B91C1C",
            action   = "full",
        ))

        # ── Cancelar ──────────────────────────────────────────────────────────
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setFixedHeight(28)
        btn_cancel.setStyleSheet(
            "QPushButton{background:#F3F4F6;border:1px solid #D1D5DB;"
            "border-radius:4px;color:#555;font-size:11px;}"
            "QPushButton:hover{background:#E5E7EB;}")
        btn_cancel.clicked.connect(self.reject)
        root.addWidget(btn_cancel, alignment=Qt.AlignRight)

    def _make_option(
        self,
        icon:     str,
        title:    str,
        color:    str,
        bg:       str,
        border:   str,
        desc:     str,
        btn_text: str,
        btn_clr:  str,
        btn_hov:  str,
        action:   str,
    ) -> QFrame:
        """Crea un bloque de opción con ícono, descripción y botón de acción."""
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame{{background:{bg};border:1px solid {border};"
            f"border-radius:6px;}}"
        )
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        # Cabecera de la opción
        hdr = QHBoxLayout(); hdr.setSpacing(8)
        ico_lbl = QLabel(icon)
        ico_lbl.setFont(QFont("Arial", 16))
        ico_lbl.setStyleSheet("border:none; background:transparent;")
        hdr.addWidget(ico_lbl)
        ttl = QLabel(title)
        ttl.setFont(QFont("Arial", 10, QFont.Bold))
        ttl.setStyleSheet(f"color:{color}; border:none; background:transparent;")
        hdr.addWidget(ttl)
        hdr.addStretch()
        lay.addLayout(hdr)

        # Descripción
        desc_lbl = QLabel(desc)
        desc_lbl.setTextFormat(Qt.RichText)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(
            "color:#555; font-size:11px; border:none; background:transparent;")
        lay.addWidget(desc_lbl)

        # Botón de acción
        btn = QPushButton(f"  {btn_text}")
        btn.setFixedHeight(30)
        btn.setStyleSheet(
            f"QPushButton{{background:{btn_clr};color:white;border-radius:5px;"
            f"font-weight:bold;font-size:11px;border:none;}}"
            f"QPushButton:hover{{background:{btn_hov};}}")
        btn.clicked.connect(lambda: self._choose(action))
        lay.addWidget(btn)

        return frame

    def _choose(self, action: str) -> None:
        self.action = action
        self.accept()
