"""
Controllers Layer — Coordina UI con servicios.

Los controladores orquestan el flujo de la aplicación:
    UI → Controller → Services → Core

No tienen dependencias de PyQt5 directamente.
Usan callbacks Python puros, que la UI conecta a señales/slots de PyQt5.
Esto los hace completamente testeables sin interfaz gráfica.

Módulos:
    SimulationController — Gestiona el ciclo completo de simulación
    ResultsController    — Gestiona resultados, visualización y exportación
"""
from controllers.simulation_controller import SimulationController
from controllers.results_controller import ResultsController, ComparisonResult

__all__ = [
    "SimulationController",
    "ResultsController",
    "ComparisonResult",
]
