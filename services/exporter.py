"""
Exportador de resultados en múltiples formatos.

Soporta:
    CSV   — Datos tabulares universales
    JSON  — Configuración + resultados completos
    Excel — Múltiples hojas con datos y métricas
    PNG   — Gráficas de matplotlib
    VTK   — Campos volumétricos para ParaView
    HDF5  — Almacenamiento científico estructurado
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Callable

import numpy as np

from core.postprocessing import WaveFrontData
from core.simulation import SimulationConfig
from services.data_extractor import ExperimentalData


class ExportFormat(str, Enum):
    """Formatos de exportación disponibles."""
    CSV   = "csv"
    JSON  = "json"
    EXCEL = "excel"
    PNG   = "png"
    VTK   = "vtk"
    HDF5  = "hdf5"

    @property
    def extension(self) -> str:
        exts = {
            "csv":   ".csv",
            "json":  ".json",
            "excel": ".xlsx",
            "png":   ".png",
            "vtk":   ".vtk",
            "hdf5":  ".h5",
        }
        return exts[self.value]

    @property
    def display_name(self) -> str:
        names = {
            "csv":   "CSV (datos tabulares)",
            "json":  "JSON (configuración + resultados)",
            "excel": "Excel (.xlsx, múltiples hojas)",
            "png":   "PNG (gráficas)",
            "vtk":   "VTK (para ParaView)",
            "hdf5":  "HDF5 (científico)",
        }
        return names[self.value]


class Exporter:
    """
    Exporta resultados de simulación a múltiples formatos.

    Args:
        output_dir:   Directorio de salida para los archivos.
        log_callback: Función para mensajes de progreso.

    Ejemplo:
        exporter = Exporter(output_dir="~/resultados", log_callback=print)
        paths = exporter.export_all(data, config, prefix="damBreakLodo")
        print(f"Exportados: {paths}")
    """

    def __init__(
        self,
        output_dir:   str | Path = ".",
        log_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.output_dir = Path(output_dir).expanduser()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._log = log_callback or (lambda msg: None)

    # ── API principal ─────────────────────────────────────────────────────────

    def export(
        self,
        data:   WaveFrontData,
        format: ExportFormat,
        prefix: str = "simulation",
        config: SimulationConfig | None = None,
        experimental: list[ExperimentalData] | None = None,
    ) -> Path:
        """
        Exporta los datos en el formato especificado.

        Args:
            data:         WaveFrontData de la simulación.
            format:       Formato de exportación.
            prefix:       Prefijo del nombre de archivo.
            config:       Configuración de la simulación (para metadatos).
            experimental: Datos experimentales a incluir (si aplica).

        Returns:
            Path al archivo generado.
        """
        exporters = {
            ExportFormat.CSV:   self._export_csv,
            ExportFormat.JSON:  self._export_json,
            ExportFormat.EXCEL: self._export_excel,
            ExportFormat.PNG:   self._export_png,
            ExportFormat.VTK:   self._export_vtk,
            ExportFormat.HDF5:  self._export_hdf5,
        }

        fn    = exporters[format]
        path  = fn(data, prefix, config, experimental or [])
        self._log(f"✓ Exportado [{format.value}]: {path.name}")
        return path

    def export_all(
        self,
        data:         WaveFrontData,
        prefix:       str = "simulation",
        config:       SimulationConfig | None = None,
        experimental: list[ExperimentalData] | None = None,
        formats:      list[ExportFormat] | None = None,
    ) -> dict[ExportFormat, Path]:
        """
        Exporta en todos los formatos especificados.

        Args:
            data:         WaveFrontData de la simulación.
            prefix:       Prefijo del nombre del archivo.
            config:       Configuración de la simulación.
            experimental: Datos experimentales opcionales.
            formats:      Lista de formatos. Si None, usa CSV + JSON + Excel + PNG.

        Returns:
            Dict {formato → path} de archivos generados.
        """
        if formats is None:
            formats = [ExportFormat.CSV, ExportFormat.JSON,
                       ExportFormat.EXCEL, ExportFormat.PNG]

        results = {}
        for fmt in formats:
            try:
                path = self.export(data, fmt, prefix, config, experimental)
                results[fmt] = path
            except Exception as e:
                self._log(f"⚠ Error exportando [{fmt.value}]: {e}")

        return results

    # ── Exportadores individuales ─────────────────────────────────────────────

    def _export_csv(
        self,
        data:         WaveFrontData,
        prefix:       str,
        config:       SimulationConfig | None,
        experimental: list[ExperimentalData],
    ) -> Path:
        """Exporta métricas del frente de onda a CSV."""
        import csv

        path = self.output_dir / f"{prefix}_wave_front.csv"

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Comentarios en líneas separadas (pandas los salta con comment="#")
            f.write(f"# OpenFOAM Manager — Wave Front Data\n")
            f.write(f"# Caso: {data.config_name}\n")
            f.write(f"# Fluido: {data.fluid_name}\n")

            writer.writerow([
                "tiempo_s",
                "frente_x_m",
                "velocidad_frente_m_s",
                "area_fluido_m2",
                "volumen_fluido_m3",
            ])

            for i, t in enumerate(data.times):
                writer.writerow([
                    f"{t:.6g}",
                    f"{data.front_position[i]:.6g}",
                    f"{data.front_velocity[i]:.6g}",
                    f"{data.fluid_area[i]:.6g}",
                    f"{data.fluid_volume[i]:.6g}",
                ])

        return path

    def _export_json(
        self,
        data:         WaveFrontData,
        prefix:       str,
        config:       SimulationConfig | None,
        experimental: list[ExperimentalData],
    ) -> Path:
        """Exporta configuración + resultados completos a JSON."""
        import json

        path = self.output_dir / f"{prefix}_results.json"

        output = {
            "metadata": {
                "exporter": "OpenFOAM Manager",
                "version":  "1.0",
            },
            "simulation": config.to_dict() if config else {},
            "wave_front": data.to_dict(),
            "experimental": [
                {
                    "label":  exp.label,
                    "field":  exp.field,
                    "units":  exp.units,
                    "source": exp.source_file,
                    "times":  exp.times.tolist(),
                    "values": exp.values.tolist(),
                }
                for exp in experimental
            ],
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        return path

    def _export_excel(
        self,
        data:         WaveFrontData,
        prefix:       str,
        config:       SimulationConfig | None,
        experimental: list[ExperimentalData],
    ) -> Path:
        """Exporta a Excel con múltiples hojas."""
        import pandas as pd

        path = self.output_dir / f"{prefix}_results.xlsx"

        with pd.ExcelWriter(path, engine="openpyxl") as writer:

            # Hoja 1: Frente de onda
            df_wf = pd.DataFrame({
                "Tiempo [s]":              data.times,
                "Posición frente [m]":     data.front_position,
                "Velocidad frente [m/s]":  data.front_velocity,
                "Área fluido [m²]":        data.fluid_area,
                "Volumen fluido [m³]":     data.fluid_volume,
            })
            df_wf.to_excel(writer, sheet_name="Frente de Onda", index=False)

            # Hoja 2: Perfiles de altura (para cada tiempo disponible)
            profile_data = {}
            for t, (xs, hs) in data.height_profiles.items():
                profile_data[f"x [m]"] = xs.tolist()
                profile_data[f"h(x) t={t:.3f}s [m]"] = hs.tolist()

            if profile_data:
                df_profiles = pd.DataFrame(profile_data)
                df_profiles.to_excel(
                    writer, sheet_name="Perfiles de Altura", index=False
                )

            # Hoja 3: Datos experimentales (si los hay)
            if experimental:
                for exp in experimental:
                    sheet = exp.label[:31]  # Excel limita a 31 chars
                    df_exp = pd.DataFrame({
                        "Tiempo [s]":            exp.times,
                        f"{exp.field} [{exp.units}]": exp.values,
                    })
                    df_exp.to_excel(writer, sheet_name=sheet, index=False)

            # Hoja 4: Configuración (si disponible)
            if config:
                params = config.fluid.get_parameters()
                geo    = config.geometry
                cfg_data = {
                    "Parámetro": [
                        "Nombre caso", "Fluido", "Tiempo final [s]",
                        "Intervalo escritura [s]", "Longitud dominio [m]",
                        "Altura dominio [m]", "Celdas nx", "Celdas ny",
                        "Densidad [kg/m³]",
                    ],
                    "Valor": [
                        config.name, config.fluid.display_name,
                        config.end_time, config.write_interval,
                        geo.length, geo.height, geo.nx, geo.ny,
                        params.get("rho", ""),
                    ],
                }
                pd.DataFrame(cfg_data).to_excel(
                    writer, sheet_name="Configuración", index=False
                )

        return path

    def _export_png(
        self,
        data:         WaveFrontData,
        prefix:       str,
        config:       SimulationConfig | None,
        experimental: list[ExperimentalData],
    ) -> Path:
        """
        Exporta gráficas de matplotlib a PNG.

        Genera un panel con 4 subgráficas:
            - Posición del frente vs tiempo
            - Velocidad del frente vs tiempo
            - Área del fluido vs tiempo
            - Perfil de altura final h(x)
        """
        import matplotlib
        matplotlib.use("Agg")  # Backend sin GUI para exportación
        import matplotlib.pyplot as plt
        import matplotlib.gridspec as gridspec

        path = self.output_dir / f"{prefix}_plots.png"

        fig = plt.figure(figsize=(14, 10))
        fig.suptitle(
            f"Análisis del frente de onda — {data.config_name} ({data.fluid_name})",
            fontsize=14, fontweight="bold"
        )

        gs   = gridspec.GridSpec(2, 2, figure=fig, hspace=0.35, wspace=0.3)
        axes = [fig.add_subplot(gs[i // 2, i % 2]) for i in range(4)]

        times = np.array(data.times)
        color = "#2C5F8A"

        # Panel 1: Posición del frente
        ax = axes[0]
        ax.plot(times, data.front_position, "-o", color=color,
                linewidth=2, markersize=4, label=data.fluid_name or "Simulación")

        # Añadir datos experimentales si coinciden con el campo
        for exp in experimental:
            if exp.field == "front_position":
                ax.plot(exp.times, exp.values, "--s", color="#E85A30",
                        linewidth=1.5, markersize=4, label=exp.label, alpha=0.85)

        ax.set_xlabel("Tiempo [s]")
        ax.set_ylabel("Posición del frente [m]")
        ax.set_title("Posición del frente de onda X(t)")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

        # Panel 2: Velocidad del frente
        ax = axes[1]
        ax.plot(times, data.front_velocity, "-o", color="#1AA870",
                linewidth=2, markersize=4)
        ax.set_xlabel("Tiempo [s]")
        ax.set_ylabel("Velocidad [m/s]")
        ax.set_title("Velocidad del frente V(t)")
        ax.grid(True, alpha=0.3)
        ax.axhline(y=0, color="black", linewidth=0.8, linestyle="--")

        # Panel 3: Área del fluido
        ax = axes[2]
        ax.fill_between(times, data.fluid_area, alpha=0.3, color=color)
        ax.plot(times, data.fluid_area, "-", color=color, linewidth=2)
        ax.set_xlabel("Tiempo [s]")
        ax.set_ylabel("Área [m²]")
        ax.set_title("Área ocupada por el fluido A(t)")
        ax.grid(True, alpha=0.3)

        # Panel 4: Perfil de altura final h(x)
        ax = axes[3]
        if data.height_profiles:
            # Usar el último tiempo disponible
            last_t = max(data.height_profiles.keys())
            xs, hs = data.height_profiles[last_t]
            ax.fill_between(xs, hs, alpha=0.4, color=color)
            ax.plot(xs, hs, "-", color=color, linewidth=2,
                    label=f"t = {last_t:.2f}s")
            ax.set_xlim(0, xs.max() * 1.05)
            ax.set_ylim(0, hs.max() * 1.2 if hs.max() > 0 else 0.1)
        ax.set_xlabel("Posición x [m]")
        ax.set_ylabel("Altura h(x) [m]")
        ax.set_title("Perfil de altura final h(x)")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)

        return path

    def _export_vtk(
        self,
        data:         WaveFrontData,
        prefix:       str,
        config:       SimulationConfig | None,
        experimental: list[ExperimentalData],
    ) -> Path:
        """
        Exporta en formato VTK Legacy para ParaView.

        Genera un archivo de línea (polydata) con la trayectoria del frente.
        """
        path = self.output_dir / f"{prefix}_wave_front.vtk"

        n_pts = len(data.times)
        with open(path, "w", encoding="utf-8") as f:
            f.write("# vtk DataFile Version 3.0\n")
            f.write(f"Wave Front — {data.config_name}\n")
            f.write("ASCII\n")
            f.write("DATASET POLYDATA\n\n")

            # Puntos: (x, y=0, z=t) — trayectoria en espacio x-t
            f.write(f"POINTS {n_pts} float\n")
            for i, t in enumerate(data.times):
                x = data.front_position[i]
                f.write(f"{x:.6g} 0.0 {t:.6g}\n")

            # Línea conectando todos los puntos
            f.write(f"\nLINES 1 {n_pts + 1}\n")
            f.write(f"{n_pts} " + " ".join(str(i) for i in range(n_pts)) + "\n")

            # Datos en puntos
            f.write(f"\nPOINT_DATA {n_pts}\n")
            f.write("SCALARS velocity float 1\n")
            f.write("LOOKUP_TABLE default\n")
            for v in data.front_velocity:
                f.write(f"{v:.6g}\n")

            f.write("\nSCALARS fluid_area float 1\n")
            f.write("LOOKUP_TABLE default\n")
            for a in data.fluid_area:
                f.write(f"{a:.6g}\n")

        return path

    def _export_hdf5(
        self,
        data:         WaveFrontData,
        prefix:       str,
        config:       SimulationConfig | None,
        experimental: list[ExperimentalData],
    ) -> Path:
        """Exporta a HDF5 (formato científico estructurado)."""
        import h5py

        path = self.output_dir / f"{prefix}_results.h5"

        with h5py.File(path, "w") as f:

            # Metadatos
            f.attrs["config_name"] = data.config_name
            f.attrs["fluid_name"]  = data.fluid_name
            f.attrs["exporter"]    = "OpenFOAM Manager"

            # Grupo: frente de onda
            wf = f.create_group("wave_front")
            wf.create_dataset("times",          data=np.array(data.times))
            wf.create_dataset("front_position",  data=np.array(data.front_position))
            wf.create_dataset("front_velocity",  data=np.array(data.front_velocity))
            wf.create_dataset("fluid_area",      data=np.array(data.fluid_area))
            wf.create_dataset("fluid_volume",    data=np.array(data.fluid_volume))
            wf["times"].attrs["units"]           = "s"
            wf["front_position"].attrs["units"]  = "m"
            wf["front_velocity"].attrs["units"]  = "m/s"
            wf["fluid_area"].attrs["units"]      = "m2"
            wf["fluid_volume"].attrs["units"]    = "m3"

            # Grupo: perfiles de altura
            if data.height_profiles:
                hp = f.create_group("height_profiles")
                for t, (xs, hs) in data.height_profiles.items():
                    grp = hp.create_group(f"t_{t:.4f}")
                    grp.create_dataset("x", data=xs)
                    grp.create_dataset("h", data=hs)
                    grp.attrs["time"] = t

            # Grupo: configuración
            if config:
                cfg = f.create_group("configuration")
                params = config.fluid.get_parameters()
                for key, val in params.items():
                    try:
                        cfg.attrs[key] = val
                    except TypeError:
                        cfg.attrs[key] = str(val)

            # Grupo: datos experimentales
            if experimental:
                exp_grp = f.create_group("experimental")
                for i, exp in enumerate(experimental):
                    eg = exp_grp.create_group(f"dataset_{i:02d}")
                    eg.create_dataset("times",  data=exp.times)
                    eg.create_dataset("values", data=exp.values)
                    eg.attrs["label"]  = exp.label
                    eg.attrs["field"]  = exp.field
                    eg.attrs["units"]  = exp.units
                    eg.attrs["source"] = exp.source_file

        return path

    def __repr__(self) -> str:
        return f"Exporter(output_dir='{self.output_dir}')"
