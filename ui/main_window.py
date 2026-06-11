"""
Ventana principal de OpenFOAM Manager 3D.

Layout:
    ┌─ Panel resumen (fijo) ─┬─────── Pestañas de análisis ────────────────────┐
    │ Fluido    [Editar]     │  [Resultados] [Comparación] [Visualización 3D]  │
    │ Geometría [Editar]     │                                                   │
    │ Simulación[Editar]     │  Contenido de la pestaña activa                  │
    │                        │                                                   │
    │ [▶ Ejecutar]           │                                                   │
    └────────────────────────┴───────────────────────────────────────────────────┘
    └─ Log + Progress ─────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations
from pathlib import Path

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QSplitter, QStatusBar, QAction,
    QFileDialog, QMessageBox,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QFont

from core.simulation import SimulationConfig
from core.simulation.simulation_config import TurbulenceMode
from controllers.simulation_controller import (
    SimulationController, ControllerState, SimulationSummary,
)
from controllers.results_controller import ResultsController, ComparisonResult
from services.exporter import ExportFormat

from ui.panels.config_summary_panel import ConfigSummaryPanel
from ui.tabs.results_comparison_tabs import ResultsTab, ComparisonTab
from ui.tabs.visualization_tab import VisualizationTab
from ui.widgets.log_progress_widgets import LogWidget, ProgressWidget
from ui.widgets.case_conflict_dialog import CaseConflictDialog, suggest_next_name


class MainWindow(QMainWindow):
    """Ventana principal de OpenFOAM Manager 3D."""

    _sig_log        = pyqtSignal(str)
    _sig_progress   = pyqtSignal(str, float)
    _sig_state      = pyqtSignal(object)
    _sig_finished   = pyqtSignal(object)
    _sig_plot_data  = pyqtSignal(dict)
    _sig_error      = pyqtSignal(str)

    APP_TITLE   = "OpenFOAM Manager 3D"
    APP_VERSION = "1.0.0"

    def __init__(self) -> None:
        super().__init__()
        # Config central — única fuente de verdad
        self._config = SimulationConfig.preset_mud_3d()
        self._project_path: Path | None = None

        self._setup_controllers()
        self._setup_ui()
        self._connect_signals()
        self._set_window()
        # Inicializar resumen
        self._panel.refresh(self._config)

    # ── Controladores ─────────────────────────────────────────────────────────

    def _setup_controllers(self) -> None:
        self._sim_ctrl = SimulationController(
            on_log           = lambda m: self._sig_log.emit(m),
            on_progress      = lambda s, p: self._sig_progress.emit(s, p),
            on_state_changed = lambda s: self._sig_state.emit(s),
            on_finished      = lambda r: self._sig_finished.emit(r),
            on_error         = lambda m: self._sig_error.emit(m),
        )
        self._res_ctrl = ResultsController(
            on_plot_data_ready = lambda d: self._sig_plot_data.emit(d),
            on_log             = lambda m: self._sig_log.emit(m),
            on_error           = lambda m: self._sig_error.emit(m),
        )

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Splitter vertical: [panel+tabs] / [log+progress]
        v_split = QSplitter(Qt.Vertical)

        # Fila superior: panel izquierdo + tabs
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)

        # Panel de resumen (izquierda, fijo)
        self._panel = ConfigSummaryPanel()
        top_layout.addWidget(self._panel)

        # Separador visual
        from PyQt5.QtWidgets import QFrame
        sep = QFrame(); sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #E0E0E0;")
        top_layout.addWidget(sep)

        # Pestañas de análisis (derecha)
        self._tabs = QTabWidget()
        self._tabs.setFont(QFont("Arial", 9))
        self._tabs.setDocumentMode(True)

        self._res_tab  = ResultsTab()
        self._comp_tab = ComparisonTab()
        self._viz_tab  = VisualizationTab()

        self._tabs.addTab(self._res_tab,  "Resultados")
        self._tabs.addTab(self._comp_tab, "Comparación")
        self._tabs.addTab(self._viz_tab,  "Visualización 3D")
        top_layout.addWidget(self._tabs, stretch=1)
        v_split.addWidget(top_widget)

        # Panel inferior: log + progress — altura libre (arrastrar el splitter)
        bottom = QWidget()
        bottom.setMinimumHeight(60)   # mínimo visible para el log
        b_lay = QVBoxLayout(bottom)
        b_lay.setContentsMargins(8, 4, 8, 4)
        b_lay.setSpacing(4)
        self._progress = ProgressWidget()
        self._progress.setFixedHeight(50)
        b_lay.addWidget(self._progress)
        self._log = LogWidget(max_lines=2000)
        b_lay.addWidget(self._log)
        v_split.addWidget(bottom)
        # Proporción inicial: 78% área de trabajo / 22% log
        v_split.setSizes([620, 180])
        v_split.setCollapsible(1, False)  # el log no puede colapsar a 0

        root.addWidget(v_split)
        self._setup_menu()
        self.setStatusBar(QStatusBar())

    def _setup_menu(self) -> None:
        menu = self.menuBar()

        # Archivo
        fm = menu.addMenu("Archivo")
        for label, shortcut, fn in [
            ("Nuevo proyecto",         "Ctrl+N", self._new_project),
            ("Abrir proyecto...",      "Ctrl+O", self._open_project),
            ("Guardar proyecto",       "Ctrl+S", self._save_project),
            ("Guardar proyecto como...","Ctrl+Shift+S", self._save_project_as),
        ]:
            a = QAction(label, self); a.setShortcut(shortcut)
            a.triggered.connect(fn); fm.addAction(a)
        fm.addSeparator()
        qa = QAction("Salir", self); qa.setShortcut("Ctrl+Q")
        qa.triggered.connect(self.close); fm.addAction(qa)

        # Simulación
        sm = menu.addMenu("Simulación")
        for label, shortcut, fn in [
            ("Ejecutar",            "F5", self._run_simulation),
            ("Cargar caso...",      "F6", self._load_case),
            ("Cancelar",            "",   self._cancel_simulation),
            ("Limpiar resultados",  "",   self._clean_results),
            ("Recargar resultados", "",   self._load_results),
        ]:
            a = QAction(label, self)
            if shortcut: a.setShortcut(shortcut)
            a.triggered.connect(fn); sm.addAction(a)

        # Ayuda
        hm = menu.addMenu("Ayuda")
        about = QAction(f"Acerca de {self.APP_TITLE}", self)
        about.triggered.connect(self._show_about)
        hm.addAction(about)

    # ── Señales ───────────────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self._sig_log.connect(self._log.append_log)
        self._sig_progress.connect(self._progress.update_progress)
        self._sig_state.connect(self._on_state_changed)
        self._sig_finished.connect(self._on_sim_finished)
        self._sig_plot_data.connect(self._on_plot_data)
        self._sig_error.connect(self._show_error)

        # Panel de resumen → abrir diálogos
        self._panel.run_requested.connect(self._run_simulation)
        self._panel.load_case_requested.connect(self._load_case)
        self._panel.clean_requested.connect(self._clean_results)
        self._panel.edit_fluid_requested.connect(self._edit_fluid)
        self._panel.edit_geometry_requested.connect(self._edit_geometry)
        self._panel.edit_simulation_requested.connect(self._edit_simulation)

        # Tabs de análisis
        self._res_tab.load_requested.connect(self._load_results)
        self._res_tab.export_requested.connect(self._export_results)
        self._comp_tab.load_csv_requested.connect(self._load_experimental_csv)
        self._comp_tab.load_excel_requested.connect(self._load_experimental_excel)
        self._comp_tab.compare_requested.connect(self._compare)
        self._viz_tab.log_message.connect(self._log.append_log)

    # ── Handlers de estado ────────────────────────────────────────────────────

    def _on_state_changed(self, state: ControllerState) -> None:
        running = state in (ControllerState.DETECTING, ControllerState.GENERATING,
                            ControllerState.RUNNING, ControllerState.INSTALLING)
        self._panel.set_running_state(running)
        labels = {
            ControllerState.IDLE:       "Listo",
            ControllerState.DETECTING:  "Verificando OpenFOAM...",
            ControllerState.INSTALLING: "Instalando OpenFOAM...",
            ControllerState.GENERATING: "Generando archivos...",
            ControllerState.RUNNING:    "Simulación en ejecución...",
            ControllerState.FINISHED:   "✓ Completada",
            ControllerState.ERROR:      "✗ Error",
            ControllerState.CANCELLED:  "Cancelada",
        }
        self.statusBar().showMessage(labels.get(state, str(state)))

    def _on_sim_finished(self, summary: SimulationSummary) -> None:
        self._panel.set_running_state(False)
        if summary.success:
            self._progress.set_completed()
            # Sincronizar pestaña Visualización
            self._viz_tab.set_case(self._config)
            # Cargar métricas en Resultados
            self._load_results()
            # Auto-cargar campos alpha en segundo plano (sin interacción del usuario)
            self._viz_tab._load_fields()
            self._log.append_log(
                "✓ Cargando campos α en segundo plano para visualización..."
            )
            self._tabs.setCurrentIndex(0)
        else:
            self._progress.set_error()

    def _on_plot_data(self, plot_data: dict) -> None:
        self._res_tab.show_plot_data(plot_data)

    def _show_error(self, msg: str) -> None:
        QMessageBox.critical(self, "Error", msg)

    # ── Diálogos de edición ───────────────────────────────────────────────────

    def _edit_fluid(self) -> None:
        from ui.dialogs.fluid_edit_dialog import FluidEditDialog
        dlg = FluidEditDialog(self._config.fluid, parent=self)
        if dlg.exec_() and dlg.result_fluid:
            self._config.fluid = dlg.result_fluid
            self._panel.refresh(self._config)
            self._log.append_log(
                f"✓ Fluido actualizado: {dlg.result_fluid.display_name}"
            )

    def _edit_geometry(self) -> None:
        from ui.dialogs.geometry_edit_dialog import GeometryEditDialog
        dlg = GeometryEditDialog(self._config.geometry, parent=self)
        if dlg.exec_() and dlg.result_geometry:
            self._config.geometry = dlg.result_geometry
            self._panel.refresh(self._config)
            geo = dlg.result_geometry
            self._log.append_log(
                f"✓ Geometría actualizada: {geo.nx}×{geo.ny}×{geo.nz} = "
                f"{geo.cell_count:,} celdas"
            )

    def _edit_simulation(self) -> None:
        from ui.dialogs.simulation_edit_dialog import SimulationEditDialog
        params = {
            "name":            self._config.name,
            "output_dir":      self._config.output_dir,
            "end_time":        self._config.end_time,
            "write_interval":  self._config.write_interval,
            "max_courant":     self._config.max_courant,
            "turbulence_mode": self._config.turbulence_mode,
        }
        dlg = SimulationEditDialog(params, fluid=self._config.fluid, parent=self)
        if dlg.exec_() and dlg.result_params:
            p = dlg.result_params
            self._config.name            = p["name"]
            self._config.output_dir      = p["output_dir"]
            self._config.end_time        = p["end_time"]
            self._config.write_interval  = p["write_interval"]
            self._config.max_courant     = p["max_courant"]
            self._config.turbulence_mode = p["turbulence_mode"]
            self._panel.refresh(self._config)
            self._log.append_log(f"✓ Simulación actualizada: {p['name']}")

    # ── Acciones principales ──────────────────────────────────────────────────

    def _run_simulation(self) -> None:
        errors = self._config.validate()
        if errors:
            self._show_error("Configuración inválida:\n" +
                             "\n".join(f"• {e}" for e in errors))
            return

        # Verificar conflicto de nombre
        if self._config.case_dir.exists():
            suggested = suggest_next_name(
                self._config.name, self._config.case_dir.parent
            )
            dlg = CaseConflictDialog(self._config.case_dir, suggested, parent=self)
            if dlg.exec_() != CaseConflictDialog.Accepted:
                return
            if dlg.action == "overwrite":
                self._sim_ctrl.clean_case(self._config)
                self._log.append_log(f"⚠ Sobreescribiendo: {self._config.name}")
            elif dlg.action == "rename":
                self._config.name = dlg.new_name
                self._panel.refresh(self._config)
                self._log.append_log(f"✓ Nuevo nombre: {self._config.name}")

        self._progress.reset()
        self._log.append_log(f"\n{'='*50}")
        self._log.append_log(f"  Iniciando: {self._config.name}")
        self._log.append_log(f"  Malla: {self._config.geometry.nx}×"
                             f"{self._config.geometry.ny}×"
                             f"{self._config.geometry.nz} = "
                             f"{self._config.geometry.cell_count:,} celdas")
        self._log.append_log(f"  Turbulencia: "
                             f"{self._config.effective_turbulence_model.value}")
        self._log.append_log(f"{'='*50}")
        self._sim_ctrl.run(self._config)

    def _load_case(self) -> None:
        """Muestra el diálogo de selección de caso y carga todo automáticamente."""
        from ui.dialogs.load_case_dialog import LoadCaseDialog

        dlg = LoadCaseDialog(
            output_dir = self._config.output_dir,
            parent     = self,
        )
        if dlg.exec_() != LoadCaseDialog.Accepted or not dlg.selected_case:
            return

        case = dlg.selected_case
        self._log.append_log(f"\n{'='*50}")
        self._log.append_log(f"  Cargando caso: {case['name']}")
        self._log.append_log(f"  Pasos: {case['n_steps']}  "
                             f"t: [{case['t_start']:.4g}s → {case['t_end']:.4g}s]")
        self._log.append_log(f"{'='*50}")

        # Actualizar nombre y directorio en la config
        self._config.name       = case["name"]
        self._config.output_dir = str(case["path"].parent)
        self._panel.refresh(self._config)

        # Sincronizar pestaña Visualización
        self._viz_tab.set_case(self._config)

        # Cargar métricas en pestaña Resultados
        self._res_ctrl.load_from_config(self._config, async_=True)
        self._comp_tab.add_simulation_to_list(
            f"{case['name']} ({self._config.fluid.display_name})"
        )

        # Lanzar carga de campos alpha en segundo plano
        self._viz_tab._load_fields()

        # Ir a la pestaña Resultados
        self._tabs.setCurrentIndex(0)

    def _cancel_simulation(self) -> None:
        self._sim_ctrl.cancel()

    def _clean_results(self) -> None:
        """Muestra diálogo de confirmación antes de limpiar."""
        from ui.dialogs.clean_dialog import CleanDialog

        case_dir = self._config.case_dir
        if not case_dir.exists():
            self._show_error(
                f"El directorio del caso no existe:\n{case_dir}\n\n"
                "Ejecute la simulación primero."
            )
            return

        dlg = CleanDialog(case_dir=case_dir, parent=self)
        if dlg.exec_() != CleanDialog.Accepted:
            return   # Cancelar — no hacer nada

        if dlg.action == "results":
            self._log.append_log(f"\n⏱ Limpiando resultados de: {self._config.name}")
            self._sim_ctrl.clean_case(self._config)

        elif dlg.action == "full":
            self._log.append_log(
                f"\n💣 Eliminando caso completo: {self._config.name}"
            )
            self._sim_ctrl.clean_case_full(self._config)
            # Limpiar panel de resultados tras borrar el caso
            self._res_tab._show_empty_state()
            self._res_tab._combo_panel.setEnabled(False)

    def _load_results(self) -> None:
        if not self._config.case_dir.exists():
            self._show_error(
                f"Sin resultados:\n{self._config.case_dir}\n\n"
                "Ejecute la simulación primero o verifique que el nombre\n"
                "del caso y el directorio de salida son correctos\n"
                "(botón \'Editar\' en Simulación del panel izquierdo)."
            )
            return

        # Sincronizar pestaña Visualización con el caso activo
        self._viz_tab.set_case(self._config)

        # Cargar métricas en pestaña Resultados
        self._res_ctrl.load_from_config(self._config, async_=True)
        label = f"{self._config.name} ({self._config.fluid.display_name})"
        self._comp_tab.add_simulation_to_list(label)

    def _export_results(self, fmt: ExportFormat) -> None:
        self._res_ctrl.export(fmt, prefix=self._config.name,
                              config=self._config, async_=True)

    def _compare(self, field: str) -> None:
        result = self._res_ctrl.compare(field=field)
        if result.n_simulations + result.n_experimental == 0:
            return
        pd = self._res_ctrl._build_comparison_plot_data(result, field)
        self._comp_tab.show_comparison_plot(pd)

    def _load_experimental_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Cargar CSV experimental", "", "CSV (*.csv *.txt)"
        )
        if not path: return
        try:
            import pandas as pd
            df_p = pd.read_csv(path, comment="#", nrows=2)
            cols = list(df_p.columns)
        except Exception: cols = []

        our_cols = {"tiempo_s","frente_x_m","velocidad_frente_m_s",
                    "area_fluido_m2","volumen_fluido_m3"}
        if our_cols.issubset(set(cols)):
            field, ok = self._ask_own_csv_field()
            if not ok: return
            data = self._res_ctrl.load_experimental_csv(
                path, field=field,
                label=f"{Path(path).stem} ({field})")
        elif cols:
            t_col, v_col, field, label, ok = self._ask_csv_columns(cols, path)
            if not ok: return
            data = self._res_ctrl.load_experimental_csv(
                path, time_col=t_col, value_col=v_col,
                field=field, label=label)
        else:
            data = self._res_ctrl.load_experimental_csv(path)

        if data:
            self._comp_tab.add_experimental_to_list(data.label)

    def _load_experimental_excel(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Cargar Excel experimental", "", "Excel (*.xlsx *.xls)"
        )
        if path:
            data = self._res_ctrl.load_experimental_excel(path)
            if data: self._comp_tab.add_experimental_to_list(data.label)

    def _ask_own_csv_field(self) -> tuple[str, bool]:
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QDialogButtonBox
        dlg = QDialog(self); dlg.setWindowTitle("¿Qué métrica comparar?")
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("CSV generado por OpenFOAM Manager 3D.\nSelecciona la métrica:"))
        combo = QComboBox()
        combo.addItem("Posición del frente X(t)  [m]",    "front_position")
        combo.addItem("Velocidad del frente V(t)  [m/s]", "front_velocity")
        combo.addItem("Área del fluido A(t)  [m²]",       "fluid_area")
        combo.addItem("Volumen del fluido Vol(t)  [m³]",  "fluid_volume")
        lay.addWidget(combo)
        btns = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept); btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)
        if dlg.exec_() == QDialog.Accepted:
            return combo.currentData(), True
        return "front_position", False

    def _ask_csv_columns(self, columns, path) -> tuple:
        from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QFormLayout,
                                      QLabel, QComboBox, QLineEdit, QDialogButtonBox)
        dlg = QDialog(self); dlg.setWindowTitle("Columnas del CSV")
        dlg.setMinimumWidth(360)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(f"Archivo: {Path(path).name}\n"
                             f"Columnas: {', '.join(columns)}"))
        form = QFormLayout()
        c_time = QComboBox(); c_time.addItems(columns)
        c_val  = QComboBox(); c_val.addItems(columns)
        if len(columns)>1: c_val.setCurrentIndex(1)
        c_field = QComboBox()
        c_field.addItem("Posición del frente [m]",    "front_position")
        c_field.addItem("Velocidad del frente [m/s]", "front_velocity")
        c_field.addItem("Área [m²]", "fluid_area")
        c_field.addItem("Volumen [m³]", "fluid_volume")
        e_label = QLineEdit(Path(path).stem)
        form.addRow("Tiempo:", c_time); form.addRow("Valor:", c_val)
        form.addRow("Tipo:", c_field); form.addRow("Etiqueta:", e_label)
        lay.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept); btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)
        if dlg.exec_() == QDialog.Accepted:
            return (c_time.currentText(), c_val.currentText(),
                    c_field.currentData(), e_label.text() or Path(path).stem, True)
        return "0","1","front_position","",False

    # ── Gestión de proyectos ──────────────────────────────────────────────────

    def _new_project(self) -> None:
        if QMessageBox.question(self, "Nuevo proyecto",
            "¿Descartar el proyecto actual?",
            QMessageBox.Yes|QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            self._config = SimulationConfig.preset_mud_3d()
            self._panel.refresh(self._config)
            self._project_path = None
            self.setWindowTitle(f"{self.APP_TITLE} v{self.APP_VERSION}")

    def _open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir proyecto", "", "JSON (*.json)")
        if not path: return
        try:
            self._config = SimulationConfig.load_json(path)
            self._panel.refresh(self._config)
            self._project_path = Path(path)
            self.setWindowTitle(
                f"{self.APP_TITLE} — {self._project_path.name}")
            self.statusBar().showMessage(f"Proyecto cargado: {path}")

            # Sincronizar pestaña Visualización con el caso cargado
            # (muestra la ruta y habilita botones si ya hay resultados)
            self._viz_tab.set_case(self._config)

            # Informar al usuario si hay resultados disponibles
            if self._config.case_dir.exists():
                self._log.append_log(
                    f"✓ Proyecto cargado: {self._config.name}\n"
                    f"  Resultados en: {self._config.case_dir}\n"
                    f"  → Use 'Cargar resultados' para ver las gráficas\n"
                    f"  → Use 'Cargar campos α' en Visualización 3D"
                )
            else:
                self._log.append_log(
                    f"✓ Proyecto cargado: {self._config.name}\n"
                    f"  Sin resultados previos en disco."
                )
        except Exception as e:
            self._show_error(f"Error al abrir:\n{e}")

    def _save_project(self) -> None:
        if self._project_path:
            self._do_save(self._project_path)
        else:
            self._save_project_as()

    def _save_project_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar proyecto",
            f"{self._config.name}.json", "JSON (*.json)")
        if path:
            self._project_path = Path(path)
            self._do_save(self._project_path)
            self.setWindowTitle(
                f"{self.APP_TITLE} — {self._project_path.name}")

    def _do_save(self, path: Path) -> None:
        self._config.save_json(path)
        self.statusBar().showMessage(f"Guardado: {path}")

    def _show_about(self) -> None:
        QMessageBox.about(self, f"Acerca de {self.APP_TITLE}",
            f"<b>{self.APP_TITLE}</b> v{self.APP_VERSION}<br><br>"
            "Simulación 3D de rompimiento de presas con OpenFOAM 9.<br>"
            "Modelo Herschel-Bulkley para fluidos viscoplásticos.<br><br>"
            "<b>Canal:</b> 1.6 × 0.6 × 0.15 m (L × H × W)<br>"
            "<b>Turbulencia:</b> laminar para HB, k-ε para agua<br>"
            "<b>Comparación:</b> cámara lateral, cámara superior, sensores de pared")

    def _set_window(self) -> None:
        self.setWindowTitle(f"{self.APP_TITLE} v{self.APP_VERSION}")
        self.resize(1280, 820)
        self.setMinimumSize(960, 650)
