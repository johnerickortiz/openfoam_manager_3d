"""
Modelo de fluido Newtoniano.

Relación constitutiva lineal: τ = μ · γ̇
La viscosidad es constante e independiente de la tasa de deformación.

Parámetros OpenFOAM:
    transportModel  Newtonian;
    nu              <viscosidad cinemática>;  [m²/s]
    rho             <densidad>;               [kg/m³]

Aplicaciones típicas: agua, aceites ligeros, gases.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.models.fluid_model import FluidModel, FluidType, ValidationResult


@dataclass
class NewtonianFluid(FluidModel):
    """
    Fluido Newtoniano con viscosidad constante.

    Args:
        nu:  Viscosidad cinemática [m²/s]. Valor típico agua: 1e-6.
        rho: Densidad [kg/m³]. Valor típico agua: 1000.
        sigma: Tensión superficial con el aire [N/m]. Agua: 0.07, lodo: 0.0.

    Ejemplo:
        agua = NewtonianFluid(nu=1e-6, rho=1000, sigma=0.07)
        print(agua.to_foam_dict(phase_name="lodo"))
    """
    nu:    float = 1e-6    # Viscosidad cinemática [m²/s]
    _rho:  float = 1000.0  # Densidad [kg/m³]
    sigma: float = 0.07    # Tensión superficial [N/m]

    def __init__(
        self,
        nu:    float = 1e-6,
        rho:   float = 1000.0,
        sigma: float = 0.07,
    ) -> None:
        self.nu    = nu
        self._rho  = rho
        self.sigma = sigma

    # ── Propiedades abstractas implementadas ─────────────────────────────────

    @property
    def display_name(self) -> str:
        return "Newtoniano"

    @property
    def fluid_type(self) -> FluidType:
        return FluidType.NEWTONIAN

    @property
    def rho(self) -> float:
        return self._rho

    @rho.setter
    def rho(self, value: float) -> None:
        self._rho = value

    # ── Métodos abstractos implementados ─────────────────────────────────────

    def to_foam_dict(self, phase_name: str = "fluid") -> str:
        """
        Genera el bloque transportProperties para OpenFOAM.

        Returns:
            Bloque de configuración para el fluido newtoniano.
        """
        return (
            f"{phase_name}\n"
            f"{{\n"
            f"    transportModel  Newtonian;\n"
            f"    nu              {self.nu:.6e};\n"
            f"    rho             {self._rho:.4g};\n"
            f"}}"
        )

    def get_parameters(self) -> dict[str, Any]:
        return {
            "transport_model": "Newtonian",
            "display_name":    self.display_name,
            "nu":              self.nu,
            "rho":             self._rho,
            "sigma":           self.sigma,
            "mu":              self.nu * self._rho,  # viscosidad dinámica [Pa·s]
        }

    def validate(self) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        if self.nu <= 0:
            result.add_error(
                f"Viscosidad cinemática nu={self.nu} debe ser positiva."
            )
        if self._rho <= 0:
            result.add_error(
                f"Densidad rho={self._rho} debe ser positiva."
            )
        if self.sigma < 0:
            result.add_error(
                f"Tensión superficial sigma={self.sigma} no puede ser negativa."
            )

        # Advertencias por valores inusuales
        if self.nu > 1e-3:
            result.add_warning(
                f"Viscosidad cinemática muy alta (nu={self.nu:.2e} m²/s). "
                "¿Es correcto? Agua: 1e-6, aceite: ~1e-4."
            )
        if self._rho < 500 or self._rho > 3000:
            result.add_warning(
                f"Densidad rho={self._rho} kg/m³ fuera del rango típico "
                "(500-3000 kg/m³)."
            )

        return result

    # ── Métodos concretos sobreescritos ──────────────────────────────────────

    def get_kinematic_viscosity_at_shear_rate(self, gamma_dot: float) -> float:
        """Para fluido newtoniano la viscosidad es constante."""
        return self.nu

    # ── Métodos auxiliares ───────────────────────────────────────────────────

    @property
    def dynamic_viscosity(self) -> float:
        """Viscosidad dinámica μ = ν · ρ [Pa·s]."""
        return self.nu * self._rho

    @classmethod
    def water(cls) -> "NewtonianFluid":
        """Crea una instancia con propiedades estándar del agua a 20°C."""
        return cls(nu=1e-6, rho=1000.0, sigma=0.07)

    @classmethod
    def air(cls) -> "NewtonianFluid":
        """Crea una instancia con propiedades estándar del aire a 20°C."""
        return cls(nu=1.48e-5, rho=1.0, sigma=0.0)

    def __repr__(self) -> str:
        return (
            f"NewtonianFluid(nu={self.nu:.2e}, rho={self._rho:.1f}, "
            f"sigma={self.sigma:.3f})"
        )
