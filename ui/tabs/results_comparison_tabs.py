"""
Pestañas de resultados y comparación.

ResultsTab:     carga resultados de una simulación y muestra gráficas.
ComparisonTab:  compara N simulaciones + datos experimentales.
"""
from __future__ import annotations

from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QComboBox, QFileDialog,
    QListWidget, QListWidgetItem, QSizePolicy,
    QSplitter, QMessageBox, QFrame,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QFont, QColor

from services.exporter import ExportFormat
from ui.widgets.plot_widget import PlotWidget


# ── ResultsTab ────────────────────────────────────────────────────────────────

class ResultsTab(QWidget):
    """
    Pestaña de resultados con selector de gráfica individual.

    Muestra UNA gráfica a la vez, seleccionable con un QComboBox
    en la parte superior izquierda. Incluye métricas resumen y
    botones de exportación.

    Señales:
        load_requested():            Usuario solicita cargar resultados.
        export_requested(ExportFormat): Usuario solicita exportación.
    """

    load_requested   = pyqtSignal()
    export_requested = pyqtSignal(object)  # ExportFormat

    # Definición de todas las gráficas disponibles
    # (key, label, solo_3d)
    _PANEL_DEFS = [
        ("front_position", "Posición del frente  X(t)",          False),
        ("front_velocity", "Velocidad del frente  V(t)",          False),
        ("fluid_volume",   "Volumen del fluido  Vol(t)",          False),
        ("height_profile", "Perfil de altura lateral  h(x, t)",  False),
        ("plan_view",      "Vista en planta (x-z) — cámara superior", True),
        ("transversal",    "Perfil transversal  h(z, t)",         True),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_plot_data: dict | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        main = QVBoxLayout(self)
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(8)

        # ── Barra superior ────────────────────────────────────────────────────
        bar = QHBoxLayout(); bar.setSpacing(8)

        # Cargar resultados
        self._btn_load = QPushButton("⟳  Recargar resultados")
        self._btn_load.setFixedHeight(28)
        self._btn_load.setToolTip(
            "Recarga las métricas del caso activo.\n"
            "Para cargar un caso diferente, use '📂 Cargar caso' en el panel izquierdo."
        )
        self._btn_load.setStyleSheet(
            "QPushButton{background:#F0F4F8;border:1px solid #CBD5E1;"
            "border-radius:4px;font-size:11px;padding:0 10px;}"
            "QPushButton:hover{background:#E2EAF5;border-color:#2C5F8A;}")
        self._btn_load.clicked.connect(self.load_requested)
        bar.addWidget(self._btn_load)

        # Separador visual
        sep = QLabel("|"); sep.setStyleSheet("color:#CCC;"); bar.addWidget(sep)

        # Selector de gráfica (dropdown principal)
        lbl_sel = QLabel("Gráfica:")
        lbl_sel.setFont(QFont("Arial", 9))
        bar.addWidget(lbl_sel)

        self._combo_panel = QComboBox()
        self._combo_panel.setFixedHeight(30)
        self._combo_panel.setMinimumWidth(300)
        self._combo_panel.setStyleSheet(
            "QComboBox{border:1px solid #CBD5E1;border-radius:4px;"
            "padding:2px 8px;background:white;font-size:11px;}"
            "QComboBox:focus{border:1px solid #2C5F8A;}"
            "QComboBox::drop-down{border:none;}"
            "QComboBox::down-arrow{image:none;width:12px;}")
        # Poblar con las opciones no-3D inicialmente
        for key, label, solo_3d in self._PANEL_DEFS:
            if not solo_3d:
                self._combo_panel.addItem(label, key)
        self._combo_panel.setEnabled(False)
        self._combo_panel.currentIndexChanged.connect(self._on_panel_changed)
        bar.addWidget(self._combo_panel)

        bar.addStretch()

        # Exportación
        lbl_exp = QLabel("Exportar:")
        lbl_exp.setFont(QFont("Arial", 9))
        bar.addWidget(lbl_exp)

        for fmt in [ExportFormat.CSV, ExportFormat.EXCEL,
                    ExportFormat.JSON, ExportFormat.PNG]:
            btn = QPushButton(fmt.value.upper())
            btn.setFixedHeight(28); btn.setFixedWidth(58)
            btn.setToolTip(fmt.display_name)
            btn.clicked.connect(lambda checked, f=fmt: self.export_requested.emit(f))
            btn.setStyleSheet(
                "QPushButton{background:#F0F4F8;border:1px solid #CBD5E1;"
                "border-radius:4px;font-size:11px;}"
                "QPushButton:hover{background:#E2EAF5;}")
            bar.addWidget(btn)

        main.addLayout(bar)

        # ── Splitter: gráfica (izq) + métricas (der) ──────────────────────────
        splitter = QSplitter(Qt.Horizontal)

        self._plot = PlotWidget(figsize=(11, 7), show_toolbar=True)
        splitter.addWidget(self._plot)

        # Métricas resumen
        mw = QWidget(); mw.setFixedWidth(190)
        ml = QVBoxLayout(mw)
        ml.setContentsMargins(6, 4, 6, 4); ml.setSpacing(7)

        hdr = QLabel("Métricas resumen")
        hdr.setFont(QFont("Arial", 9, QFont.Bold)); ml.addWidget(hdr)

        self._metrics_widgets = {}
        for key, label, unit in [
            ("final_extent",  "Frente final",    "m"),
            ("max_velocity",  "V máxima",         "m/s"),
            ("final_volume",  "Volumen final",    "m³"),
            ("final_area",    "Área proyectada",  "m²"),
            ("n_time_steps",  "Pasos de tiempo",  ""),
        ]:
            grp = QGroupBox(label); grp.setFont(QFont("Arial", 8))
            gl  = QVBoxLayout(grp); gl.setContentsMargins(5, 5, 5, 5)
            vl  = QLabel("—"); vl.setAlignment(Qt.AlignCenter)
            vl.setFont(QFont("Arial", 12, QFont.Bold))
            vl.setStyleSheet("color:#2C5F8A;")
            ul  = QLabel(unit); ul.setAlignment(Qt.AlignCenter)
            ul.setStyleSheet("color:#888;font-size:10px;")
            gl.addWidget(vl); gl.addWidget(ul)
            ml.addWidget(grp)
            self._metrics_widgets[key] = vl

        ml.addStretch()
        splitter.addWidget(mw)
        splitter.setSizes([780, 190])
        main.addWidget(splitter)

        self._show_empty_state()

    # ── Selector de gráfica ───────────────────────────────────────────────────

    def _populate_combo(self, is_3d: bool) -> None:
        """Rellena el combo con las opciones disponibles según si es 3D."""
        prev_key = self._combo_panel.currentData()
        self._combo_panel.blockSignals(True)
        self._combo_panel.clear()

        for key, label, solo_3d in self._PANEL_DEFS:
            if solo_3d and not is_3d:
                continue
            self._combo_panel.addItem(label, key)

        # Restaurar selección previa si sigue disponible
        restored = False
        if prev_key:
            for i in range(self._combo_panel.count()):
                if self._combo_panel.itemData(i) == prev_key:
                    self._combo_panel.setCurrentIndex(i)
                    restored = True; break
        if not restored:
            self._combo_panel.setCurrentIndex(0)

        self._combo_panel.blockSignals(False)
        self._combo_panel.setEnabled(True)

    def _on_panel_changed(self, _index: int) -> None:
        """Renderiza la gráfica seleccionada en el combo."""
        if self._current_plot_data is None:
            return
        key = self._combo_panel.currentData()
        if key:
            self._render_panel(key)

    def _render_panel(self, panel_key: str) -> None:
        """Renderiza un único panel ocupando toda la figura."""
        if self._current_plot_data is None:
            return
        panels = self._current_plot_data.get("panels", {})
        panel  = panels.get(panel_key, {})
        cfg    = self._current_plot_data.get("plot_config", {})
        title  = self._current_plot_data.get("title", "")
        is_3d  = self._current_plot_data.get("is_3d", False)
        self._plot.render_single_panel(panel_key, panel, cfg, is_3d, title)

    # ── API pública ───────────────────────────────────────────────────────────

    def show_plot_data(self, plot_data: dict) -> None:
        """Recibe datos del ResultsController y muestra la gráfica activa."""
        self._current_plot_data = plot_data
        is_3d = plot_data.get("is_3d", False)

        # Actualizar combo (añade/quita opciones 3D según corresponda)
        self._populate_combo(is_3d)

        # Renderizar el panel actualmente seleccionado
        self._on_panel_changed(0)

        # Actualizar métricas resumen
        summary = plot_data.get("summary", {})
        for key, lbl in self._metrics_widgets.items():
            val = summary.get(key)
            if val is None:
                lbl.setText("—")
            elif isinstance(val, int):
                lbl.setText(str(val))
            else:
                lbl.setText(f"{val:.4g}")

    def show_error(self, message: str) -> None:
        self._plot.figure.clear()
        ax = self._plot.figure.add_subplot(1, 1, 1)
        ax.text(0.5, 0.5, f"Error:\n{message}", ha="center", va="center",
                color="#E85A30", fontsize=10, transform=ax.transAxes)
        ax.axis("off"); self._plot.canvas.draw()

    def _show_empty_state(self) -> None:
        self._plot.figure.clear()
        ax = self._plot.figure.add_subplot(1, 1, 1)
        ax.text(0.5, 0.5,
                "Ejecute una simulación y presione\n"
                "'Cargar resultados' para ver las gráficas",
                ha="center", va="center", fontsize=11,
                color="#AAAAAA", transform=ax.transAxes)
        ax.axis("off"); self._plot.canvas.draw()


# ── ComparisonTab ─────────────────────────────────────────────────────────────

class ComparisonTab(QWidget):
    """
    Pestaña de comparación de N simulaciones y datos experimentales.

    Permite:
        - Añadir simulaciones desde el controlador (ya cargadas)
        - Cargar datos experimentales desde CSV o Excel
        - Seleccionar la métrica a comparar
        - Visualizar todas las series superpuestas
        - Exportar la comparación

    Señales:
        compare_requested(field: str): Solicita comparación de los datasets cargados.
        load_csv_requested():          Usuario quiere cargar datos CSV.
        load_excel_requested():        Usuario quiere cargar datos Excel.
        export_comparison_requested(): Exportar gráfica de comparación.
    """

    compare_requested         = pyqtSignal(str)
    load_csv_requested        = pyqtSignal()
    load_excel_requested      = pyqtSignal()
    export_comparison_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._datasets = []   # Lista de (label, tipo) para mostrar en la lista
        self._setup_ui()

    def _setup_ui(self) -> None:
        main = QHBoxLayout(self)
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(12)

        # ── Panel izquierdo: control ──────────────────────────────────────────
        left = QVBoxLayout()
        left.setSpacing(10)
        left.setContentsMargins(0, 0, 0, 0)
        left_widget = QWidget()
        left_widget.setFixedWidth(220)
        left_widget.setLayout(left)

        # Datasets cargados
        ds_group = QGroupBox("Datasets cargados")
        ds_group.setFont(QFont("Arial", 9, QFont.Bold))
        ds_layout = QVBoxLayout(ds_group)

        self._list_datasets = QListWidget()
        self._list_datasets.setMaximumHeight(160)
        ds_layout.addWidget(self._list_datasets)

        btn_remove = QPushButton("Eliminar seleccionado")
        btn_remove.setFixedHeight(26)
        btn_remove.clicked.connect(self._remove_selected)
        ds_layout.addWidget(btn_remove)
        left.addWidget(ds_group)

        # Cargar datos experimentales
        exp_group = QGroupBox("Datos experimentales")
        exp_group.setFont(QFont("Arial", 9, QFont.Bold))
        exp_layout = QVBoxLayout(exp_group)

        btn_csv = QPushButton("📄  Cargar CSV")
        btn_csv.setFixedHeight(28)
        btn_csv.clicked.connect(self.load_csv_requested)
        btn_csv.setStyleSheet("QPushButton { background:#F0F4F8; border:1px solid #CBD5E1; border-radius:4px; }")
        exp_layout.addWidget(btn_csv)

        btn_excel = QPushButton("📊  Cargar Excel")
        btn_excel.setFixedHeight(28)
        btn_excel.clicked.connect(self.load_excel_requested)
        btn_excel.setStyleSheet("QPushButton { background:#F0F4F8; border:1px solid #CBD5E1; border-radius:4px; }")
        exp_layout.addWidget(btn_excel)

        lbl_hint = QLabel(
            "Columnas esperadas:\n"
            "  Col 0: tiempo [s]\n"
            "  Col 1: valor"
        )
        lbl_hint.setStyleSheet("color:#888; font-size:10px;")
        lbl_hint.setWordWrap(True)
        exp_layout.addWidget(lbl_hint)
        left.addWidget(exp_group)

        # Selector de métrica
        field_group = QGroupBox("Métrica a comparar")
        field_group.setFont(QFont("Arial", 9, QFont.Bold))
        field_layout = QVBoxLayout(field_group)

        self._combo_field = QComboBox()
        self._combo_field.addItem("Posición del frente X(t)",  "front_position")
        self._combo_field.addItem("Velocidad del frente V(t)", "front_velocity")
        self._combo_field.addItem("Área del fluido A(t)",      "fluid_area")
        self._combo_field.addItem("Volumen del fluido Vol(t)",  "fluid_volume")
        field_layout.addWidget(self._combo_field)
        left.addWidget(field_group)

        # Botón comparar
        btn_compare = QPushButton("▶  Comparar")
        btn_compare.setFixedHeight(34)
        btn_compare.setStyleSheet(
            "QPushButton { background:#2C5F8A; color:white; border-radius:5px; "
            "font-weight:bold; font-size:12px; }"
            "QPushButton:hover { background:#3A78B5; }"
        )
        btn_compare.clicked.connect(self._on_compare)
        left.addWidget(btn_compare)

        # Métricas de comparación
        self._metrics_group = QGroupBox("Métricas (RMSE, R²)")
        self._metrics_group.setFont(QFont("Arial", 9, QFont.Bold))
        self._metrics_layout = QVBoxLayout(self._metrics_group)
        self._lbl_metrics = QLabel("—")
        self._lbl_metrics.setWordWrap(True)
        self._lbl_metrics.setStyleSheet("font-size: 10px; color: #444;")
        self._metrics_layout.addWidget(self._lbl_metrics)
        left.addWidget(self._metrics_group)

        # Exportar
        btn_export = QPushButton("💾  Exportar comparación")
        btn_export.setFixedHeight(28)
        btn_export.clicked.connect(self.export_comparison_requested)
        btn_export.setStyleSheet("QPushButton { background:#F0F4F8; border:1px solid #CBD5E1; border-radius:4px; }")
        left.addWidget(btn_export)

        left.addStretch()
        main.addWidget(left_widget)

        # ── Separador ─────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #DDD;")
        main.addWidget(sep)

        # ── Panel derecho: gráfica de comparación ─────────────────────────────
        right = QVBoxLayout()

        lbl = QLabel("Comparación de simulaciones y datos experimentales")
        lbl.setFont(QFont("Arial", 9, QFont.Bold))
        right.addWidget(lbl)

        self._plot = PlotWidget(figsize=(10, 6.5), show_toolbar=True)
        right.addWidget(self._plot)

        main.addLayout(right, stretch=1)

        self._show_empty()

    def _show_empty(self) -> None:
        self._plot.figure.clear()
        ax = self._plot.figure.add_subplot(1, 1, 1)
        ax.text(
            0.5, 0.5,
            "Cargue simulaciones y/o datos experimentales\n"
            "y presione 'Comparar'",
            ha="center", va="center", fontsize=11,
            color="#AAAAAA", transform=ax.transAxes,
        )
        ax.axis("off")
        self._plot.canvas.draw()

    def _on_compare(self) -> None:
        field = self._combo_field.currentData()
        self.compare_requested.emit(field)

    def _remove_selected(self) -> None:
        row = self._list_datasets.currentRow()
        if row >= 0:
            self._list_datasets.takeItem(row)
            if row < len(self._datasets):
                self._datasets.pop(row)

    # ── API pública ───────────────────────────────────────────────────────────

    def add_simulation_to_list(self, label: str) -> None:
        """Añade una simulación a la lista de datasets."""
        item = QListWidgetItem(f"🔵 {label}")
        item.setToolTip(f"Simulación: {label}")
        self._list_datasets.addItem(item)
        self._datasets.append((label, "simulation"))

    def add_experimental_to_list(self, label: str) -> None:
        """Añade un dataset experimental a la lista."""
        item = QListWidgetItem(f"🔴 {label}")
        item.setToolTip(f"Experimental: {label}")
        self._list_datasets.addItem(item)
        self._datasets.append((label, "experimental"))

    def show_comparison_plot(self, plot_data: dict) -> None:
        """Renderiza la gráfica de comparación."""
        self._plot.render_plot_data(plot_data)

        # Mostrar métricas si las hay
        metrics = plot_data.get("metrics", [])
        if metrics:
            lines = []
            for m in metrics:
                lines.append(
                    f"<b>{m['comparison']}</b><br>"
                    f"RMSE={m['rmse']:.4f}  MAE={m['mae']:.4f}  R²={m['r2']:.3f}"
                )
            self._lbl_metrics.setText("<br><br>".join(lines))
        else:
            self._lbl_metrics.setText("Sin datos experimentales para calcular métricas.")

    def clear_datasets(self) -> None:
        """Limpia la lista de datasets."""
        self._list_datasets.clear()
        self._datasets.clear()
