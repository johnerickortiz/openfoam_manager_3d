"""
Servicio para lanzar ParaView y generar archivos VTK desde casos OpenFOAM.

Responsabilidades:
    - Encontrar ParaView en Windows o Linux
    - Crear el archivo case.foam requerido por ParaView
    - Ejecutar foamToVTK para convertir resultados a formato VTK
    - Lanzar ParaView con el caso abierto
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

from services.openfoam_detector import OpenFOAMDetector, Platform


# Rutas de instalación típicas de ParaView en Windows
PARAVIEW_WINDOWS_PATHS = [
    r"C:\Program Files\ParaView 5.13.0\bin\paraview.exe",
    r"C:\Program Files\ParaView 5.12.0\bin\paraview.exe",
    r"C:\Program Files\ParaView 5.11.2\bin\paraview.exe",
    r"C:\Program Files\ParaView 5.11.0\bin\paraview.exe",
    r"C:\Program Files\ParaView 5.10.1\bin\paraview.exe",
    r"C:\Program Files\ParaView 5.10.0\bin\paraview.exe",
    r"C:\Program Files (x86)\ParaView 5.13.0\bin\paraview.exe",
]

PARAVIEW_LINUX_PATHS = [
    "/usr/bin/paraview",
    "/usr/local/bin/paraview",
    "/opt/paraview/bin/paraview",
]


class ParaViewLauncher:
    """
    Encuentra y lanza ParaView con un caso OpenFOAM.

    Args:
        log_callback: Función para mensajes de progreso.
    """

    def __init__(
        self,
        log_callback: Callable[[str], None] | None = None,
    ) -> None:
        self._log = log_callback or (lambda msg: None)
        self._detector = OpenFOAMDetector(log_callback=log_callback)

    # Ruta personalizada guardada por el usuario
    _custom_path: str | None = None

    def find_paraview(self) -> str | None:
        """
        Busca ParaView usando múltiples estrategias en orden de prioridad.

        Estrategias:
            1. Ruta personalizada guardada por el usuario
            2. PATH del sistema (where/which)
            3. Glob en Program Files (cualquier versión)
            4. Registro de Windows
            5. Lista de rutas conocidas como fallback
        """
        plat = self._detector._detect_platform()

        # 1. Ruta personalizada guardada
        if ParaViewLauncher._custom_path:
            if Path(ParaViewLauncher._custom_path).exists():
                return ParaViewLauncher._custom_path

        if plat == Platform.WINDOWS:
            return self._find_on_windows()
        else:
            return self._find_on_linux()

    def _find_on_windows(self) -> str | None:
        """Búsqueda exhaustiva en Windows."""
        import glob as _glob

        # Estrategia A: PATH del sistema
        try:
            result = subprocess.run(
                ["where", "paraview"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                path = result.stdout.strip().split('\n')[0].strip()
                if path and Path(path).exists():
                    self._log(f"  ParaView en PATH: {path}")
                    return path
        except Exception:
            pass

        # Estrategia B: Glob en Program Files — encuentra CUALQUIER versión
        patterns = [
            r"C:\Program Files\ParaView*\bin\paraview.exe",
            r"C:\Program Files (x86)\ParaView*\bin\paraview.exe",
            r"C:\ParaView*\bin\paraview.exe",
            r"D:\Program Files\ParaView*\bin\paraview.exe",
            r"D:\ParaView*\bin\paraview.exe",
        ]
        for pattern in patterns:
            matches = sorted(_glob.glob(pattern), reverse=True)  # más reciente primero
            for match in matches:
                if Path(match).exists():
                    self._log(f"  ParaView encontrado (glob): {match}")
                    return match

        # Estrategia C: Registro de Windows
        try:
            import winreg
            keys_to_try = [
                (winreg.HKEY_LOCAL_MACHINE,
                 r"SOFTWARE\Kitware\ParaView"),
                (winreg.HKEY_LOCAL_MACHINE,
                 r"SOFTWARE\WOW6432Node\Kitware\ParaView"),
                (winreg.HKEY_CURRENT_USER,
                 r"SOFTWARE\Kitware\ParaView"),
            ]
            for hive, key_path in keys_to_try:
                try:
                    with winreg.OpenKey(hive, key_path) as key:
                        install_dir, _ = winreg.QueryValueEx(key, "InstallDir")
                        exe = Path(install_dir) / "bin" / "paraview.exe"
                        if exe.exists():
                            self._log(f"  ParaView en registro: {exe}")
                            return str(exe)
                except (FileNotFoundError, OSError):
                    continue
        except ImportError:
            pass  # winreg solo existe en Windows real

        # Estrategia D: Lista de versiones conocidas como último recurso
        for path in PARAVIEW_WINDOWS_PATHS:
            if Path(path).exists():
                return path

        return None

    def _find_on_linux(self) -> str | None:
        """Búsqueda en Linux."""
        import shutil
        found = shutil.which("paraview")
        if found:
            return found
        for path in PARAVIEW_LINUX_PATHS:
            if Path(path).exists():
                return path
        return None

    @classmethod
    def set_custom_path(cls, path: str) -> None:
        """Guarda una ruta personalizada de ParaView (persiste en la sesión)."""
        cls._custom_path = path

    def create_foam_file(self, case_dir: str | Path) -> Path:
        """
        Crea el archivo case.foam necesario para abrir el caso en ParaView.

        Args:
            case_dir: Directorio del caso OpenFOAM.

        Returns:
            Path al archivo case.foam creado.
        """
        case_path = Path(case_dir)
        foam_file = case_path / "case.foam"
        foam_file.touch(exist_ok=True)
        self._log(f"✓ Creado: {foam_file}")
        return foam_file

    def run_foam_to_vtk(
        self,
        case_dir: str | Path,
        fields:   list[str] | None = None,
    ) -> bool:
        """
        Ejecuta foamToVTK para convertir resultados de OpenFOAM a VTK.

        Genera un directorio VTK/ dentro del caso con archivos .vtk
        para cada paso de tiempo.

        Args:
            case_dir: Directorio del caso OpenFOAM.
            fields:   Lista de campos a exportar. Si None, exporta todos.

        Returns:
            True si la conversión fue exitosa.
        """
        case_dir = Path(case_dir)
        plat = self._detector._detect_platform()

        self._log("\nConvirtiendo resultados a VTK...")

        # Construir comando foamToVTK
        fields_arg = ""
        if fields:
            fields_arg = "-fields '(" + " ".join(fields) + ")'"

        cmd = self._detector.build_foam_command(
            command  = f"foamToVTK {fields_arg}",
            case_dir = str(case_dir),
            plat     = plat,
        )

        try:
            with subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            ) as proc:
                for line in proc.stdout:
                    self._log(line.rstrip())
                proc.wait(timeout=120)

                if proc.returncode == 0:
                    vtk_dir = case_dir / "VTK"
                    if plat == Platform.WINDOWS:
                        # En Windows, VTK está en la ruta de Windows
                        vtk_count = len(list(vtk_dir.glob("*.vtk"))) if vtk_dir.exists() else 0
                    else:
                        vtk_count = len(list(vtk_dir.glob("*.vtk"))) if vtk_dir.exists() else 0
                    self._log(f"✓ VTK generado: {vtk_count} archivos en {vtk_dir}")
                    return True
                else:
                    self._log("✗ foamToVTK falló")
                    return False

        except subprocess.TimeoutExpired:
            self._log("✗ Tiempo de espera agotado para foamToVTK")
            return False
        except Exception as e:
            self._log(f"✗ Error en foamToVTK: {e}")
            return False

    def launch(
        self,
        case_dir:       str | Path,
        paraview_path:  str | None = None,
    ) -> bool:
        """
        Lanza ParaView con el caso abierto.

        Args:
            case_dir:      Directorio del caso OpenFOAM.
            paraview_path: Ruta al ejecutable. Si None, lo busca automáticamente.

        Returns:
            True si ParaView se lanzó correctamente.
        """
        pv = paraview_path or self.find_paraview()

        if not pv:
            self._log("✗ ParaView no encontrado en el sistema.")
            self._log("  Descarga desde: https://www.paraview.org/download/")
            return False

        foam_file = self.create_foam_file(case_dir)

        self._log(f"\nLanzando ParaView...")
        self._log(f"  Ejecutable: {pv}")
        self._log(f"  Caso: {foam_file}")

        try:
            subprocess.Popen(
                [pv, str(foam_file)],
                creationflags=subprocess.DETACHED_PROCESS
                if hasattr(subprocess, "DETACHED_PROCESS") else 0,
            )
            self._log("✓ ParaView lanzado correctamente.")
            return True
        except Exception as e:
            self._log(f"✗ No se pudo lanzar ParaView: {e}")
            return False

    def get_vtk_files(self, case_dir: str | Path) -> list[Path]:
        """
        Lista los archivos VTK disponibles en el caso.

        Returns:
            Lista de paths a archivos .vtk ordenados por tiempo.
        """
        case_path = Path(case_dir)
        vtk_dir   = case_path / "VTK"
        if not vtk_dir.exists():
            return []
        return sorted(vtk_dir.glob("*.vtk"))

    def __repr__(self) -> str:
        pv = self.find_paraview()
        return f"ParaViewLauncher(paraview={'found' if pv else 'not found'})"
