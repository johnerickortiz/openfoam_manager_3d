"""
Generador de casos OpenFOAM 3D.

Genera la estructura completa de archivos para una simulación 3D con interFoam.
Diferencias clave respecto a la versión 2D:

    BC (condiciones de contorno):
        - frontWall y backWall son paredes físicas (noSlip, fixedFluxPressure...)
        - No existe 'defaultFaces' con type empty (solo válido en cuasi-2D)

    Turbulencia inteligente (effective_turbulence_model):
        - Laminar → archivo turbulenceProperties sin bloque RAS
                  → fvSolution sin entradas k/epsilon
        - RAS     → kEpsilon/kOmegaSST con wall functions en las 6 paredes

    fvSolution 3D:
        - nNonOrthogonalCorrectors 1 (recomendado para exactitud en 3D)

    blockMeshDict y setFieldsDict:
        - Vienen directamente de GeometryConfig (ya actualizados en Paso 1)
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from core.models import HerschelBulkleyFluid, NewtonianFluid
from core.simulation import SimulationConfig, GeometryConfig
from core.simulation.simulation_config import TurbulenceModel


class CaseGenerator:
    """
    Genera la estructura completa de un caso OpenFOAM 3D.

    Args:
        log_callback: Función opcional para mensajes de progreso.
    """

    def __init__(
        self,
        log_callback: Callable[[str], None] | None = None,
    ) -> None:
        self._log = log_callback or (lambda msg: None)

    # ── API principal ─────────────────────────────────────────────────────────

    def generate(self, config: SimulationConfig) -> Path:
        """
        Genera todos los archivos del caso OpenFOAM 3D.

        Returns:
            Path al directorio del caso generado.
        """
        errors = config.validate()
        if errors:
            raise ValueError(
                "Configuración inválida:\n" + "\n".join(f"  - {e}" for e in errors)
            )

        case_dir = config.case_dir
        turb     = config.effective_turbulence_model
        self._log(f"Generando caso 3D en: {case_dir}")
        self._log(f"  Turbulencia: {turb.value}")
        self._log(f"  Malla: {config.geometry.nx}×"
                  f"{config.geometry.ny}×{config.geometry.nz} = "
                  f"{config.geometry.cell_count:,} celdas")

        for d in [case_dir/"0", case_dir/"constant", case_dir/"system"]:
            d.mkdir(parents=True, exist_ok=True)

        self._write_initial_conditions(config, case_dir, turb)
        self._write_constant(config, case_dir, turb)
        self._write_system(config, case_dir)

        self._log(f"✅ Caso '{config.name}' generado.")
        return case_dir

    # ── Condiciones iniciales (0/) ────────────────────────────────────────────

    def _write_initial_conditions(
        self,
        config:   SimulationConfig,
        case_dir: Path,
        turb:     TurbulenceModel,
    ) -> None:
        self._log("\n[Condiciones iniciales]")
        z_dir  = case_dir / "0"
        phase  = config.phase_name
        is_ras = turb.is_ras

        files = {
            f"alpha.{phase}.orig": self._alpha_field(phase),
            "U":                   self._velocity_field(),
            "p_rgh":               self._pressure_field(),
            "k":                   self._k_field(is_ras),
            "epsilon":             self._epsilon_field(is_ras),
            "nut":                 self._nut_field(is_ras),
        }

        for fname, content in files.items():
            (z_dir / fname).write_text(content, encoding="utf-8")
            self._log(f"  ✓ 0/{fname}")

    def _foam_header(self, cls: str, obj: str, loc: str = "0") -> str:
        return (
            f'/*--------------------------------*- C++ -*--'
            f'----------------------------------*\\\n'
            f'  =========                 |\n'
            f'  \\\\\\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox\n'
            f'   \\\\\\\\    /   O peration     | Version:  9\n'
            f'\\*-----------------------------------------------------------'
            f'----------------*/\n'
            f'FoamFile\n{{\n'
            f'    format      ascii;\n'
            f'    class       {cls};\n'
            f'    location    "{loc}";\n'
            f'    object      {obj};\n'
            f'}}\n'
            f'// * * * * * * * * * * * * * * * * * * * * * * * * //\n\n'
        )

    def _alpha_field(self, phase: str) -> str:
        hdr = self._foam_header("volScalarField", f"alpha.{phase}")
        return hdr + f"""dimensions      [0 0 0 0 0 0 0];
