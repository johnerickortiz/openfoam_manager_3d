"""
Controlador de simulaciones.

Orquesta el flujo completo:
    1. Validar configuración
    2. Detectar / instalar OpenFOAM
    3. Generar archivos del caso
    4. Ejecutar blockMesh → setFields → interFoam
    5. Notificar a la UI con progreso, logs y resultado

Comunicación con la UI exclusivamente via callbacks Python puros.
La UI (PyQt5) conecta sus señales a estos callbacks.

Ejemplo de uso desde la UI:
    controller = SimulationController(
        on_log=lambda msg: log_widget.append(msg),
        on_progress=lambda step, pct: progress_bar.setValue(int(pct)),
        on_finished=lambda result: self._on_sim_finished(result),
        on_error=lambda msg: QMessageBox.critical(self, 'Error', msg),
    )
    controller.run(config)
    # Para cancelar:
    controller.cancel()
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

from core.simulation import SimulationConfig
from services.openfoam_detector import OpenFOAMDetector, OpenFOAMStatus
from services.case_generator import CaseGenerator
from services.simulation_runner import SimulationRunner, SimulationResult, RunnerStatus


class ControllerState(str, Enum):
    """Estado interno del controlador."""
    IDLE        = "idle"
    DETECTING   = "detecting"
    INSTALLING  = "installing"
    GENERATING  = "generating"
    RUNNING     = "running"
    FINISHED    = "finished"
    ERROR       = "error"
    CANCELLED   = "cancelled"


@dataclass
class SimulationSummary:
    """Resumen completo del proceso de simulación para la UI."""
    config:       SimulationConfig
    state:        ControllerState
    result:       SimulationResult | None  = None
    case_dir:     str                      = ""
    error_msg:    str                      = ""
    duration_s:   float                    = 0.0
    of_version:   str                      = ""

    @property
    def success(self) -> bool:
        return (
            self.state == ControllerState.FINISHED
            and self.result is not None
            and self.result.success
        )


class SimulationController:
    """
    Orquesta el ciclo completo de una simulación OpenFOAM.

    Callbacks disponibles (todos opcionales):
        on_log(msg: str)
            Recibe cada línea de log en tiempo real.

        on_progress(step: str, percent: float)
            Notifica el progreso (0-100).
            'step' es el nombre del paso actual.

        on_state_changed(state: ControllerState)
            Notifica cambios de estado del flujo.

        on_finished(summary: SimulationSummary)
            Notifica el resultado final (éxito o fallo).

        on_error(message: str)
            Notifica un error crítico.

    Ejemplo completo (sin UI):
        ctrl = SimulationController(on_log=print, on_progress=lambda s,p: None)
        config = SimulationConfig.preset_mud_literature()
        config.output_dir = '/tmp/casos'
        ctrl.run(config)
    """

    def __init__(
        self,
        on_log:           Callable[[str], None]                    | None = None,
        on_progress:      Callable[[str, float], None]             | None = None,
        on_state_changed: Callable[[ControllerState], None]        | None = None,
        on_finished:      Callable[[SimulationSummary], None]      | None = None,
        on_error:         Callable[[str], None]                    | None = None,
    ) -> None:

        # Callbacks (con valores por defecto no-op)
        self._on_log           = on_log           or (lambda msg: None)
        self._on_progress      = on_progress      or (lambda s, p: None)
        self._on_state_changed = on_state_changed or (lambda s: None)
        self._on_finished      = on_finished      or (lambda r: None)
        self._on_error         = on_error         or (lambda msg: None)

        # Estado interno
        self._state:   ControllerState   = ControllerState.IDLE
        self._runner:  SimulationRunner  = None
        self._thread:  threading.Thread  = None
        self._cancel   = threading.Event()
        self._current_config: SimulationConfig | None = None
        self._summary: SimulationSummary | None = None

    # ── Propiedades ───────────────────────────────────────────────────────────

    @property
    def state(self) -> ControllerState:
        return self._state

    @property
    def is_busy(self) -> bool:
        return self._state in (
            ControllerState.DETECTING,
            ControllerState.INSTALLING,
            ControllerState.GENERATING,
            ControllerState.RUNNING,
        )

    @property
    def current_config(self) -> SimulationConfig | None:
        return self._current_config

    # ── API pública ───────────────────────────────────────────────────────────

    def run(self, config: SimulationConfig) -> None:
        """
        Inicia el flujo completo de simulación de forma asíncrona.

        La UI permanece responsiva. Los resultados llegan via on_finished().

        Args:
            config: Configuración completa de la simulación.

        Raises:
            RuntimeError: Si ya hay una simulación en curso.
        """
        if self.is_busy:
            self._on_error(
                "Ya hay una simulación en curso. "
                "Cancela la actual antes de iniciar una nueva."
            )
            return

        # Validación previa
        errors = config.validate()
        if errors:
            msg = "Configuración inválida:\n" + "\n".join(f"  • {e}" for e in errors)
            self._on_error(msg)
            return

        self._cancel.clear()
        self._current_config = config

        self._thread = threading.Thread(
            target = self._workflow,
            args   = (config,),
            daemon = True,
            name   = f"SimController-{config.name}",
        )
        self._thread.start()

    def run_sync(self, config: SimulationConfig) -> SimulationSummary:
        """
        Ejecuta el flujo de forma síncrona (bloqueante).

        Útil para testing y scripts sin UI.

        Args:
            config: Configuración de la simulación.

        Returns:
            SimulationSummary con el resultado final.
        """
        errors = config.validate()
        if errors:
            msg = "Configuración inválida:\n" + "\n".join(f"  • {e}" for e in errors)
            return SimulationSummary(
                config    = config,
                state     = ControllerState.ERROR,
                error_msg = msg,
            )

        self._cancel.clear()
        self._current_config = config
        return self._workflow(config)

    def cancel(self) -> None:
        """
        Cancela la simulación en curso.

        Funciona en cualquier etapa: detección, generación o ejecución.
        """
        if not self.is_busy:
            return

        self._on_log("\n⚠ Cancelando...")
        self._cancel.set()

        if self._runner and self._runner.is_running:
            self._runner.cancel()

        self._set_state(ControllerState.CANCELLED)

    def clean_case(self, config: SimulationConfig) -> None:
        """Elimina solo los directorios de tiempo (resultados) del caso."""
        if self.is_busy:
            self._on_error("No se puede limpiar mientras hay una simulación en curso.")
            return
        runner = SimulationRunner(on_log=self._on_log)
        runner.clean_results(config.case_dir)

    def clean_case_full(self, config: SimulationConfig) -> None:
        """Elimina el directorio completo del caso (malla + config + resultados)."""
        if self.is_busy:
            self._on_error("No se puede eliminar mientras hay una simulación en curso.")
            return
        runner = SimulationRunner(on_log=self._on_log)
        runner.clean_full_case(config.case_dir)

    # ── Flujo interno ─────────────────────────────────────────────────────────

    def _workflow(self, config: SimulationConfig) -> SimulationSummary:
        """Flujo completo: detección → generación → ejecución."""
        start = time.time()
        summary = SimulationSummary(
            config   = config,
            state    = ControllerState.IDLE,
            case_dir = str(config.case_dir),
        )

        try:
            # ── Paso 1: Detectar / instalar OpenFOAM ─────────────────────────
            if self._cancel.is_set():
                return self._finish(summary, ControllerState.CANCELLED)

            self._set_state(ControllerState.DETECTING)
            self._on_log("═" * 55)
            self._on_log("  OPENFOAM MANAGER — Iniciando simulación")
            self._on_log("═" * 55)
            self._on_progress("Detectando OpenFOAM", 2.0)

            detection = self._detect_openfoam()

            if not detection.is_ready:
                if detection.status == OpenFOAMStatus.NOT_INSTALLED:
                    self._set_state(ControllerState.INSTALLING)
                    self._on_progress("Instalando OpenFOAM 9", 5.0)
                    detection = self._install_openfoam()

                if not detection.is_ready:
                    return self._finish(
                        summary,
                        ControllerState.ERROR,
                        error_msg = (
                            "OpenFOAM 9 no está disponible.\n"
                            + "\n".join(detection.messages)
                        ),
                    )

            summary.of_version = f"OpenFOAM {detection.foam_root or '9'}"
            self._on_log(f"✓ {summary.of_version} listo")
            self._on_progress("OpenFOAM detectado", 10.0)

            # ── Paso 2: Generar archivos del caso ─────────────────────────────
            if self._cancel.is_set():
                return self._finish(summary, ControllerState.CANCELLED)

            self._set_state(ControllerState.GENERATING)
            self._on_progress("Generando archivos del caso", 12.0)

            try:
                generator = CaseGenerator(log_callback=self._on_log)
                case_dir  = generator.generate(config)
                self._on_progress("Archivos generados", 20.0)
                self._on_log(f"✓ Caso generado en: {case_dir}")
            except Exception as e:
                return self._finish(
                    summary,
                    ControllerState.ERROR,
                    error_msg = f"Error generando el caso: {e}",
                )

            # ── Paso 3: Ejecutar simulación ───────────────────────────────────
            if self._cancel.is_set():
                return self._finish(summary, ControllerState.CANCELLED)

            self._set_state(ControllerState.RUNNING)

            # Crear runner con callbacks que escalan el progreso (20% → 100%)
            def _scaled_progress(step: str, pct: float) -> None:
                # Escalar de [0, 100] a [20, 100]
                scaled = 20.0 + pct * 0.80
                self._on_progress(step, scaled)

            self._runner = SimulationRunner(
                on_log      = self._on_log,
                on_progress = _scaled_progress,
            )

            # Ejecutar de forma síncrona en este hilo
            sim_result = self._runner.run_sync(
                case_dir   = case_dir,
                phase_name = config.phase_name,
            )
            summary.result = sim_result

            if sim_result.status == RunnerStatus.CANCELLED:
                return self._finish(summary, ControllerState.CANCELLED)

            if not sim_result.success:
                failed = sim_result.failed_step
                error_msg = (
                    f"La simulación falló en el paso '{failed.step}'.\n"
                    f"{failed.error_msg}"
                ) if failed else "La simulación falló por motivo desconocido."

                return self._finish(summary, ControllerState.ERROR,
                                    error_msg=error_msg)

            # ── Éxito ─────────────────────────────────────────────────────────
            summary.duration_s = time.time() - start
            self._on_progress("Completado", 100.0)
            return self._finish(summary, ControllerState.FINISHED)

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self._on_log(f"\n✗ Error inesperado:\n{tb}")
            return self._finish(
                summary,
                ControllerState.ERROR,
                error_msg = f"Error inesperado: {e}",
            )

    def _detect_openfoam(self):
        """Detecta OpenFOAM y loguea el resultado."""
        detector = OpenFOAMDetector(log_callback=self._on_log)
        result   = detector.detect()

        self._on_log(f"  Estado: {result.status.value}")
        self._on_log(f"  interFoam: {'✓' if result.interfoam_ok else '✗'}")
        self._on_log(f"  HerschelBulkley: {'✓' if result.hb_model_ok else '✗'}")

        return result

    def _install_openfoam(self):
        """Instala OpenFOAM y retorna el resultado de la nueva detección."""
        self._on_log("\nOpenFOAM 9 no encontrado. Iniciando instalación...")
        detector = OpenFOAMDetector(log_callback=self._on_log)
        detector.install()
        return detector.detect()

    def _finish(
        self,
        summary:   SimulationSummary,
        state:     ControllerState,
        error_msg: str = "",
    ) -> SimulationSummary:
        """Finaliza el flujo, actualiza el estado y notifica a la UI."""
        summary.state     = state
        summary.error_msg = error_msg

        self._set_state(state)

        if state == ControllerState.ERROR:
            self._on_log(f"\n✗ Error: {error_msg}")
            self._on_error(error_msg)

        elif state == ControllerState.CANCELLED:
            self._on_log("\n⚠ Simulación cancelada por el usuario.")

        elif state == ControllerState.FINISHED:
            dur = summary.duration_s
            self._on_log(
                f"\n✅ Simulación completada en "
                f"{dur:.1f}s ({dur/60:.1f} min)"
            )

        self._on_finished(summary)
        self._summary = summary
        return summary

    def _set_state(self, state: ControllerState) -> None:
        """Actualiza el estado y notifica a la UI."""
        self._state = state
        self._on_state_changed(state)

    # ── Utilidades ────────────────────────────────────────────────────────────

    def get_last_summary(self) -> SimulationSummary | None:
        """Retorna el resumen de la última simulación ejecutada."""
        return self._summary

    def __repr__(self) -> str:
        return f"SimulationController(state={self._state.value})"
