"""
Core layer — dominio puro del sistema OpenFOAM Manager.

Sin dependencias de UI (PyQt5) ni de OpenFOAM directamente.
Testeable de forma completamente aislada.

Subpaquetes:
    models         — Modelos de fluido (FluidModel, Newtonian, HerschelBulkley)
    simulation     — Configuración de simulaciones y geometría
    postprocessing — Lectura de resultados y extracción de métricas
"""
