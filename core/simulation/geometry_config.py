"""
Configuración geométrica 3D del dominio de simulación.

Dominio: canal rectangular con paredes físicas en todas las caras.
    x → dirección longitudinal (largo del canal, dirección de flujo)
    y → dirección vertical     (altura, opuesta a la gravedad)
    z → dirección transversal  (ancho del canal, entre paredes laterales)

Diferencias respecto a la versión cuasi-2D:
    - Parámetro 'width' (z) es la dimensión física real del canal
    - 'nz' >= 2 genera malla 3D real (nz=1 sería cuasi-2D, no recomendado)
    - blockMeshDict incluye patches frontWall y backWall (paredes físicas)
    - setFieldsDict usa box 3D con z de 0 a width
    - compute_preview() retorna datos para vista lateral (x-y) Y vista en planta (x-z)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict


class PreviewData(TypedDict):
    """
    Datos estructurados para renderizar la previsualización geométrica.
    Incluye ambas vistas (lateral y planta) para el canal 3D.
    """
    # Dimensiones físicas
    domain_length:  float          # x — largo del canal [m]
    domain_height:  float          # y — alto del canal [m]
    domain_width:   float          # z — ancho del canal [m]
    # Malla
    nx:             int
    ny:             int
    nz:             int
    dx:             float          # tamaño celda x [m]
    dy:             float          # tamaño celda y [m]
    dz:             float          # tamaño celda z [m]
    cell_count:     int            # nx × ny × nz
    # Presa
    dam_length:     float          # extensión x de la presa [m]
    dam_height:     float          # extensión y de la presa [m]
    dam_width:      float          # extensión z de la presa [m] (= domain_width, presa ocupa todo el ancho)
    # Vista lateral (x-y): para cámara lateral del experimento
    lateral_dam_rect:   tuple[float, float, float, float]  # (x0, y0, w, h)
    lateral_grid_x:     list[float]
    lateral_grid_y:     list[float]
    # Vista en planta (x-z): para cámara superior del experimento
    plan_dam_rect:      tuple[float, float, float, float]  # (x0, z0, w, d)
    plan_grid_x:        list[float]
    plan_grid_z:        list[float]
    # Métricas
    is_3d:          bool
    aspect_ratio_yz: float         # H/W — relevante para visualización
    annotations:    list[dict]


@dataclass
class GeometryConfig:
    """
    Geometría 3D del dominio: canal rectangular con paredes en todas las caras.

    Args:
        length:          Longitud del canal [m]. Dirección x (flujo).
        height:          Altura del canal [m]. Dirección y (vertical).
        width:           Ancho del canal [m]. Dirección z (transversal).
        nx:              Celdas en x.
        ny:              Celdas en y.
        nz:              Celdas en z. Mínimo 2 para simulación 3D real.
        dam_width_frac:  Fracción de la longitud ocupada por la presa (x).
        dam_height_frac: Fracción de la altura ocupada por la presa (y).
                         La presa siempre ocupa el 100% del ancho (z).

    Ejemplo (canal de laboratorio):
        geo = GeometryConfig(
            length=1.6, height=0.6, width=0.15,
            nx=80, ny=30, nz=8,
            dam_width_frac=0.25, dam_height_frac=0.50,
        )
    """
    length:          float = 1.6     # x [m]
    height:          float = 0.6     # y [m]
    width:           float = 0.15    # z [m]
    nx:              int   = 80
    ny:              int   = 30
    nz:              int   = 8
    dam_width_frac:  float = 0.25    # fracción de length
    dam_height_frac: float = 0.50    # fracción de height
    # La presa siempre ocupa el 100% del ancho (dam_depth_frac = 1.0)

    # ── Propiedades derivadas ─────────────────────────────────────────────────

    @property
    def dx(self) -> float:
        return self.length / self.nx

    @property
    def dy(self) -> float:
        return self.height / self.ny

    @property
    def dz(self) -> float:
        return self.width / self.nz

    @property
    def cell_count(self) -> int:
        return self.nx * self.ny * self.nz

    @property
    def dam_length(self) -> float:
        """Extensión longitudinal de la presa [m]."""
        return self.length * self.dam_width_frac

    @property
    def dam_height(self) -> float:
        """Extensión vertical de la presa [m]."""
        return self.height * self.dam_height_frac

    @property
    def is_3d(self) -> bool:
        return self.nz >= 2

    @property
    def aspect_ratio_yz(self) -> float:
        return self.height / max(self.width, 1e-9)

    # ── Preview (datos para GeometryPreviewWidget) ────────────────────────────

    def compute_preview(self, max_grid_lines: int = 20) -> PreviewData:
        """
        Calcula los datos para renderizar AMBAS vistas del dominio 3D.

        Vista lateral (x-y): perfil del fluido — comparable con cámara lateral.
        Vista en planta (x-z): distribución transversal — comparable con cámara superior.

        Args:
            max_grid_lines: Máximo de líneas de malla por dirección.

        Returns:
            PreviewData con todo lo necesario para las dos vistas.
        """
        step_x = max(1, self.nx // max_grid_lines)
        step_y = max(1, self.ny // max_grid_lines)
        step_z = max(1, self.nz // max_grid_lines)

        grid_x = [i * self.dx for i in range(0, self.nx + 1, step_x)]
        grid_y = [j * self.dy for j in range(0, self.ny + 1, step_y)]
        grid_z = [k * self.dz for k in range(0, self.nz + 1, step_z)]

        annotations = [
            {"text": f"L = {self.length:.3f} m",  "role": "dim_x",
             "x": self.length/2, "y": -self.height*0.08, "ha": "center"},
            {"text": f"H = {self.height:.3f} m",  "role": "dim_y",
             "x": -self.length*0.07, "y": self.height/2, "ha": "center", "rotation": 90},
            {"text": f"W = {self.width:.3f} m",   "role": "dim_z",
             "x": self.length/2, "y": -self.width*0.08, "ha": "center"},
            {"text": (f"Δx={self.dx*1000:.1f} mm  "
                      f"Δy={self.dy*1000:.1f} mm  "
                      f"Δz={self.dz*1000:.1f} mm"),
             "role": "cell_size",
             "x": self.length/2, "y": self.height*1.06, "ha": "center"},
            {"text": f"{self.nx}×{self.ny}×{self.nz} = {self.cell_count:,} celdas",
             "role": "cell_count",
             "x": self.length/2, "y": self.height*1.12, "ha": "center"},
        ]

        return PreviewData(
            domain_length  = self.length,
            domain_height  = self.height,
            domain_width   = self.width,
            nx=self.nx, ny=self.ny, nz=self.nz,
            dx=self.dx, dy=self.dy, dz=self.dz,
            cell_count     = self.cell_count,
            dam_length     = self.dam_length,
            dam_height     = self.dam_height,
            dam_width      = self.width,   # presa ocupa todo el ancho
            lateral_dam_rect = (0.0, 0.0, self.dam_length, self.dam_height),
            lateral_grid_x   = grid_x,
            lateral_grid_y   = grid_y,
            plan_dam_rect    = (0.0, 0.0, self.dam_length, self.width),
            plan_grid_x      = grid_x,
            plan_grid_z      = grid_z,
            is_3d          = self.is_3d,
            aspect_ratio_yz = self.aspect_ratio_yz,
            annotations    = annotations,
        )

    # ── Generación de archivos OpenFOAM ──────────────────────────────────────

    def to_block_mesh_dict(self) -> str:
        """
        Genera system/blockMeshDict para dominio 3D con paredes físicas.

        Patches generados:
            leftWall   — x=0 (pared aguas arriba)
            rightWall  — x=L (pared donde impacta el fluido / sensores)
            lowerWall  — y=0 (suelo del canal)
            atmosphere — y=H (salida libre superior)
            frontWall  — z=0 (pared lateral física)
            backWall   — z=W (pared lateral física)
        """
        L, H, W = self.length, self.height, self.width

        return f"""/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\\\    /   O peration     | Website:  https://openfoam.org
    \\\\  /    A nd           | Version:  9
     \\\\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    format      ascii;
    class       dictionary;
    object      blockMeshDict;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

