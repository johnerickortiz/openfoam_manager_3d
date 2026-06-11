"""
Services Layer — Lógica de negocio e interacción con OpenFOAM.

Independiente de la UI. Detecta automáticamente la plataforma
(Windows/WSL2/Linux nativo) para ejecutar los comandos correctamente.

Módulos:
    openfoam_detector  — Detecta e instala OpenFOAM 9
    case_generator     — Genera los archivos del caso OpenFOAM
    simulation_runner  — Ejecuta blockMesh, setFields, interFoam
    data_extractor     — Coordina la extracción de métricas post-simulación
    exporter           — Exporta resultados a CSV, Excel, JSON, PNG, VTK
"""
from services.openfoam_detector import OpenFOAMDetector, OpenFOAMStatus
from services.case_generator import CaseGenerator
from services.simulation_runner import SimulationRunner, RunnerStatus
from services.data_extractor import DataExtractor
from services.exporter import Exporter, ExportFormat

__all__ = [
    "OpenFOAMDetector",
    "OpenFOAMStatus",
    "CaseGenerator",
    "SimulationRunner",
    "RunnerStatus",
    "DataExtractor",
    "Exporter",
    "ExportFormat",
]
