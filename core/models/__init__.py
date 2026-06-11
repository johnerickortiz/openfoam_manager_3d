"""
Modelos de fluido disponibles en el sistema.

Para añadir un nuevo fluido:
    1. Crear un archivo nuevo (ej: bingham.py)
    2. Heredar de FluidModel e implementar todos los métodos abstractos
    3. Registrar en FLUID_REGISTRY con una clave única

Ejemplo:
    from core.models import FLUID_REGISTRY
    fluid = FLUID_REGISTRY["herschel_bulkley"](nu0=1.0, tau0=0.02778, ...)
"""
from core.models.fluid_model import FluidModel, FluidType
from core.models.newtonian import NewtonianFluid
from core.models.herschel_bulkley import HerschelBulkleyFluid

# Registro central de fluidos disponibles
# Clave: identificador único | Valor: clase del fluido
FLUID_REGISTRY: dict[str, type[FluidModel]] = {
    "newtonian":        NewtonianFluid,
    "herschel_bulkley": HerschelBulkleyFluid,
}

__all__ = [
    "FluidModel",
    "FluidType",
    "NewtonianFluid",
    "HerschelBulkleyFluid",
    "FLUID_REGISTRY",
]