// Canal 3D: {L:.4f} m x {H:.4f} m x {W:.4f} m
// Malla:    {self.nx} x {self.ny} x {self.nz} celdas
// Tamaño:   dx={self.dx*1000:.2f}mm  dy={self.dy*1000:.2f}mm  dz={self.dz*1000:.2f}mm

convertToMeters 1;

vertices
(
    (0   0   0  )  // 0 — esquina inf. izq. frente  (x=0, y=0, z=0)
    ({L:.6g}  0   0  )  // 1 — esquina inf. der. frente  (x=L, y=0, z=0)
    ({L:.6g}  {H:.6g}  0  )  // 2 — esquina sup. der. frente  (x=L, y=H, z=0)
    (0   {H:.6g}  0  )  // 3 — esquina sup. izq. frente  (x=0, y=H, z=0)
    (0   0   {W:.6g} )  // 4 — esquina inf. izq. fondo   (x=0, y=0, z=W)
    ({L:.6g}  0   {W:.6g} )  // 5 — esquina inf. der. fondo   (x=L, y=0, z=W)
    ({L:.6g}  {H:.6g}  {W:.6g} )  // 6 — esquina sup. der. fondo   (x=L, y=H, z=W)
    (0   {H:.6g}  {W:.6g} )  // 7 — esquina sup. izq. fondo   (x=0, y=H, z=W)
);

