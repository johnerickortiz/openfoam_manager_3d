"""
Detección e instalación automatizada de OpenFOAM 9.

Soporta tres entornos de ejecución:
    - Linux nativo (Ubuntu 22.04)
    - WSL2 desde Windows (Windows Subsystem for Linux)
    - Windows directo (llama a WSL internamente)

Flujo de detección:
    1. Detectar plataforma actual
    2. Buscar /opt/openfoam9/etc/bashrc
    3. Si no existe → instalar desde repositorio oficial
    4. Verificar que interFoam y HerschelBulkley están disponibles
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable


class Platform(str, Enum):
    """Plataforma de ejecución detectada."""
    LINUX_NATIVE = "linux_native"   # Ubuntu nativo
    WSL2         = "wsl2"           # WSL2 desde dentro de Ubuntu
    WINDOWS      = "windows"        # Windows llamando a WSL


class OpenFOAMStatus(str, Enum):
    """Estado de la instalación de OpenFOAM."""
    INSTALLED     = "installed"       # Instalado y funcional
    NOT_INSTALLED = "not_installed"   # No instalado
    PARTIAL       = "partial"         # Instalado parcialmente
    UNKNOWN       = "unknown"         # No se pudo determinar


@dataclass
class DetectionResult:
    """Resultado de la detección de OpenFOAM."""
    status:       OpenFOAMStatus
    platform:     Platform
    foam_root:    str | None       # /opt/openfoam9
    bashrc_path:  str | None       # /opt/openfoam9/etc/bashrc
    interfoam_ok: bool = False
    hb_model_ok:  bool = False
    messages:     list[str] = None

    def __post_init__(self):
        if self.messages is None:
            self.messages = []

    @property
    def is_ready(self) -> bool:
        """True si OpenFOAM está instalado y los componentes clave están disponibles."""
        return (
            self.status == OpenFOAMStatus.INSTALLED
            and self.interfoam_ok
            and self.hb_model_ok
        )

    @property
    def source_command(self) -> str:
        """Comando para activar el entorno de OpenFOAM."""
        path = self.bashrc_path or "/opt/openfoam9/etc/bashrc"
        return f"source {path}"


class OpenFOAMDetector:
    """
    Detecta e instala OpenFOAM 9.

    Args:
        log_callback: Función opcional para recibir mensajes de progreso.
                      Signature: (message: str) -> None

    Ejemplo (solo detección):
        detector = OpenFOAMDetector()
        result = detector.detect()
        if result.is_ready:
            print(f"OpenFOAM listo en {result.foam_root}")
        else:
            detector.install(log_callback=print)

    Ejemplo (detección + instalación automática):
        detector = OpenFOAMDetector(log_callback=print)
        result = detector.ensure_installed()
    """

    FOAM_ROOT    = "/opt/openfoam9"
    FOAM_BASHRC  = "/opt/openfoam9/etc/bashrc"
    FOAM_VERSION = "9"

    def __init__(
        self,
        log_callback: Callable[[str], None] | None = None,
    ) -> None:
        self._log = log_callback or (lambda msg: None)

    # ── API principal ─────────────────────────────────────────────────────────

    def detect(self) -> DetectionResult:
        """
        Detecta el estado de la instalación de OpenFOAM.

        Returns:
            DetectionResult con estado, plataforma y rutas.
        """
        plat = self._detect_platform()
        self._log(f"Plataforma detectada: {plat.value}")

        # Verificar si el directorio de OpenFOAM existe
        bashrc = Path(self.FOAM_BASHRC)
        if not self._file_exists_on_platform(self.FOAM_BASHRC, plat):
            self._log(f"OpenFOAM 9 no encontrado en {self.FOAM_ROOT}")
            return DetectionResult(
                status     = OpenFOAMStatus.NOT_INSTALLED,
                platform   = plat,
                foam_root  = None,
                bashrc_path = None,
                messages   = ["OpenFOAM 9 no está instalado."],
            )

        self._log(f"Encontrado: {self.FOAM_BASHRC}")

        # Verificar interFoam
        interfoam_ok = self._check_command("interFoam -help", plat)
        self._log(f"interFoam: {'✓' if interfoam_ok else '✗'}")

        # Verificar modelo Herschel-Bulkley
        hb_path = (
            f"{self.FOAM_ROOT}/src/transportModels/"
            "viscosityModels/HerschelBulkley/HerschelBulkley.C"
        )
        hb_ok = self._file_exists_on_platform(hb_path, plat)
        self._log(f"HerschelBulkley: {'✓' if hb_ok else '✗'}")

        status = (
            OpenFOAMStatus.INSTALLED
            if interfoam_ok and hb_ok
            else OpenFOAMStatus.PARTIAL
        )

        messages = []
        if not interfoam_ok:
            messages.append("interFoam no encontrado. Verificar instalación.")
        if not hb_ok:
            messages.append("Modelo HerschelBulkley no encontrado.")

        return DetectionResult(
            status       = status,
            platform     = plat,
            foam_root    = self.FOAM_ROOT,
            bashrc_path  = self.FOAM_BASHRC,
            interfoam_ok = interfoam_ok,
            hb_model_ok  = hb_ok,
            messages     = messages,
        )

    def ensure_installed(self) -> DetectionResult:
        """
        Detecta OpenFOAM e instala si no está presente.

        Returns:
            DetectionResult con estado final tras detección/instalación.
        """
        result = self.detect()

        if result.is_ready:
            self._log("OpenFOAM 9 ya está instalado y listo.")
            return result

        if result.status == OpenFOAMStatus.NOT_INSTALLED:
            self._log("Iniciando instalación de OpenFOAM 9...")
            success = self.install(result.platform)
            if success:
                return self.detect()
            else:
                result.messages.append("La instalación falló. Ver log para detalles.")
                return result

        return result

    def install(
        self,
        plat: Platform | None = None,
    ) -> bool:
        """
        Instala OpenFOAM 9 desde el repositorio oficial.

        Requiere conexión a internet y permisos sudo.

        Args:
            plat: Plataforma. Si None, se auto-detecta.

        Returns:
            True si la instalación fue exitosa.
        """
        plat = plat or self._detect_platform()
        self._log("=" * 50)
        self._log("Instalando OpenFOAM 9 desde repositorio oficial")
        self._log("=" * 50)

        commands = self._get_install_commands()

        for i, (description, cmd) in enumerate(commands, 1):
            self._log(f"\n[{i}/{len(commands)}] {description}")
            self._log(f"$ {cmd}")

            success = self._run_command_with_log(cmd, plat)
            if not success:
                self._log(f"✗ Falló: {description}")
                return False
            self._log(f"✓ Completado: {description}")

        # Añadir source al .bashrc del usuario
        self._add_to_bashrc(plat)

        self._log("\n✅ OpenFOAM 9 instalado correctamente.")
        return True

    # ── Detección de plataforma ───────────────────────────────────────────────

    def _detect_platform(self) -> Platform:
        """Detecta en qué entorno se está ejecutando."""
        system = platform.system().lower()

        if system == "windows":
            return Platform.WINDOWS

        if system == "linux":
            # Verificar si estamos dentro de WSL2
            try:
                with open("/proc/version", "r") as f:
                    version_info = f.read().lower()
                if "microsoft" in version_info or "wsl" in version_info:
                    return Platform.WSL2
            except (OSError, IOError):
                pass
            return Platform.LINUX_NATIVE

        # macOS u otro: tratar como Linux nativo (puede requerir ajuste)
        return Platform.LINUX_NATIVE

    # ── Ejecución de comandos ─────────────────────────────────────────────────

    def _run_command(
        self,
        cmd:  str,
        plat: Platform,
        timeout: int = 300,
    ) -> subprocess.CompletedProcess:
        """Ejecuta un comando en la plataforma correcta."""
        if plat == Platform.WINDOWS:
            full_cmd = ["wsl", "bash", "-c", cmd]
        else:
            full_cmd = ["bash", "-c", cmd]

        return subprocess.run(
            full_cmd,
            capture_output = True,
            text           = True,
            timeout        = timeout,
        )

    def _run_command_with_log(
        self,
        cmd:  str,
        plat: Platform,
        timeout: int = 600,
    ) -> bool:
        """Ejecuta un comando y loguea la salida línea por línea."""
        if plat == Platform.WINDOWS:
            full_cmd = ["wsl", "bash", "-c", cmd]
        else:
            full_cmd = ["bash", "-c", cmd]

        try:
            with subprocess.Popen(
                full_cmd,
                stdout = subprocess.PIPE,
                stderr = subprocess.STDOUT,
                text   = True,
                bufsize = 1,
            ) as proc:
                for line in proc.stdout:
                    self._log(line.rstrip())
                proc.wait(timeout=timeout)
                return proc.returncode == 0
        except subprocess.TimeoutExpired:
            self._log("✗ Tiempo de espera agotado.")
            return False
        except Exception as e:
            self._log(f"✗ Error: {e}")
            return False

    def _check_command(self, cmd: str, plat: Platform) -> bool:
        """Verifica si un comando se ejecuta correctamente."""
        source_cmd = f"source {self.FOAM_BASHRC} 2>/dev/null && {cmd} 2>/dev/null"
        try:
            result = self._run_command(source_cmd, plat, timeout=30)
            return result.returncode == 0
        except Exception:
            return False

    def _file_exists_on_platform(self, path: str, plat: Platform) -> bool:
        """Verifica si un archivo existe en la plataforma correcta."""
        cmd = f"test -f '{path}' || test -d '{path}'"
        try:
            result = self._run_command(cmd, plat, timeout=15)
            return result.returncode == 0
        except Exception:
            # Fallback: verificar localmente si es Linux
            if plat != Platform.WINDOWS:
                return Path(path).exists()
            return False

    # ── Comandos de instalación ───────────────────────────────────────────────

    def _get_install_commands(self) -> list[tuple[str, str]]:
        """
        Retorna la secuencia de comandos de instalación.

        Returns:
            Lista de (descripción, comando_bash).
        """
        return [
            (
                "Actualizar lista de paquetes",
                "sudo apt-get update -y",
            ),
            (
                "Instalar dependencias base",
                "sudo apt-get install -y wget software-properties-common",
            ),
            (
                "Agregar clave GPG del repositorio oficial",
                (
                    "sudo sh -c \"wget -q -O - https://dl.openfoam.org/gpg.key "
                    "> /etc/apt/trusted.gpg.d/openfoam.asc\""
                ),
            ),
            (
                "Agregar repositorio OpenFOAM Foundation",
                "sudo add-apt-repository -y http://dl.openfoam.org/ubuntu",
            ),
            (
                "Actualizar lista de paquetes con nuevo repositorio",
                "sudo apt-get update -y",
            ),
            (
                "Instalar OpenFOAM 9 (puede tardar varios minutos)",
                "sudo apt-get install -y openfoam9",
            ),
        ]

    def _add_to_bashrc(self, plat: Platform) -> None:
        """Agrega el source de OpenFOAM al .bashrc del usuario."""
        source_line = f"\n# OpenFOAM 9\nsource {self.FOAM_BASHRC}\n"
        cmd = (
            f"grep -q 'openfoam9' ~/.bashrc || "
            f"echo '{source_line}' >> ~/.bashrc"
        )
        try:
            self._run_command(cmd, plat, timeout=10)
            self._log("✓ Source agregado a ~/.bashrc")
        except Exception:
            self._log("⚠ No se pudo actualizar ~/.bashrc")

    # ── Utilidades ────────────────────────────────────────────────────────────

    def get_shell_prefix(self, plat: Platform | None = None) -> list[str]:
        """
        Retorna el prefijo de comando para ejecutar en el entorno correcto.

        Usado por SimulationRunner para construir los comandos.

        Returns:
            Lista de argumentos para subprocess (antes del comando real).

        Ejemplo:
            prefix = detector.get_shell_prefix()
            cmd = prefix + ["-c", f"source {bashrc} && blockMesh"]
        """
        plat = plat or self._detect_platform()
        if plat == Platform.WINDOWS:
            return ["wsl", "bash"]
        return ["bash"]

    def build_foam_command(
        self,
        command:    str,
        case_dir:   str,
        plat:       Platform | None = None,
    ) -> list[str]:
        """
        Construye el comando completo para ejecutar un solver OpenFOAM.

        Sourcea el entorno de OpenFOAM automáticamente.

        Args:
            command:  Comando OpenFOAM (ej: "blockMesh", "interFoam").
            case_dir: Directorio del caso (absoluto o ~/).
            plat:     Plataforma. Si None, auto-detecta.

        Returns:
            Lista lista para pasar a subprocess.Popen.

        Ejemplo:
            cmd = detector.build_foam_command("interFoam", "~/cases/damBreak")
            proc = subprocess.Popen(cmd, stdout=PIPE, stderr=STDOUT)
        """
        plat = plat or self._detect_platform()
        prefix = self.get_shell_prefix(plat)

        # Normalizar path para WSL si es Windows
        if plat == Platform.WINDOWS:
            case_dir = self._windows_to_wsl_path(case_dir)

        script = (
            f"source {self.FOAM_BASHRC} && "
            f"cd {case_dir} && "
            f"{command}"
        )
        return prefix + ["-c", script]

    @staticmethod
    def _windows_to_wsl_path(windows_path: str) -> str:
        """Convierte un path de Windows a formato WSL."""
        # C:\Users\erick\... → /mnt/c/Users/erick/...
        path = windows_path.replace("\\", "/")
        if len(path) >= 2 and path[1] == ":":
            drive = path[0].lower()
            path = f"/mnt/{drive}{path[2:]}"
        return path

    def __repr__(self) -> str:
        plat = self._detect_platform()
        return f"OpenFOAMDetector(platform={plat.value})"
