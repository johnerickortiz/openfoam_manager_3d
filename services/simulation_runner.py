"""
Ejecutor de simulaciones OpenFOAM.

Gestiona la ejecución de la secuencia completa:
    blockMesh → setFields → interFoam

Usa callbacks para notificar progreso y logs en tiempo real,
sin depender de PyQt5. El controlador conecta estos callbacks
a las señales de PyQt5.

Soporta:
    - Ejecución síncrona (para testing y uso en scripts)
    - Ejecución asíncrona mediante threading (para la UI)
    - Cancelación de simulación en curso
    - Detección automática de plataforma (WSL/Linux)
"""
from __future__ import annotations

import subprocess
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

from services.openfoam_detector import OpenFOAMDetector, Platform


class RunnerStatus(str, Enum):
    """Estado actual del runner de simulación."""
    IDLE      = "idle"        # Sin simulación activa
    RUNNING   = "running"     # Simulación en ejecución
    COMPLETED = "completed"   # Terminada con éxito
    FAILED    = "failed"      # Terminada con error
    CANCELLED = "cancelled"   # Cancelada por el usuario


@dataclass
class StepResult:
    """Resultado de un paso de la simulación (blockMesh, setFields, interFoam)."""
    step:       str
    success:    bool
    returncode: int
    duration_s: float
    error_msg:  str = ""


@dataclass
class SimulationResult:
    """Resultado completo de una simulación."""
    status:   RunnerStatus
    case_dir: str
    steps:    list[StepResult] = field(default_factory=list)
    total_duration_s: float = 0.0
    error_msg: str = ""

    @property
    def success(self) -> bool:
        return self.status == RunnerStatus.COMPLETED

    @property
    def failed_step(self) -> StepResult | None:
        for step in self.steps:
            if not step.success:
                return step
        return None


