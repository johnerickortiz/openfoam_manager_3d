"""
Configuración completa de una simulación OpenFOAM 3D.

Novedades respecto a la versión 2D:
    - turbulence_mode: selección automática según el fluido o manual
        * "auto"    → laminar para HB, kEpsilon para Newtoniano
        * "laminar" → fuerza laminar (recomendado para lodo en laboratorio)
        * "kEpsilon", "kOmegaSST" → modelos RANS
    - effective_turbulence_model: propiedad calculada (la que usa CaseGenerator)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from core.models.fluid_model import FluidModel
from core.models.newtonian import NewtonianFluid
from core.models.herschel_bulkley import HerschelBulkleyFluid
from core.simulation.geometry_config import GeometryConfig


class TurbulenceModel(str, Enum):
    """Modelos de turbulencia disponibles en OpenFOAM 9."""
    LAMINAR     = "laminar"
    K_EPSILON   = "kEpsilon"
    K_OMEGA_SST = "kOmegaSST"

    @property
    def display_name(self) -> str:
        names = {
            "laminar":    "Laminar (sin turbulencia)",
            "kEpsilon":   "RAS k-ε",
            "kOmegaSST":  "RAS k-ω SST",
        }
        return names.get(self.value, self.value)

    @property
    def is_ras(self) -> bool:
        return self != TurbulenceModel.LAMINAR


class TurbulenceMode(str, Enum):
    """Modo de selección de turbulencia."""
    AUTO        = "auto"      # Elige según el fluido (recomendado)
    LAMINAR     = "laminar"   # Fuerza laminar
    K_EPSILON   = "kEpsilon"
    K_OMEGA_SST = "kOmegaSST"

    @property
    def display_name(self) -> str:
        names = {
            "auto":       "Automático (laminar para HB, k-ε para agua)",
            "laminar":    "Laminar (sin turbulencia)",
            "kEpsilon":   "RAS k-ε",
            "kOmegaSST":  "RAS k-ω SST",
        }
        return names.get(self.value, self.value)


@dataclass
class SimulationConfig:
    """
    Configuración completa de una simulación OpenFOAM 3D.

    Args:
        name:             Nombre identificador del caso.
        end_time:         Tiempo final [s].
        write_interval:   Intervalo de escritura [s].
        max_courant:      Número de Courant máximo.
        fluid:            Fluido principal (HB o Newtoniano).
        air:              Propiedades del aire.
        geometry:         Geometría 3D del dominio.
        turbulence_mode:  Modo de selección de turbulencia.
        phase_name:       Nombre de la fase en OpenFOAM.
        output_dir:       Directorio de salida.
        description:      Descripción del caso.
    """
    name:             str            = "damBreakLodo"
    end_time:         float          = 5.0
    write_interval:   float          = 0.05
    max_courant:      float          = 0.5
    fluid:            FluidModel     = field(
        default_factory=HerschelBulkleyFluid.from_literature_mud
    )
    air:              NewtonianFluid = field(default_factory=NewtonianFluid.air)
    geometry:         GeometryConfig = field(default_factory=GeometryConfig)
    turbulence_mode:  TurbulenceMode = TurbulenceMode.AUTO
    phase_name:       str            = "lodo"
    output_dir:       str            = "~/openfoam_cases"
    description:      str            = ""

    # ── Turbulencia efectiva ──────────────────────────────────────────────────

    @property
    def effective_turbulence_model(self) -> TurbulenceModel:
        """
        Modelo de turbulencia que realmente se usa en la simulación.

        Lógica 'auto':
            - Herschel-Bulkley → laminar
              (flujo viscoplástico en laboratorio suele ser laminar;
               k-ε introduciría viscosidad turbulenta artificial)
            - Newtoniano → kEpsilon
              (agua a velocidades de dam-break es turbulenta)

        El usuario puede sobreescribir esta lógica con turbulence_mode.
        """
        if self.turbulence_mode == TurbulenceMode.AUTO:
            if isinstance(self.fluid, HerschelBulkleyFluid):
                return TurbulenceModel.LAMINAR
            return TurbulenceModel.K_EPSILON

        # Modos explícitos
        mode_map = {
            TurbulenceMode.LAMINAR:     TurbulenceModel.LAMINAR,
            TurbulenceMode.K_EPSILON:   TurbulenceModel.K_EPSILON,
            TurbulenceMode.K_OMEGA_SST: TurbulenceModel.K_OMEGA_SST,
        }
        return mode_map.get(self.turbulence_mode, TurbulenceModel.LAMINAR)

    # ── Propiedades derivadas ─────────────────────────────────────────────────

    @property
    def case_dir(self) -> Path:
        return Path(self.output_dir).expanduser() / self.name

    @property
    def alpha_field_name(self) -> str:
        return f"alpha.{self.phase_name}"

    @property
    def n_write_steps(self) -> int:
        return max(1, int(self.end_time / self.write_interval))

    @property
    def sigma(self) -> float:
        if hasattr(self.fluid, "sigma"):
            return self.fluid.sigma
        return 0.0

    # ── Validación ────────────────────────────────────────────────────────────

    def validate(self) -> list[str]:
        errors: list[str] = []

        if not self.name or not self.name.replace("_", "").replace("-", "").isalnum():
            errors.append(f"Nombre '{self.name}' inválido.")
        if self.end_time <= 0:
            errors.append(f"end_time={self.end_time} debe ser positivo.")
        if self.write_interval <= 0:
            errors.append(f"write_interval={self.write_interval} debe ser positivo.")
        if self.write_interval > self.end_time:
            errors.append("write_interval no puede ser mayor que end_time.")
        if not 0 < self.max_courant <= 2.0:
            errors.append(f"max_courant={self.max_courant} debe estar en (0, 2].")

        fluid_result = self.fluid.validate()
        if not fluid_result.is_valid:
            errors.extend(f"[Fluido] {e}" for e in fluid_result.errors)

        geo_errors = self.geometry.validate()
        errors.extend(f"[Geometría] {e}" for e in geo_errors)

        return errors

    def is_valid(self) -> bool:
        return len(self.validate()) == 0

    # ── Serialización JSON ────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        fluid_dict = self.fluid.get_parameters()
        fluid_dict["__type__"] = self.fluid.__class__.__name__

        return {
            "name":             self.name,
            "description":      self.description,
            "end_time":         self.end_time,
            "write_interval":   self.write_interval,
            "max_courant":      self.max_courant,
            "phase_name":       self.phase_name,
            "output_dir":       self.output_dir,
            "turbulence_mode":  self.turbulence_mode.value,
            "fluid": fluid_dict,
            "air": {"nu": self.air.nu, "rho": self.air.rho},
            "geometry": {
                "length":          self.geometry.length,
                "height":          self.geometry.height,
                "width":           self.geometry.width,
                "nx":              self.geometry.nx,
                "ny":              self.geometry.ny,
                "nz":              self.geometry.nz,
                "dam_width_frac":  self.geometry.dam_width_frac,
                "dam_height_frac": self.geometry.dam_height_frac,
            },
        }

    def save_json(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load_json(cls, path: str | Path) -> "SimulationConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        fluid_data = data["fluid"]
        fluid_type = fluid_data.pop("__type__", "NewtonianFluid")

        if fluid_type == "HerschelBulkleyFluid":
            fluid = HerschelBulkleyFluid(
                tau0=fluid_data.get("tau0", 50.0),
                k   =fluid_data.get("k",    10.0),
                n   =fluid_data.get("n",    0.4),
                nu0 =fluid_data.get("nu0",  1.0),
                rho =fluid_data.get("rho",  1800.0),
                sigma=fluid_data.get("sigma", 0.0),
            )
        else:
            fluid = NewtonianFluid(
                nu   =fluid_data.get("nu",    1e-6),
                rho  =fluid_data.get("rho",   1000.0),
                sigma=fluid_data.get("sigma", 0.07),
            )

        air_data = data.get("air", {})
        geo_data = data["geometry"]

        return cls(
            name            = data["name"],
            description     = data.get("description", ""),
            end_time        = data["end_time"],
            write_interval  = data["write_interval"],
            max_courant     = data.get("max_courant", 0.5),
            phase_name      = data.get("phase_name", "lodo"),
            output_dir      = data.get("output_dir", "~/openfoam_cases"),
            turbulence_mode = TurbulenceMode(
                data.get("turbulence_mode", "auto")
            ),
            fluid    = fluid,
            air      = NewtonianFluid(
                nu =air_data.get("nu",  1.48e-5),
                rho=air_data.get("rho", 1.0),
            ),
            geometry = GeometryConfig(**geo_data),
        )

    # ── Presets ───────────────────────────────────────────────────────────────

    @classmethod
    def preset_mud_3d(cls) -> "SimulationConfig":
        """Lodo en canal de laboratorio — parámetros de literatura."""
        return cls(
            name        = "damBreakLodo3D",
            description = "Lodo volcánico 3D — canal 1.6×0.6×0.15 m",
            fluid       = HerschelBulkleyFluid.from_literature_mud(),
            geometry    = GeometryConfig(
                length=1.6, height=0.6, width=0.15,
                nx=80, ny=30, nz=8,
                dam_width_frac=0.25, dam_height_frac=0.50,
            ),
            turbulence_mode = TurbulenceMode.AUTO,  # → laminar para HB
            end_time    = 5.0,
            write_interval = 0.05,
        )

    @classmethod
    def preset_water_3d(cls) -> "SimulationConfig":
        """Agua newtoniana en canal de laboratorio — referencia."""
        return cls(
            name        = "damBreakAgua3D",
            description = "Agua newtoniana 3D — canal 1.6×0.6×0.15 m",
            fluid       = NewtonianFluid.water(),
            geometry    = GeometryConfig(
                length=1.6, height=0.6, width=0.15,
                nx=80, ny=30, nz=8,
                dam_width_frac=0.25, dam_height_frac=0.50,
            ),
            turbulence_mode = TurbulenceMode.AUTO,  # → kEpsilon para agua
            end_time    = 5.0,
            write_interval = 0.05,
        )

    def __repr__(self) -> str:
        turb = self.effective_turbulence_model.value
        return (
            f"SimulationConfig(name='{self.name}', "
            f"fluid={self.fluid.__class__.__name__}, "
            f"turb={turb}, "
            f"geo={self.geometry.nx}×{self.geometry.ny}×{self.geometry.nz})"
        )
