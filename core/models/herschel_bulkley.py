"""
Modelo de fluido Herschel-Bulkley (viscoplástico).

Ecuación constitutiva:
    τ = τ₀ + k·|γ̇|ⁿ     si |τ| > τ₀  (zona de flujo)
    γ̇ = 0               si |τ| ≤ τ₀  (zona plug)

Regularización numérica de OpenFOAM (bi-viscosa):
    ν_eff = min(ν₀, (τ₀/ρ + (k/ρ)·|γ̇|ⁿ) / max(|γ̇|, ε))

IMPORTANTE — Conversión a parámetros cinemáticos:
    OpenFOAM trabaja con viscosidad cinemática [m²/s].
    Los parámetros dinámicos deben dividirse entre ρ:
        tau0_cin = tau0 / rho   [m²/s²]
        k_cin    = k / rho      [m²/s]

Parámetros del modelo:
    tau0  : Esfuerzo de fluencia [Pa] — umbral para que el fluido fluya
    k     : Consistencia [Pa·sⁿ]    — resistencia al flujo
    n     : Índice de flujo [-]      — n<1: pseudoplástico, n=1: Bingham
    nu0   : Viscosidad plateau [m²/s] — PARÁMETRO NUMÉRICO, no físico
    rho   : Densidad [kg/m³]

Aplicaciones típicas: lodo, lahar, pasta, lava, cemento fresco.

Referencias:
    Herschel & Bulkley (1926). Kolloid Zeitschrift, 39, 291-300.
    Ancey (2007). Journal of Non-Newtonian Fluid Mechanics, 142, 4-35.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from core.models.fluid_model import FluidModel, FluidType, ValidationResult


@dataclass
class HerschelBulkleyFluid(FluidModel):
    """
    Fluido viscoplástico Herschel-Bulkley.

    Args:
        tau0 : Esfuerzo de fluencia [Pa]. Típico lodo: 10-200 Pa.
        k    : Consistencia [Pa·sⁿ]. Típico lodo: 1-50 Pa·sⁿ.
        n    : Índice de flujo [-]. Lodo volcánico: 0.3-0.6.
        nu0  : Viscosidad cinemática plateau [m²/s]. Valor numérico: ~1.0.
        rho  : Densidad [kg/m³]. Lodo: 1500-2200 kg/m³.
        sigma: Tensión superficial [N/m]. Para lodo: 0.0.

    Ejemplo (lodo con datos de literatura):
        lodo = HerschelBulkleyFluid(
            tau0=50.0, k=10.0, n=0.4,
            nu0=1.0, rho=1800.0, sigma=0.0
        )
        print(lodo.to_foam_dict("lodo"))
        print(lodo.summary())
    """

    tau0:   float = 50.0    # Esfuerzo de fluencia [Pa]
    k:      float = 10.0    # Consistencia [Pa·sⁿ]
    n:      float = 0.4     # Índice de flujo [-]
    nu0:    float = 1.0     # Viscosidad plateau (regularización) [m²/s]
    _rho:   float = 1800.0  # Densidad [kg/m³]
    sigma:  float = 0.0     # Tensión superficial [N/m]

    def __init__(
        self,
        tau0:  float = 50.0,
        k:     float = 10.0,
        n:     float = 0.4,
        nu0:   float = 1.0,
        rho:   float = 1800.0,
        sigma: float = 0.0,
    ) -> None:
        self.tau0  = tau0
        self.k     = k
        self.n     = n
        self.nu0   = nu0
        self._rho  = rho
        self.sigma = sigma

    # ── Propiedades abstractas implementadas ─────────────────────────────────

    @property
    def display_name(self) -> str:
        return "Herschel-Bulkley"

    @property
    def fluid_type(self) -> FluidType:
        return FluidType.VISCOPLASTIC

    @property
    def rho(self) -> float:
        return self._rho

    @rho.setter
    def rho(self, value: float) -> None:
        self._rho = value

    # ── Parámetros cinemáticos (para OpenFOAM) ────────────────────────────────

    @property
    def tau0_kinematic(self) -> float:
        """Esfuerzo de fluencia cinemático: τ₀/ρ [m²/s²]."""
        return self.tau0 / self._rho

    @property
    def k_kinematic(self) -> float:
        """Consistencia cinemática: k/ρ [m²/s]."""
        return self.k / self._rho

    # ── Métodos abstractos implementados ─────────────────────────────────────

    def to_foam_dict(self, phase_name: str = "fluid") -> str:
        """
        Genera el bloque HerschelBulkley para constant/transportProperties.

        Los parámetros se convierten automáticamente a valores cinemáticos
        dividiendo tau0 y k entre rho, tal como requiere OpenFOAM.

        Returns:
            Bloque de configuración listo para escribir en el archivo.
        """
        tau0_cin = self.tau0_kinematic
        k_cin    = self.k_kinematic

        return (
            f"{phase_name}\n"
            f"{{\n"
            f"    transportModel  HerschelBulkley;\n"
            f"\n"
            f"    HerschelBulkleyCoeffs\n"
            f"    {{\n"
            f"        // Parámetros cinemáticos (divididos entre rho={self._rho:.4g} kg/m³)\n"
            f"        nu0   nu0  [0 2 -1 0 0 0 0]  {self.nu0:.6g};    "
            f"// Viscosidad plateau (regularización) [m²/s]\n"
            f"        tau0  tau0 [0 2 -2 0 0 0 0]  {tau0_cin:.6g};    "
            f"// {self.tau0:.4g} Pa / {self._rho:.4g} kg/m³\n"
            f"        k     k    [0 2 -1 0 0 0 0]  {k_cin:.6g};    "
            f"// {self.k:.4g} Pa·sⁿ / {self._rho:.4g} kg/m³\n"
            f"        n     n    [0 0  0 0 0 0 0]  {self.n:.4g};    "
            f"// Índice de flujo [-]\n"
            f"    }}\n"
            f"\n"
            f"    rho     {self._rho:.4g};   // Densidad [kg/m³]\n"
            f"}}"
        )

    def get_parameters(self) -> dict[str, Any]:
        return {
            "transport_model":  "HerschelBulkley",
            "display_name":     self.display_name,
            "rho":              self._rho,
            "tau0":             self.tau0,
            "k":                self.k,
            "n":                self.n,
            "nu0":              self.nu0,
            "sigma":            self.sigma,
            # Parámetros cinemáticos (los que usa OpenFOAM)
            "tau0_kinematic":   self.tau0_kinematic,
            "k_kinematic":      self.k_kinematic,
        }

    def validate(self) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        # Errores críticos
        if self.tau0 < 0:
            result.add_error(
                f"Esfuerzo de fluencia tau0={self.tau0} Pa no puede ser negativo."
            )
        if self.k <= 0:
            result.add_error(
                f"Consistencia k={self.k} Pa·sⁿ debe ser positiva."
            )
        if self.n <= 0 or self.n > 3:
            result.add_error(
                f"Índice de flujo n={self.n} fuera del rango válido (0, 3]."
            )
        if self.nu0 <= 0:
            result.add_error(
                f"Viscosidad plateau nu0={self.nu0} debe ser positiva."
            )
        if self._rho <= 0:
            result.add_error(
                f"Densidad rho={self._rho} debe ser positiva."
            )

        # Advertencias de coherencia física
        if self.nu0 < 0.01:
            result.add_warning(
                f"Viscosidad plateau nu0={self.nu0} m²/s es muy baja. "
                "Puede causar inestabilidades numéricas. Recomendado: > 0.1 m²/s."
            )

        nu_flow = self.get_kinematic_viscosity_at_shear_rate(1.0)
        if self.nu0 < nu_flow * 10:
            result.add_warning(
                f"nu0={self.nu0:.3f} m²/s debería ser al menos 2-3 órdenes "
                f"de magnitud mayor que ν_eff en zona de flujo "
                f"({nu_flow:.4f} m²/s a γ̇=1 s⁻¹)."
            )

        if self.n > 1:
            result.add_warning(
                f"n={self.n} > 1 indica fluido dilatante. "
                "Verifique que sea el comportamiento esperado."
            )

        if self.tau0 == 0:
            result.add_warning(
                "tau0=0 convierte el modelo en ley de potencia pura (sin zona plug)."
            )

        if self._rho < 1000 or self._rho > 2500:
            result.add_warning(
                f"Densidad rho={self._rho} kg/m³ fuera del rango típico "
                "para lodo/lahar (1000-2500 kg/m³)."
            )

        return result

    # ── Métodos concretos sobreescritos ──────────────────────────────────────

    def get_kinematic_viscosity_at_shear_rate(self, gamma_dot: float) -> float:
        """
        Calcula la viscosidad cinemática efectiva usando la regularización
        bi-viscosa de OpenFOAM.

        Args:
            gamma_dot: tasa de deformación [1/s]. Usar > 0.

        Returns:
            Viscosidad cinemática efectiva [m²/s].
        """
        if gamma_dot <= 0:
            return self.nu0

        eps = 1e-10
        nu_hb = (
            self.tau0_kinematic + self.k_kinematic * (gamma_dot ** self.n)
        ) / max(gamma_dot, eps)

        return min(self.nu0, nu_hb)

    # ── Análisis reológico ────────────────────────────────────────────────────

    def yield_stress_pa(self) -> float:
        """Esfuerzo de fluencia en Pa (alias legible)."""
        return self.tau0

    def effective_viscosity_curve(
        self,
        gamma_min: float = 0.001,
        gamma_max: float = 1000.0,
        n_points:  int   = 100,
    ) -> tuple[list[float], list[float]]:
        """
        Genera la curva de viscosidad efectiva vs tasa de deformación.

        Útil para graficar el comportamiento reológico en la UI.

        Args:
            gamma_min: Tasa mínima [1/s].
            gamma_max: Tasa máxima [1/s].
            n_points:  Número de puntos.

        Returns:
            Tupla (gamma_dots, nu_effs) con listas de igual longitud.
        """
        import math
        log_min = math.log10(gamma_min)
        log_max = math.log10(gamma_max)
        step = (log_max - log_min) / (n_points - 1)

        gamma_dots = [10 ** (log_min + i * step) for i in range(n_points)]
        nu_effs    = [self.get_kinematic_viscosity_at_shear_rate(g) for g in gamma_dots]

        return gamma_dots, nu_effs

    def shear_stress_curve(
        self,
        gamma_min: float = 0.001,
        gamma_max: float = 1000.0,
        n_points:  int   = 100,
    ) -> tuple[list[float], list[float]]:
        """
        Genera la curva reológica τ vs γ̇ (curva de flujo).

        Returns:
            Tupla (gamma_dots, taus) con esfuerzos en Pa.
        """
        gamma_dots, nu_effs = self.effective_viscosity_curve(
            gamma_min, gamma_max, n_points
        )
        # τ = ν_eff · ρ · γ̇   (viscosidad dinámica × tasa)
        taus = [nu * self._rho * g for nu, g in zip(nu_effs, gamma_dots)]
        return gamma_dots, taus

    @classmethod
    def from_literature_mud(cls) -> "HerschelBulkleyFluid":
        """
        Crea instancia con parámetros típicos de lodo de literatura.

        Fuente: Ancey (2007), Cochard & Ancey (2009).
        """
        return cls(tau0=50.0, k=10.0, n=0.4, nu0=1.0, rho=1800.0, sigma=0.0)

    @classmethod
    def from_experimental_data(
        cls,
        tau0:  float,
        k:     float,
        n:     float,
        rho:   float,
        nu0:   float | None = None,
    ) -> "HerschelBulkleyFluid":
        """
        Crea instancia desde datos reométricos experimentales.

        Si nu0 no se proporciona, se calcula automáticamente como 3 órdenes
        de magnitud mayor que la viscosidad cinemática a γ̇ = 0.1 s⁻¹.

        Args:
            tau0 : Esfuerzo de fluencia experimental [Pa].
            k    : Consistencia experimental [Pa·sⁿ].
            n    : Índice de flujo experimental [-].
            rho  : Densidad medida [kg/m³].
            nu0  : Viscosidad plateau [m²/s]. Si None, se auto-calcula.
        """
        if nu0 is None:
            # Auto-cálculo: 1000x mayor que ν_eff a baja tasa de deformación
            nu_ref = (tau0 / rho) / 0.1 + (k / rho) * (0.1 ** (n - 1))
            nu0 = max(nu_ref * 1000, 0.1)

        return cls(tau0=tau0, k=k, n=n, nu0=nu0, rho=rho)

    def __repr__(self) -> str:
        return (
            f"HerschelBulkleyFluid("
            f"tau0={self.tau0:.2f}, k={self.k:.2f}, "
            f"n={self.n:.2f}, nu0={self.nu0:.2f}, rho={self._rho:.1f})"
        )