class SimulationRunner:
    """
    Ejecuta simulaciones OpenFOAM con notificación de progreso en tiempo real.

    Callbacks disponibles:
        on_log(message: str)         — Línea de log de OpenFOAM
        on_progress(step: str, pct)  — Progreso (nombre_paso, porcentaje 0-100)
        on_finished(result)          — Resultado final de la simulación

    Ejemplo síncrono:
        runner = SimulationRunner(
            on_log=print,
            on_progress=lambda s, p: print(f"{s}: {p}%"),
        )
        result = runner.run_sync(config)

    Ejemplo asíncrono (para UI):
        runner = SimulationRunner(
            on_log=log_widget.append,
            on_progress=progress_bar.update,
            on_finished=results_tab.load_results,
        )
        runner.run_async(config)
        # ... usuario puede cancelar con runner.cancel()
    """

    # Pesos relativos de cada paso para calcular progreso total
    _STEP_WEIGHTS = {
        "blockMesh": 0.05,
        "setFields": 0.05,
        "interFoam": 0.90,
    }

    def __init__(
        self,
        on_log:      Callable[[str], None]           | None = None,
        on_progress: Callable[[str, float], None]    | None = None,
        on_finished: Callable[[SimulationResult], None] | None = None,
        detector:    OpenFOAMDetector                | None = None,
    ) -> None:
        self._on_log      = on_log      or (lambda msg: None)
        self._on_progress = on_progress or (lambda step, pct: None)
        self._on_finished = on_finished or (lambda result: None)
        self._detector    = detector or OpenFOAMDetector(log_callback=on_log)

        self._status: RunnerStatus = RunnerStatus.IDLE
        self._cancel_event         = threading.Event()
        self._thread: threading.Thread | None = None
        self._current_proc: subprocess.Popen | None = None

    # ── Propiedades ───────────────────────────────────────────────────────────

    @property
    def status(self) -> RunnerStatus:
        return self._status

    @property
    def is_running(self) -> bool:
        return self._status == RunnerStatus.RUNNING

    # ── API principal ─────────────────────────────────────────────────────────

    def run_sync(
        self,
        case_dir:   str | Path,
        phase_name: str = "lodo",
    ) -> SimulationResult:
        """
        Ejecuta la simulación de forma síncrona (bloqueante).

        Útil para testing y scripts. Para la UI usar run_async().

        Args:
            case_dir:   Directorio del caso OpenFOAM.
            phase_name: Nombre de la fase principal.

        Returns:
            SimulationResult con el estado final.
        """
        self._cancel_event.clear()
        self._status = RunnerStatus.RUNNING
        result = self._execute_simulation(Path(case_dir), phase_name)
        self._status = result.status
        self._on_finished(result)
        return result

    def run_async(
        self,
        case_dir:   str | Path,
        phase_name: str = "lodo",
    ) -> None:
        """
        Ejecuta la simulación en un hilo separado (no bloqueante).

        La UI permanece responsiva. El resultado se entrega via on_finished().

        Args:
            case_dir:   Directorio del caso OpenFOAM.
            phase_name: Nombre de la fase principal.
        """
        if self.is_running:
            self._on_log("⚠ Ya hay una simulación en ejecución.")
            return

        self._cancel_event.clear()
        self._status = RunnerStatus.RUNNING

        self._thread = threading.Thread(
            target  = self._async_worker,
            args    = (Path(case_dir), phase_name),
            daemon  = True,
            name    = "SimulationRunner",
        )
        self._thread.start()

    def cancel(self) -> None:
        """
        Cancela la simulación en curso.

        Envía señal de cancelación y termina el proceso OpenFOAM activo.
        """
        if not self.is_running:
            return

        self._on_log("\n⚠ Cancelando simulación...")
        self._cancel_event.set()

        if self._current_proc and self._current_proc.poll() is None:
            try:
                self._current_proc.terminate()
                self._current_proc.wait(timeout=5)
            except (subprocess.TimeoutExpired, OSError):
                try:
                    self._current_proc.kill()
                except OSError:
                    pass

        self._status = RunnerStatus.CANCELLED
        self._on_log("✓ Simulación cancelada.")

    # ── Ejecución interna ─────────────────────────────────────────────────────

    def _async_worker(self, case_dir: Path, phase_name: str) -> None:
        """Worker que corre en el hilo secundario."""
        result = self._execute_simulation(case_dir, phase_name)
        self._status = result.status
        self._on_finished(result)

    def _execute_simulation(
        self,
        case_dir:   Path,
        phase_name: str,
    ) -> SimulationResult:
        """
        Ejecuta la secuencia completa: blockMesh → setFields → interFoam.
        """
        import time
        start_total = time.time()
        steps       = []
        plat        = self._detector._detect_platform()

        self._on_log("=" * 55)
        self._on_log(f"SIMULACIÓN: {case_dir.name}")
        self._on_log(f"Plataforma: {plat.value}")
        self._on_log("=" * 55)

        # Pasos a ejecutar
        simulation_steps = [
            ("blockMesh", []),
            ("setFields", []),
            ("interFoam", []),
        ]

        cumulative_weight = 0.0
        total_weight      = sum(self._STEP_WEIGHTS.values())

        for step_name, extra_args in simulation_steps:
            if self._cancel_event.is_set():
                return SimulationResult(
                    status   = RunnerStatus.CANCELLED,
                    case_dir = str(case_dir),
                    steps    = steps,
                )

            # Paso especial: copiar alpha.orig antes de setFields
            if step_name == "setFields":
                self._copy_alpha_orig(case_dir, phase_name, plat)

            self._on_log(f"\n{'─'*40}")
            self._on_log(f"▶ Ejecutando: {step_name}")
            self._on_log(f"{'─'*40}")

            weight = self._STEP_WEIGHTS[step_name]
            step_result = self._run_step(
                step_name       = step_name,
                case_dir        = case_dir,
                plat            = plat,
                base_progress   = cumulative_weight / total_weight * 100,
                step_progress_w = weight / total_weight * 100,
            )
            steps.append(step_result)
            cumulative_weight += weight

            if not step_result.success:
                self._on_log(f"\n✗ Falló: {step_name}")
                self._on_log(f"  {step_result.error_msg}")
                return SimulationResult(
                    status    = RunnerStatus.FAILED,
                    case_dir  = str(case_dir),
                    steps     = steps,
                    error_msg = f"Falló en '{step_name}': {step_result.error_msg}",
                    total_duration_s = time.time() - start_total,
                )

            self._on_log(f"✓ {step_name} completado en {step_result.duration_s:.1f}s")

        total_time = time.time() - start_total
        self._on_progress("Completado", 100.0)
        self._on_log(f"\n{'='*55}")
        self._on_log(f"✅ Simulación completada en {total_time:.1f}s")
        self._on_log(f"{'='*55}")

        return SimulationResult(
            status           = RunnerStatus.COMPLETED,
            case_dir         = str(case_dir),
            steps            = steps,
            total_duration_s = total_time,
        )

    def _run_step(
        self,
        step_name:       str,
        case_dir:        Path,
        plat:            Platform,
        base_progress:   float,
        step_progress_w: float,
    ) -> StepResult:
        """Ejecuta un paso individual y captura su salida."""
        import time

        cmd = self._detector.build_foam_command(
            command  = step_name,
            case_dir = str(case_dir),
            plat     = plat,
        )

        start = time.time()
        lines_count = 0
        stderr_lines = []

        try:
            with subprocess.Popen(
                cmd,
                stdout  = subprocess.PIPE,
                stderr  = subprocess.STDOUT,
                text    = True,
                bufsize = 1,
            ) as proc:
                self._current_proc = proc

                for line in proc.stdout:
                    if self._cancel_event.is_set():
                        proc.terminate()
                        break

                    line = line.rstrip()
                    self._on_log(line)
                    lines_count += 1

                    # Actualizar progreso basado en líneas procesadas
                    # (estimación heurística)
                    if lines_count % 10 == 0:
                        est_pct = min(base_progress + step_progress_w * 0.9, 99.0)
                        self._on_progress(step_name, est_pct)

                    # Capturar errores
                    if "FOAM FATAL ERROR" in line or "FOAM exiting" in line:
                        stderr_lines.append(line)

                proc.wait()
                returncode = proc.returncode

        except Exception as e:
            return StepResult(
                step       = step_name,
                success    = False,
                returncode = -1,
                duration_s = time.time() - start,
                error_msg  = str(e),
            )

        finally:
            self._current_proc = None

        duration = time.time() - start
        success  = (returncode == 0) and not self._cancel_event.is_set()

        # Actualizar progreso al finalizar el paso
        if success:
            self._on_progress(step_name, base_progress + step_progress_w)

        return StepResult(
            step       = step_name,
            success    = success,
            returncode = returncode,
            duration_s = duration,
            error_msg  = "\n".join(stderr_lines) if not success else "",
        )

    def _copy_alpha_orig(
        self,
        case_dir:   Path,
        phase_name: str,
        plat:       Platform,
    ) -> None:
        """Copia alpha.<phase>.orig a alpha.<phase> antes de setFields."""
        orig = case_dir / "0" / f"alpha.{phase_name}.orig"
        dest = case_dir / "0" / f"alpha.{phase_name}"

        if orig.exists():
            import shutil
            shutil.copy2(orig, dest)
            self._on_log(f"  ✓ Copiado: alpha.{phase_name}.orig → alpha.{phase_name}")
        else:
            self._on_log(f"  ⚠ No encontrado: 0/alpha.{phase_name}.orig")

    # ── Utilidades ────────────────────────────────────────────────────────────

    def clean_results(self, case_dir: str | Path) -> None:
        """
        Elimina los directorios de tiempo de resultados anteriores.

        Equivalente a: foamListTimes -rm

        Args:
            case_dir: Directorio del caso.
        """
        case_path = Path(case_dir)
        removed   = 0

        for d in case_path.iterdir():
            if d.is_dir():
                try:
                    t = float(d.name)
                    if t > 0:
                        import shutil
                        shutil.rmtree(d)
                        removed += 1
                except ValueError:
                    pass

        self._on_log(f"✓ Eliminados {removed} directorios de resultados anteriores.")

    def clean_full_case(self, case_dir: str | Path) -> None:
        """
        Elimina el directorio completo del caso (malla + config + resultados).

        Equivalente a borrar manualmente la carpeta del caso en disco.
        Esta operación NO se puede deshacer.

        Args:
            case_dir: Directorio raíz del caso OpenFOAM.
        """
        import shutil
        case_path = Path(case_dir)
        if not case_path.exists():
            self._on_log(f"⚠ El directorio no existe: {case_path}")
            return
        shutil.rmtree(case_path)
        self._on_log(f"✓ Caso eliminado completamente: {case_path.name}")

    def __repr__(self) -> str:
        return f"SimulationRunner(status={self._status.value})"