internalField   uniform 0;

boundaryField
{{
    leftWall    {{ type zeroGradient; }}
    rightWall   {{ type zeroGradient; }}
    lowerWall   {{ type zeroGradient; }}
    atmosphere  {{ type inletOutlet; inletValue uniform 0; value uniform 0; }}
    frontWall   {{ type zeroGradient; }}
    backWall    {{ type zeroGradient; }}
}}

// ************************************************************************* //
"""

    def _velocity_field(self) -> str:
        hdr = self._foam_header("volVectorField", "U")
        return hdr + """dimensions      [0 1 -1 0 0 0 0];
internalField   uniform (0 0 0);

boundaryField
{
    leftWall    { type noSlip; }
    rightWall   { type noSlip; }
    lowerWall   { type noSlip; }
    atmosphere  { type pressureInletOutletVelocity; value uniform (0 0 0); }
    frontWall   { type noSlip; }
    backWall    { type noSlip; }
}

// ************************************************************************* //
"""

    def _pressure_field(self) -> str:
        hdr = self._foam_header("volScalarField", "p_rgh")
        return hdr + """dimensions      [1 -1 -2 0 0 0 0];
internalField   uniform 0;

boundaryField
{
    leftWall    { type fixedFluxPressure; gradient uniform 0; value uniform 0; }
    rightWall   { type fixedFluxPressure; gradient uniform 0; value uniform 0; }
    lowerWall   { type fixedFluxPressure; gradient uniform 0; value uniform 0; }
    atmosphere  { type totalPressure; p0 uniform 0; }
    frontWall   { type fixedFluxPressure; gradient uniform 0; value uniform 0; }
    backWall    { type fixedFluxPressure; gradient uniform 0; value uniform 0; }
}

// ************************************************************************* //
"""

    def _k_field(self, is_ras: bool) -> str:
        hdr  = self._foam_header("volScalarField", "k")
        val  = "uniform 1e-4" if is_ras else "uniform 0"
        wall = "kqRWallFunction" if is_ras else "zeroGradient"
        atm  = f"inletOutlet; inletValue {val}; value {val}" if is_ras \
               else "zeroGradient"

        if is_ras:
            walls_bc = f"{{ type {wall}; value {val}; }}"
        else:
            walls_bc = f"{{ type {wall}; }}"

        return hdr + f"""dimensions      [0 2 -2 0 0 0 0];
internalField   {val};

boundaryField
{{
    leftWall    {walls_bc}
    rightWall   {walls_bc}
    lowerWall   {walls_bc}
    atmosphere  {{ type {atm}; }}
    frontWall   {walls_bc}
    backWall    {walls_bc}
}}

// ************************************************************************* //
"""

    def _epsilon_field(self, is_ras: bool) -> str:
        hdr  = self._foam_header("volScalarField", "epsilon")
        val  = "uniform 1e-4" if is_ras else "uniform 0"
        wall = "epsilonWallFunction" if is_ras else "zeroGradient"
        atm  = f"inletOutlet; inletValue {val}; value {val}" if is_ras \
               else "zeroGradient"

        if is_ras:
            walls_bc = f"{{ type {wall}; value {val}; }}"
        else:
            walls_bc = f"{{ type {wall}; }}"

        return hdr + f"""dimensions      [0 2 -3 0 0 0 0];
internalField   {val};

