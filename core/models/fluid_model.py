"""
Clase base abstracta para todos los modelos de fluido.

Define la interfaz que deben implementar todos los fluidos del sistema.
Garantiza que cualquier fluido nuevo sea compatible con CaseGenerator,
la interfaz gráfica y el sistema de exportación sin modificaciones.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FluidType(str, Enum):
    """Clasificación del tipo de comportamiento reológico."""
    NEWTONIAN     = "Newtoniano"
    VISCOPLASTIC  = "Viscoplástico"
    POWER_LAW     = "Ley de Potencia"
    THIXOTROPIC   = "Tixotrópico"


@dataclass
class ValidationResult:
    """Resultado de la validación de parámetros de un fluido."""
    is_valid: bool
    errors:   list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.is_valid = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def __str__(self) -> str:
        lines = []
        if self.errors:
            lines.append("Errores:")
            lines.extend(f"  - {e}" for e in self.errors)
        if self.warnings:
            lines.append("Advertencias:")
            lines.extend(f"  - {w}" for w in self.warnings)
        return "\n".join(lines) if lines else "Validación correcta."


class FluidModel(ABC):
    """
    Interfaz base para todos los modelos de fluido.

    Cada fluido debe implementar:
        - to_foam_dict()    : genera el bloque transportProperties para OpenFOAM
        - get_parameters()  : retorna dict con todos los parámetros nominales
        - validate()        : verifica coherencia física de los parámetros
        - display_name      : nombre legible para la UI
        - fluid_type        : clasificación reológica

    Ejemplo de uso:
        fluid = HerschelBulkleyFluid(rho=1800, tau0=50, k=10, n=0.4, nu0=1.0)
        foam_block = fluid.to_foam_dict(phase_name="lodo")
        params = fluid.get_parameters()
    """

    # ── Propiedades obligatorias ──────────────────────────────────────────────

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Nombre legible para mostrar en la interfaz gráfica."""

    @property
    @abstractmethod
    def fluid_type(self) -> FluidType:
        """Tipo de comportamiento reológico."""

    @property
    @abstractmethod
    def rho(self) -> float:
        """Densidad del fluido [kg/m³]."""

    # ── Métodos obligatorios ──────────────────────────────────────────────────

    @abstractmethod
    def to_foam_dict(self, phase_name: str = "fluid") -> str:
        """
        Genera el bloque de configuración para constant/transportProperties.

        Args:
            phase_name: nombre de la fase en OpenFOAM (ej: "lodo", "water")

        Returns:
            Cadena con el bloque listo para escribir en el archivo.

        Ejemplo de salida para Newtonian:
            lodo
            {
                transportModel  Newtonian;
                nu              1e-06;
                rho             1000;
            }
        """

    @abstractmethod
    def get_parameters(self) -> dict[str, Any]:
        """
        Retorna todos los parámetros del fluido como diccionario.

        Returns:
            Dict con claves: nombre_parámetro → valor.
            Siempre incluye 'rho' y 'transport_model'.
        """

    @abstractmethod
    def validate(self) -> ValidationResult:
        """
        Verifica la coherencia física de los parámetros.

        Returns:
            ValidationResult con errores y advertencias encontrados.
        """

    # ── Métodos concretos compartidos ─────────────────────────────────────────

    def get_kinematic_viscosity_at_shear_rate(self, gamma_dot: float) -> float:
        """
        Calcula la viscosidad cinemática efectiva a una tasa de deformación dada.

        Implementación por defecto para fluidos newtonianos.
        Los fluidos no newtonianos deben sobreescribir este método.

        Args:
            gamma_dot: tasa de deformación [1/s]

        Returns:
            Viscosidad cinemática efectiva [m²/s]
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} debe implementar "
            "get_kinematic_viscosity_at_shear_rate()"
        )

    def summary(self) -> str:
        """Resumen legible del fluido y sus parámetros."""
        params = self.get_parameters()
        lines = [
            f"Fluido: {self.display_name} ({self.fluid_type.value})",
            f"Densidad: {self.rho} kg/m³",
        ]
        for key, val in params.items():
            if key not in ("rho", "transport_model", "display_name"):
                lines.append(f"  {key}: {val}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(rho={self.rho})"
