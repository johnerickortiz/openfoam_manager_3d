"""
Diálogo de conflicto de nombre de caso.

Aparece cuando el directorio de salida ya contiene un caso con el mismo nombre.
Ofrece tres opciones:
    - Sobreescribir: elimina el caso existente y continúa con el mismo nombre
    - Renombrar:     usa un nombre sugerido automáticamente (sufijo _1, _2, ...)
    - Cancelar:      no hace nada
"""
from __future__ import annotations

from pathlib import Path

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QFrame, QSizePolicy,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QIcon


class CaseConflictDialog(QDialog):
    """
    Diálogo modal que avisa de un conflicto de nombre y permite resolverlo.

    Resultado accesible via:
        dialog.action  →  "overwrite" | "rename" | "cancel"
        dialog.new_name →  nombre final del caso (con o sin sufijo)

    Ejemplo de uso:
        dlg = CaseConflictDialog(
            existing_path = Path("C:/casos/damBreakLodo"),
            suggested_name = "damBreakLodo_1",
            parent = self,
        )
        if dlg.exec_() == QDialog.Accepted:
            config.name = dlg.new_name
            if dlg.action == "overwrite":
                clean_case(config.case_dir)
    """

    def __init__(
        self,
        existing_path:  Path,
        suggested_name: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.action   = "cancel"
        self.new_name = suggested_name

        self._existing_path  = existing_path
        self._suggested_name = suggested_name

        self.setWindowTitle("Caso ya existente")
        self.setMinimumWidth(480)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # ── Icono + mensaje principal ─────────────────────────────────────────
        top_row = QHBoxLayout()
        top_row.setSpacing(14)

        icon_lbl = QLabel("⚠")
        icon_lbl.setFont(QFont("Arial", 28))
        icon_lbl.setStyleSheet("color: #E8A030;")
        icon_lbl.setFixedWidth(42)
        top_row.addWidget(icon_lbl, alignment=Qt.AlignTop)

        msg_col = QVBoxLayout()
        msg_col.setSpacing(6)

        lbl_title = QLabel("El caso ya existe")
        lbl_title.setFont(QFont("Arial", 12, QFont.Bold))
        msg_col.addWidget(lbl_title)

        lbl_path = QLabel(
            f"Ya existe un caso en:\n"
            f"<code style='color:#2C5F8A;'>{self._existing_path}</code>"
        )
        lbl_path.setTextFormat(Qt.RichText)
        lbl_path.setWordWrap(True)
        lbl_path.setStyleSheet("color: #444; font-size: 11px;")
        msg_col.addWidget(lbl_path)

        lbl_question = QLabel("¿Qué deseas hacer?")
        lbl_question.setFont(QFont("Arial", 10))
        lbl_question.setStyleSheet("color: #333; margin-top: 4px;")
        msg_col.addWidget(lbl_question)

        top_row.addLayout(msg_col)
        layout.addLayout(top_row)

        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #E0E0E0;")
        layout.addWidget(sep)

        # ── Opción 1: Sobreescribir ───────────────────────────────────────────
        ovw_frame = QFrame()
        ovw_frame.setStyleSheet(
            "QFrame { background: #FFF8F0; border: 1px solid #F0D0A0; "
            "border-radius: 6px; }"
        )
        ovw_lay = QVBoxLayout(ovw_frame)
        ovw_lay.setContentsMargins(12, 10, 12, 10)
        ovw_lay.setSpacing(6)

        ovw_header = QHBoxLayout()
        lbl_ovw_icon = QLabel("🗑")
        lbl_ovw_icon.setFont(QFont("Arial", 14))
        ovw_header.addWidget(lbl_ovw_icon)
        lbl_ovw_title = QLabel("Sobreescribir")
        lbl_ovw_title.setFont(QFont("Arial", 10, QFont.Bold))
        lbl_ovw_title.setStyleSheet("color: #B05010;")
        ovw_header.addWidget(lbl_ovw_title)
        ovw_header.addStretch()
        ovw_lay.addLayout(ovw_header)

        lbl_ovw_desc = QLabel(
            "Elimina todos los resultados anteriores y ejecuta la simulación "
            "con el mismo nombre. Esta acción no se puede deshacer."
        )
        lbl_ovw_desc.setWordWrap(True)
        lbl_ovw_desc.setStyleSheet("color: #666; font-size: 10px;")
        ovw_lay.addWidget(lbl_ovw_desc)

        btn_ovw = QPushButton("  Sobreescribir caso existente")
        btn_ovw.setFixedHeight(32)
        btn_ovw.setStyleSheet(
            "QPushButton { background:#E8A030; color:white; border-radius:5px; "
            "font-weight:bold; font-size:11px; }"
            "QPushButton:hover { background:#D08020; }"
        )
        btn_ovw.clicked.connect(self._on_overwrite)
        ovw_lay.addWidget(btn_ovw)
        layout.addWidget(ovw_frame)

        # ── Opción 2: Renombrar ───────────────────────────────────────────────
        ren_frame = QFrame()
        ren_frame.setStyleSheet(
            "QFrame { background: #F0F8FF; border: 1px solid #A0C8F0; "
            "border-radius: 6px; }"
        )
        ren_lay = QVBoxLayout(ren_frame)
        ren_lay.setContentsMargins(12, 10, 12, 10)
        ren_lay.setSpacing(6)

        ren_header = QHBoxLayout()
        lbl_ren_icon = QLabel("✏")
        lbl_ren_icon.setFont(QFont("Arial", 14))
        ren_header.addWidget(lbl_ren_icon)
        lbl_ren_title = QLabel("Renombrar caso")
        lbl_ren_title.setFont(QFont("Arial", 10, QFont.Bold))
        lbl_ren_title.setStyleSheet("color: #1A5F9A;")
        ren_header.addWidget(lbl_ren_title)
        ren_header.addStretch()
        ren_lay.addLayout(ren_header)

        lbl_ren_desc = QLabel(
            "Crea el nuevo caso con un nombre diferente, conservando "
            "el caso existente intacto."
        )
        lbl_ren_desc.setWordWrap(True)
        lbl_ren_desc.setStyleSheet("color: #666; font-size: 10px;")
        ren_lay.addWidget(lbl_ren_desc)

        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        lbl_name = QLabel("Nuevo nombre:")
        lbl_name.setFont(QFont("Arial", 9))
        name_row.addWidget(lbl_name)

        self._edit_name = QLineEdit(self._suggested_name)
        self._edit_name.setFont(QFont("Arial", 9))
        self._edit_name.setStyleSheet(
            "QLineEdit { border: 1px solid #2C5F8A; border-radius: 4px; "
            "padding: 4px 8px; background: white; }"
        )
        self._edit_name.textChanged.connect(self._validate_name)
        name_row.addWidget(self._edit_name)
        ren_lay.addLayout(name_row)

        self._lbl_name_error = QLabel("")
        self._lbl_name_error.setStyleSheet("color:#E85A30; font-size:10px;")
        ren_lay.addWidget(self._lbl_name_error)

        self._btn_rename = QPushButton("  Usar nombre nuevo")
        self._btn_rename.setFixedHeight(32)
        self._btn_rename.setStyleSheet(
            "QPushButton { background:#2C5F8A; color:white; border-radius:5px; "
            "font-weight:bold; font-size:11px; }"
            "QPushButton:hover { background:#3A78B5; }"
            "QPushButton:disabled { background:#AAA; }"
        )
        self._btn_rename.clicked.connect(self._on_rename)
        ren_lay.addWidget(self._btn_rename)
        layout.addWidget(ren_frame)

        # ── Cancelar ─────────────────────────────────────────────────────────
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setFixedHeight(28)
        btn_cancel.setStyleSheet(
            "QPushButton { background:#F0F4F8; border:1px solid #CBD5E1; "
            "border-radius:4px; color:#555; }"
            "QPushButton:hover { background:#E2EAF5; }"
        )
        btn_cancel.clicked.connect(self.reject)
        layout.addWidget(btn_cancel, alignment=Qt.AlignRight)

        # Validación inicial
        self._validate_name(self._suggested_name)

    # ── Validación ────────────────────────────────────────────────────────────

    def _validate_name(self, name: str) -> None:
        """Valida el nombre propuesto y habilita/deshabilita el botón."""
        name = name.strip()
        if not name:
            self._lbl_name_error.setText("El nombre no puede estar vacío.")
            self._btn_rename.setEnabled(False)
            return

        # Solo letras, números, guiones y guiones bajos
        import re
        if not re.match(r'^[\w\-]+$', name):
            self._lbl_name_error.setText(
                "Solo letras, números, _ y - (sin espacios ni caracteres especiales)."
            )
            self._btn_rename.setEnabled(False)
            return

        # Verificar que no coincida con el caso existente
        if name == self._existing_path.name:
            self._lbl_name_error.setText(
                "Es el mismo nombre que el caso existente."
            )
            self._btn_rename.setEnabled(False)
            return

        # Verificar que el nuevo directorio tampoco exista
        new_path = self._existing_path.parent / name
        if new_path.exists():
            self._lbl_name_error.setText(
                f"'{name}' también existe. Elige otro nombre."
            )
            self._btn_rename.setEnabled(False)
            return

        self._lbl_name_error.setText("")
        self._btn_rename.setEnabled(True)

    # ── Acciones ──────────────────────────────────────────────────────────────

    def _on_overwrite(self) -> None:
        self.action   = "overwrite"
        self.new_name = self._existing_path.name
        self.accept()

    def _on_rename(self) -> None:
        name = self._edit_name.text().strip()
        if name:
            self.action   = "rename"
            self.new_name = name
            self.accept()


# ── Función auxiliar ──────────────────────────────────────────────────────────

def suggest_next_name(base_name: str, output_dir: Path) -> str:
    """
    Genera el siguiente nombre disponible con sufijo numérico.

    Ejemplos:
        "damBreakLodo"   →  "damBreakLodo_1"  (si no existe)
        "damBreakLodo_1" →  "damBreakLodo_2"  (si _1 ya existe)

    Args:
        base_name:  Nombre del caso que ya existe.
        output_dir: Directorio donde se guardan los casos.

    Returns:
        Primer nombre disponible con sufijo _N.
    """
    import re
    # Extraer base sin sufijo numérico existente
    match = re.match(r'^(.+?)(_\d+)?$', base_name)
    stem  = match.group(1) if match else base_name

    for i in range(1, 1000):
        candidate = f"{stem}_{i}"
        if not (output_dir / candidate).exists():
            return candidate

    return f"{stem}_new"