boundaryField
{{
    leftWall    {walls_bc}
    rightWall   {walls_bc}
    lowerWall   {walls_bc}
    atmosphere  {{ type {atm}; }}
    frontWall   {walls_bc}
    backWall    {walls_bc}
}}

// ************************************************************************* //
"""

    def _nut_field(self, is_ras: bool) -> str:
        hdr  = self._foam_header("volScalarField", "nut")
        wall = "nutkWallFunction" if is_ras else "calculated"
        return hdr + f"""dimensions      [0 2 -1 0 0 0 0];
internalField   uniform 0;

boundaryField
{{
    leftWall    {{ type {wall}; value uniform 0; }}
    rightWall   {{ type {wall}; value uniform 0; }}
    lowerWall   {{ type {wall}; value uniform 0; }}
    atmosphere  {{ type calculated; value uniform 0; }}
    frontWall   {{ type {wall}; value uniform 0; }}
    backWall    {{ type {wall}; value uniform 0; }}
}}

// ************************************************************************* //
"""

    # ── Constantes (constant/) ────────────────────────────────────────────────

    def _write_constant(
        self,
        config:   SimulationConfig,
        case_dir: Path,
        turb:     TurbulenceModel,
    ) -> None:
        self._log("\n[Propiedades constantes]")
        const = case_dir / "constant"

        files = {
            "transportProperties":  self._transport_properties(config),
            "turbulenceProperties": self._turbulence_properties(turb),
            "g":                    self._gravity(),
        }
        for fname, content in files.items():
            (const / fname).write_text(content, encoding="utf-8")
            self._log(f"  ✓ constant/{fname}")

    def _transport_properties(self, config: SimulationConfig) -> str:
        phase      = config.phase_name
        fluid_blk  = config.fluid.to_foam_dict(phase)
        air_blk    = config.air.to_foam_dict("air")
        hdr        = self._foam_header("dictionary", "transportProperties", "constant")
        return hdr + f"""phases ({phase} air);

{fluid_blk}

{air_blk}

sigma    {config.sigma:.6g};

// ************************************************************************* //
"""

    def _turbulence_properties(self, turb: TurbulenceModel) -> str:
        hdr = self._foam_header("dictionary", "turbulenceProperties", "constant")

        if turb == TurbulenceModel.LAMINAR:
            body = "simulationType  laminar;\n"
        else:
            body = (
                f"simulationType  RAS;\n\n"
                f"RAS\n{{\n"
                f"    model           {turb.value};\n"
                f"    turbulence      on;\n"
                f"    printCoeffs     on;\n"
                f"}}\n"
            )
        return hdr + body + "\n// ************************************************************************* //\n"

    def _gravity(self) -> str:
        hdr = self._foam_header("uniformDimensionedVectorField", "g", "constant")
        return hdr + """dimensions      [0 1 -2 0 0 0 0];
value           (0 -9.81 0);

// ************************************************************************* //
"""

    # ── Sistema (system/) ─────────────────────────────────────────────────────

    def _write_system(
        self,
        config:   SimulationConfig,
        case_dir: Path,
    ) -> None:
        self._log("\n[Parámetros del sistema]")
        sys_dir = case_dir / "system"
        turb    = config.effective_turbulence_model
        geo     = config.geometry

        files = {
            "blockMeshDict": geo.to_block_mesh_dict(),
            "setFieldsDict": geo.to_set_fields_dict(config.phase_name),
            "controlDict":   self._control_dict(config),
            "fvSchemes":     self._fv_schemes(config),
            "fvSolution":    self._fv_solution(config, turb),
        }
        for fname, content in files.items():
            (sys_dir / fname).write_text(content, encoding="utf-8")
            self._log(f"  ✓ system/{fname}")

    def _control_dict(self, config: SimulationConfig) -> str:
        hdr = self._foam_header("dictionary", "controlDict", "system")
        return hdr + f"""application     interFoam;

startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         {config.end_time:.6g};

deltaT          0.001;

writeControl    adjustableRunTime;
writeInterval   {config.write_interval:.6g};
purgeWrite      0;
writeFormat     ascii;
writePrecision  6;
writeCompression off;

timeFormat      general;
timePrecision   6;

runTimeModifiable yes;
adjustTimeStep  yes;
maxCo           {config.max_courant:.4g};
maxAlphaCo      {config.max_courant:.4g};
maxDeltaT       1;

// ************************************************************************* //
"""

    def _fv_schemes(self, config: SimulationConfig) -> str:
        phase = config.phase_name
        hdr   = self._foam_header("dictionary", "fvSchemes", "system")
        return hdr + f"""ddtSchemes
{{
    default         Euler;
}}

gradSchemes
{{
    default         Gauss linear;
}}

divSchemes
{{
    default         none;
    div(rhoPhi,U)               Gauss linearUpwind grad(U);
    div(phi,alpha)              Gauss vanLeer;
    div(phirb,alpha)            Gauss linear;
    div(((rho*nuEff)*dev2(T(grad(U))))) Gauss linear;
    div(phi,k)                  Gauss upwind;
    div(phi,epsilon)            Gauss upwind;
    div(phi,omega)              Gauss upwind;
}}

laplacianSchemes
{{
    default         Gauss linear corrected;
}}

interpolationSchemes
{{
    default         linear;
}}

snGradSchemes
{{
    default         corrected;
}}

// ************************************************************************* //
"""

    def _fv_solution(
        self,
        config: SimulationConfig,
        turb:   TurbulenceModel,
    ) -> str:
        phase  = config.phase_name
        hdr    = self._foam_header("dictionary", "fvSolution", "system")

        # Bloque de solvers para turbulencia
        if turb.is_ras:
            # String plano (NO f-string) — usar llaves simples { }
            turb_solvers = """
    UFinal
    {
        $U;
        relTol          0;
    }

    "(k|epsilon|omega|nuTilda).*"
    {
        solver          PBiCGStab;
        preconditioner  DILU;
        tolerance       1e-08;
        relTol          0;
    }
"""
        else:
            # Laminar — string plano, llaves simples
            turb_solvers = """
    UFinal
    {
        $U;
        relTol          0;
    }
"""

        return hdr + f"""solvers
{{
    "alpha.{phase}.*"
    {{
        nAlphaCorr      2;
        nAlphaSubCycles 1;
        cAlpha          1;
        icAlpha         0;
        MULESCorr       yes;
        nLimiterIter    3;
        alphaApplyPrevCorr yes;
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-8;
        relTol          0;
        minIter         1;
    }}

    "pcorr.*"
    {{
        solver          PCG;
        preconditioner  DIC;
        tolerance       1e-5;
        relTol          0;
    }}

    p_rgh
    {{
        solver          PCG;
        preconditioner  DIC;
        tolerance       1e-07;
        relTol          0.05;
    }}

    p_rghFinal
    {{
        $p_rgh;
        relTol          0;
    }}

    U
    {{
        solver          PBiCGStab;
        preconditioner  DILU;
        tolerance       1e-06;
        relTol          0;
    }}
{turb_solvers}
}}

PIMPLE
{{
    momentumPredictor   no;
    nCorrectors         3;
    nNonOrthogonalCorrectors 1;
    pRefCell            0;
    pRefValue           0;
}}

relaxationFactors
{{
    equations
    {{
        U       0.7;
        k       0.7;
        epsilon 0.7;
    }}
}}

// ************************************************************************* //
"""

    # ── Utilidades ────────────────────────────────────────────────────────────

    def list_generated_files(self, case_dir: Path) -> list[str]:
        return sorted(
            str(f.relative_to(case_dir))
            for f in case_dir.rglob("*") if f.is_file()
        )

    def __repr__(self) -> str:
        return "CaseGenerator3D()"