blocks
(
    hex (0 1 2 3 4 5 6 7) ({self.nx} {self.ny} {self.nz}) simpleGrading (1 1 1)
);

edges
(
);

boundary
(
    leftWall
    {{
        type wall;
        faces ( (0 3 7 4) );
    }}
    rightWall
    {{
        type wall;
        faces ( (1 5 6 2) );
    }}
    lowerWall
    {{
        type wall;
        faces ( (0 4 5 1) );
    }}
    atmosphere
    {{
        type patch;
        faces ( (3 2 6 7) );
    }}
    frontWall
    {{
        type wall;
        faces ( (0 1 2 3) );
    }}
    backWall
    {{
        type wall;
        faces ( (4 7 6 5) );
    }}
);

mergePatchPairs
(
);

// ************************************************************************* //
"""

    def to_set_fields_dict(self, phase_name: str = "lodo") -> str:
        """
        Genera system/setFieldsDict para columna inicial 3D.

        La presa ocupa:
            x: [0, dam_length]
            y: [0, dam_height]
            z: [0, width]  ← toda la profundidad del canal
        """
        return f"""/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\\\    /   O peration     | Version:  9
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    format      ascii;
    class       dictionary;
    location    "system";
    object      setFieldsDict;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

// Columna inicial 3D (presa ocupa todo el ancho del canal):
//   x: [0, {self.dam_length:.4f} m]  ({self.dam_width_frac*100:.0f}% de L={self.length:.4f} m)
//   y: [0, {self.dam_height:.4f} m]  ({self.dam_height_frac*100:.0f}% de H={self.height:.4f} m)
//   z: [0, {self.width:.4f} m]       (100% del ancho — paredes físicas)

defaultFieldValues
(
    volScalarFieldValue alpha.{phase_name} 0
);

regions
(
    boxToCell
    {{
        box (0 0 0) ({self.dam_length:.6g} {self.dam_height:.6g} {self.width:.6g});
        fieldValues
        (
            volScalarFieldValue alpha.{phase_name} 1
        );
    }}
);

// ************************************************************************* //
"""

    # ── Validación ────────────────────────────────────────────────────────────

    def validate(self) -> list[str]:
        errors = []
        if self.length <= 0:
            errors.append(f"length={self.length} debe ser positivo.")
        if self.height <= 0:
            errors.append(f"height={self.height} debe ser positivo.")
        if self.width <= 0:
            errors.append(f"width={self.width} debe ser positivo.")
        if self.nx < 4:
            errors.append(f"nx={self.nx} debe ser >= 4.")
        if self.ny < 4:
            errors.append(f"ny={self.ny} debe ser >= 4.")
        if self.nz < 2:
            errors.append(f"nz={self.nz} debe ser >= 2 para simulación 3D.")
        if not 0 < self.dam_width_frac < 1:
            errors.append(f"dam_width_frac={self.dam_width_frac} debe estar en (0,1).")
        if not 0 < self.dam_height_frac < 1:
            errors.append(f"dam_height_frac={self.dam_height_frac} debe estar en (0,1).")
        if self.dz > self.dx * 3:
            errors.append(
                f"Malla muy anisótropa: dz={self.dz*1000:.1f}mm >> dx={self.dx*1000:.1f}mm. "
                "Aumentar nz para equilibrar."
            )
        return errors

    def __repr__(self) -> str:
        return (
            f"GeometryConfig("
            f"L={self.length}m, H={self.height}m, W={self.width}m, "
            f"nx={self.nx}, ny={self.ny}, nz={self.nz}, "
            f"cells={self.cell_count:,})"
        )
