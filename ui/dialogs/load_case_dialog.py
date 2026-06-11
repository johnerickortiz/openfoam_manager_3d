"""
Diálogo para seleccionar un caso OpenFOAM existente en disco.

Escanea el directorio de salida buscando carpetas que contengan
una estructura válida de caso OpenFOAM (constant/, system/, y al
menos un directorio de tiempo numérico > 0).

Muestra cada caso con: nombre, número de pasos, rango de tiempo.
"""
from __future__ import annotations
from pathlib import Path

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QDialogButtonBox, QFrame, QAbstractItemView, QLineEdit,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor




def _scan_cases(output_dir: Path) -> list[dict]:
    """
    Devuelve lista de casos OpenFOAM válidos en output_dir.

    Un directorio se considera caso válido si tiene:
        - constant/   (propiedades del fluido)
        - system/     (configuración de malla)
        - Al menos un directorio de tiempo numérico > 0 (resultados)
    """
    if not output_dir.exists():
        return []

    cases = []
    for d in sorted(output_dir.iterdir()):
        if not d.is_dir():
            continue
        if not (d / "constant").exists():
            continue
        if not (d / "system").exists():
            continue

        time_dirs = []
        for sub in d.iterdir():
            if sub.is_dir():
                try:
                    t = float(sub.name)
                    if t > 0:
                        time_dirs.append(t)
                except ValueError:
                    pass

        if not time_dirs:
            continue

        time_dirs.sort()
        cases.append({
            "name":    d.name,
            "path":    d,
            "n_steps": len(time_dirs),
            "t_start": time_dirs[0],
            "t_end":   time_dirs[-1],
            "has_0":   (d / "0").exists(),
        })

    return cases


class LoadCaseDialog(QDialog):
    """
    Diálogo para seleccionar un caso OpenFOAM desde disco.

    Resultado:
        dialog.selected_case  →  dict con keys: name, path, n_steps, t_start, t_end
                                 o None si se canceló.
    """

    def __init__(self, output_dir: str | Path, parent=None) -> None:
        super().__init__(parent)
        self.selected_case: dict | None = None
        self._output_dir = Path(output_dir).expanduser()
        self.setWindowTitle("Cargar caso")
        self.setMinimumSize(620, 420)
        self.setModal(True)
        self._setup_ui()
        self._scan()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(16, 16, 16, 16)

        # ── Directorio de salida ──────────────────────────────────────────────
        dir_grp = QFrame()
        dir_grp.setStyleSheet(
            "QFrame{background:#F0F4F8;border:1px solid #D0D8E4;"
            "border-radius:5px;}"
        )
        dir_lay = QHBoxLayout(dir_grp)
        dir_lay.setContentsMargins(10, 8, 10, 8)

        lbl_dir = QLabel("Directorio de salida:")
        lbl_dir.setFont(QFont("Arial", 9, QFont.Bold))
        lbl_dir.setStyleSheet("border:none;background:transparent;")
        dir_lay.addWidget(lbl_dir)

        self._edit_dir = QLineEdit(str(self._output_dir))
        self._edit_dir.setReadOnly(True)
        self._edit_dir.setStyleSheet(
            "QLineEdit{background:white;border:1px solid #CBD5E1;"
            "border-radius:4px;padding:3px 6px;font-size:11px;}"
        )
        dir_lay.addWidget(self._edit_dir, stretch=1)

        btn_browse = QPushButton("Cambiar...")
        btn_browse.setFixedHeight(28)
        btn_browse.setStyleSheet(
            "QPushButton{background:#F0F4F8;border:1px solid #CBD5E1;"
            "border-radius:4px;font-size:11px;}"
            "QPushButton:hover{background:#E2EAF5;}"
        )
        btn_browse.clicked.connect(self._browse)
        dir_lay.addWidget(btn_browse)

        root.addWidget(dir_grp)

        # ── Etiqueta de estado ─────────────────────────────────────────────────
        self._lbl_status = QLabel("Buscando casos...")
        self._lbl_status.setStyleSheet("color:#666;font-size:10px;")
        root.addWidget(self._lbl_status)

        # ── Tabla de casos ─────────────────────────────────────────────────────
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(
            ["Nombre del caso", "Pasos", "t inicio", "t fin"]
        )
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch
        )
        for col in [1, 2, 3]:
            self._table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeToContents
            )
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setStyleSheet(
            "QTableWidget{border:1px solid #D0D8E4;border-radius:4px;"
            "gridline-color:#EEF2F7;}"
            "QTableWidget::item{padding:6px 8px;}"
            "QTableWidget::item:selected{background:#D6E4F5;color:#1A3D5C;}"
            "QHeaderView::section{background:#F0F4F8;border:none;"
            "border-bottom:1px solid #D0D8E4;padding:6px;font-weight:bold;"
            "font-size:11px;}"
        )
        self._table.itemDoubleClicked.connect(self._on_accept)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        root.addWidget(self._table, stretch=1)

        # ── Nota informativa ──────────────────────────────────────────────────
        note = QLabel(
            "Solo se muestran carpetas con estructura válida de OpenFOAM "
            "(constant/, system/ y al menos un paso de tiempo)."
        )
        note.setStyleSheet("color:#AAA;font-size:10px;font-style:italic;")
        note.setWordWrap(True)
        root.addWidget(note)

        # ── Botones ───────────────────────────────────────────────────────────
        btns = QDialogButtonBox()
        self._btn_load = btns.addButton(
            "📂  Cargar caso", QDialogButtonBox.AcceptRole
        )
        self._btn_load.setEnabled(False)
        self._btn_load.setStyleSheet(
            "QPushButton{background:#2C5F8A;color:white;border-radius:5px;"
            "font-weight:bold;padding:5px 16px;}"
            "QPushButton:hover{background:#3A78B5;}"
            "QPushButton:disabled{background:#AAA;}"
        )
        btns.addButton("Cancelar", QDialogButtonBox.RejectRole)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    # ── Escaneo ───────────────────────────────────────────────────────────────

    def _scan(self) -> None:
        self._table.setRowCount(0)
        self._lbl_status.setText("Buscando casos...")
        self._lbl_status.setStyleSheet("color:#666;font-size:10px;")
        # Escaneo síncrono — listar directorios es instantáneo
        cases = _scan_cases(self._output_dir)
        self._populate(cases)

    def _populate(self, cases: list[dict]) -> None:
        self._table.setRowCount(0)

        if not cases:
            self._lbl_status.setText(
                f"No se encontraron casos en: {self._output_dir}"
            )
            return

        self._lbl_status.setText(
            f"  {len(cases)} caso{'s' if len(cases) != 1 else ''} "
            f"encontrado{'s' if len(cases) != 1 else ''} "
            f"en: {self._output_dir}"
        )
        self._lbl_status.setStyleSheet("color:#1AA870;font-size:10px;")

        for row, c in enumerate(cases):
            self._table.insertRow(row)
            self._table.setRowHeight(row, 34)

            # Nombre
            item_name = QTableWidgetItem(f"  {c['name']}")
            item_name.setData(Qt.UserRole, c)
            item_name.setFont(QFont("Arial", 10, QFont.Bold))
            self._table.setItem(row, 0, item_name)

            # Pasos
            item_n = QTableWidgetItem(f"  {c['n_steps']:,}")
            item_n.setTextAlignment(Qt.AlignCenter)
            item_n.setForeground(QColor("#2C5F8A"))
            self._table.setItem(row, 1, item_n)

            # t inicio
            item_t0 = QTableWidgetItem(f"  {c['t_start']:.4g} s")
            item_t0.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 2, item_t0)

            # t fin
            item_t1 = QTableWidgetItem(f"  {c['t_end']:.4g} s")
            item_t1.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 3, item_t1)

        # Seleccionar primero por defecto
        self._table.selectRow(0)

    # ── Acciones ──────────────────────────────────────────────────────────────

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Seleccionar directorio de salida",
            str(self._output_dir),
        )
        if path:
            self._output_dir = Path(path)
            self._edit_dir.setText(str(self._output_dir))
            self._lbl_status.setStyleSheet("color:#666;font-size:10px;")
            self._scan()

    def _on_selection_changed(self) -> None:
        self._btn_load.setEnabled(
            len(self._table.selectedItems()) > 0
        )

    def _on_accept(self) -> None:
        rows = self._table.selectedItems()
        if not rows:
            return
        row = self._table.row(rows[0])
        item = self._table.item(row, 0)
        if item:
            self.selected_case = item.data(Qt.UserRole)
            self.accept()
