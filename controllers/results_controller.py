"""
Controlador de resultados y visualización.

Gestiona:
    - Carga y análisis de resultados de simulación (WaveFrontData)
    - Comparación de N simulaciones entre sí
    - Carga de datos experimentales para validación
    - Exportación en múltiples formatos
    - Preparación de datos para gráficas de matplotlib

Comunicación con la UI exclusivamente via callbacks Python puros.

Ejemplo de uso:
    ctrl = ResultsController(
        on_data_ready=lambda data: results_tab.show(data),
        on_plot_ready=lambda fig_data: plot_widget.render(fig_data),
        on_log=log_widget.append,
    )
    ctrl.load_from_config(config)
    ctrl.compare([config_lodo, config_agua])
    ctrl.export(ExportFormat.EXCEL, prefix='comparacion')
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

from core.postprocessing import WaveFrontData
from core.simulation import SimulationConfig, GeometryConfig
from services.data_extractor import DataExtractor, ExperimentalData
from services.exporter import Exporter, ExportFormat


@dataclass
class PlotConfig:
    """Configuración para las gráficas de matplotlib."""
    show_grid:       bool  = True
    show_legend:     bool  = True
    line_width:      float = 2.0
    marker_size:     float = 4.0
    fig_width:       float = 12.0
    fig_height:      float = 8.0
    dpi:             int   = 100
    color_sim:       str   = "#2C5F8A"   # Azul OpenFOAM
    color_exp:       str   = "#E85A30"   # Naranja datos reales
    color_secondary: str   = "#1AA870"   # Verde segunda simulación


@dataclass
class ComparisonResult:
    """
    Resultado de comparar N simulaciones y opcionalmente datos experimentales.

    Attributes:
        simulations:   Lista de WaveFrontData de cada simulación.
        experimental:  Lista de datos experimentales cargados.
        labels:        Etiquetas para cada dataset (para las gráficas).
        metrics:       Dict con métricas de comparación {label → {rmse, mae, r2}}.
    """
    simulations:  list[WaveFrontData]
    experimental: list[ExperimentalData]
    labels:       list[str]
    metrics:      dict[str, dict] = field(default_factory=dict)

    @property
    def n_simulations(self) -> int:
        return len(self.simulations)

    @property
    def n_experimental(self) -> int:
        return len(self.experimental)

    @property
    def has_experimental(self) -> bool:
        return len(self.experimental) > 0


class ResultsController:
    """
    Gestiona la carga, análisis, visualización y exportación de resultados.

    Callbacks disponibles:
        on_data_ready(data: WaveFrontData)
            Datos de una simulación cargados y procesados.

        on_comparison_ready(result: ComparisonResult)
            Comparación de N simulaciones lista para visualizar.

        on_plot_data_ready(plot_data: dict)
            Datos estructurados para construir gráficas matplotlib en la UI.
            Evita pasar objetos Figure (no serializable entre hilos).

        on_export_done(paths: dict)
            Exportación completada. Dict {formato → path}.

        on_log(msg: str)
            Mensajes de log.

        on_error(msg: str)
            Error durante el procesamiento.
    """

    # Paleta de colores para múltiples simulaciones
    _COLORS = [
        "#2C5F8A",  # Azul
        "#E85A30",  # Naranja
        "#1AA870",  # Verde
        "#9B59B6",  # Púrpura
        "#F39C12",  # Amarillo
        "#1ABC9C",  # Turquesa
    ]

    def __init__(
        self,
        on_data_ready:        Callable[[WaveFrontData], None]        | None = None,
        on_comparison_ready:  Callable[[ComparisonResult], None]     | None = None,
        on_plot_data_ready:   Callable[[dict], None]                 | None = None,
        on_export_done:       Callable[[dict], None]                 | None = None,
        on_log:               Callable[[str], None]                  | None = None,
        on_error:             Callable[[str], None]                  | None = None,
    ) -> None:

        self._on_data_ready       = on_data_ready       or (lambda d: None)
        self._on_comparison_ready = on_comparison_ready or (lambda r: None)
        self._on_plot_data_ready  = on_plot_data_ready  or (lambda d: None)
        self._on_export_done      = on_export_done      or (lambda p: None)
        self._on_log              = on_log              or (lambda m: None)
        self._on_error            = on_error            or (lambda m: None)

        # Estado interno
        self._loaded_data:    list[WaveFrontData]    = []
        self._experimental:   list[ExperimentalData] = []
        self._last_config:    SimulationConfig | None = None
        self._plot_config:    PlotConfig              = PlotConfig()
        self._extractor:      DataExtractor           = DataExtractor(
            log_callback=self._on_log
        )

    # ── Carga de resultados de simulación ─────────────────────────────────────

    def load_from_config(
        self,
        config:    SimulationConfig,
        threshold: float = 0.5,
        async_:    bool  = True,
    ) -> WaveFrontData | None:
        """
        Carga y procesa los resultados de una simulación.

        Args:
            config:    Configuración de la simulación (incluye case_dir y geometry).
            threshold: Umbral de alpha para la interfaz (default 0.5).
            async_:    Si True, carga en hilo secundario (para UI).
                       Si False, carga sincrónicamente (para testing).

        Returns:
            WaveFrontData si async_=False, None si async_=True.
        """
        self._last_config = config

        if async_:
            threading.Thread(
                target = self._load_worker,
                args   = (config, threshold),
                daemon = True,
                name   = f"ResultsLoader-{config.name}",
            ).start()
            return None
        else:
            return self._load_worker(config, threshold)

    def load_from_dir(
        self,
        case_dir:   str | Path,
        geometry:   GeometryConfig,
        field_name: str   = "alpha.lodo",
        label:      str   = "",
        async_:     bool  = True,
    ) -> WaveFrontData | None:
        """
        Carga resultados directamente desde un directorio de caso.

        Útil cuando se tienen resultados pero no el SimulationConfig original.

        Args:
            case_dir:   Directorio del caso OpenFOAM.
            geometry:   Geometría del dominio (para reconstruir coordenadas).
            field_name: Nombre del campo alpha.
            label:      Etiqueta para identificar este dataset.
            async_:     Si True, carga asíncronamente.
        """
        if async_:
            threading.Thread(
                target = self._load_dir_worker,
                args   = (case_dir, geometry, field_name, label),
                daemon = True,
            ).start()
            return None
        else:
            return self._load_dir_worker(case_dir, geometry, field_name, label)

    def _load_worker(
        self,
        config:    SimulationConfig,
        threshold: float,
    ) -> WaveFrontData | None:
        """Worker para carga asíncrona desde config."""
        try:
            self._on_log(f"\nCargando resultados: {config.name}...")
            data = self._extractor.extract_from_config(config, threshold)

            # Añadir a la lista de datos cargados
            self._loaded_data.append(data)

            self._on_log(f"✓ {data.n_time_steps} pasos de tiempo procesados.")
            self._on_data_ready(data)

            # Preparar y emitir datos de gráfica
            plot_data = self._build_single_plot_data(data)
            self._on_plot_data_ready(plot_data)

            return data

        except FileNotFoundError as e:
            self._on_error(
                f"No se encontró el directorio del caso.\n"
                f"Verifique que la simulación se ejecutó correctamente.\n\n{e}"
            )
        except RuntimeError as e:
            self._on_error(f"Sin resultados disponibles:\n{e}")
        except Exception as e:
            import traceback
            self._on_log(f"\n✗ Error al cargar resultados:\n{traceback.format_exc()}")
            self._on_error(f"Error al cargar resultados: {e}")

        return None

    def _load_dir_worker(
        self,
        case_dir:   str | Path,
        geometry:   GeometryConfig,
        field_name: str,
        label:      str,
    ) -> WaveFrontData | None:
        """Worker para carga asíncrona desde directorio."""
        try:
            data = self._extractor.extract_from_dir(
                case_dir   = case_dir,
                geometry   = geometry,
                field_name = field_name,
                config_name = label,
            )
            self._loaded_data.append(data)
            self._on_data_ready(data)
            plot_data = self._build_single_plot_data(data)
            self._on_plot_data_ready(plot_data)
            return data
        except Exception as e:
            self._on_error(f"Error cargando desde directorio: {e}")
        return None

    # ── Carga de datos experimentales ─────────────────────────────────────────

    def load_experimental_csv(
        self,
        file_path:  str | Path,
        time_col:   str | int = 0,
        value_col:  str | int = 1,
        label:      str | None = None,
        field:      str = "front_position",
        units:      str = "m",
        skip_rows:  int = 0,
        delimiter:  str = ",",
    ) -> ExperimentalData | None:
        """
        Carga datos experimentales desde CSV y los añade al contexto de comparación.

        Args:
            file_path:  Ruta al archivo CSV.
            time_col:   Columna de tiempo (índice o nombre).
            value_col:  Columna de valores (índice o nombre).
            label:      Etiqueta para la gráfica.
            field:      Tipo de dato ('front_position', 'fluid_area', etc.).
            units:      Unidades del campo.
            skip_rows:  Filas a omitir al inicio.
            delimiter:  Separador del CSV.

        Returns:
            ExperimentalData si fue exitoso, None si hubo error.
        """
        try:
            exp_data = self._extractor.load_experimental_csv(
                file_path = file_path,
                time_col  = time_col,
                value_col = value_col,
                label     = label,
                field     = field,
                units     = units,
                skip_rows = skip_rows,
                delimiter = delimiter,
            )
            self._experimental.append(exp_data)
            self._on_log(f"✓ Datos experimentales cargados: {exp_data.label}")
            return exp_data

        except Exception as e:
            self._on_error(f"Error cargando CSV experimental: {e}")
            return None

    def load_experimental_excel(
        self,
        file_path:  str | Path,
        sheet_name: str | int = 0,
        time_col:   str | int = 0,
        value_col:  str | int = 1,
        label:      str | None = None,
        field:      str = "front_position",
        units:      str = "m",
        skip_rows:  int = 0,
    ) -> ExperimentalData | None:
        """Carga datos experimentales desde Excel."""
        try:
            exp_data = self._extractor.load_experimental_excel(
                file_path  = file_path,
                sheet_name = sheet_name,
                time_col   = time_col,
                value_col  = value_col,
                label      = label,
                field      = field,
                units      = units,
                skip_rows  = skip_rows,
            )
            self._experimental.append(exp_data)
            self._on_log(f"✓ Datos Excel cargados: {exp_data.label}")
            return exp_data

        except Exception as e:
            self._on_error(f"Error cargando Excel experimental: {e}")
            return None

    # ── Comparación ───────────────────────────────────────────────────────────

    def compare(
        self,
        sim_data:     list[WaveFrontData] | None = None,
        experimental: list[ExperimentalData] | None = None,
        field:        str = "front_position",
    ) -> ComparisonResult:
        """
        Compara N simulaciones y/o datos experimentales.

        Si sim_data y experimental son None, usa los datos ya cargados
        en el controlador (self._loaded_data y self._experimental).

        Args:
            sim_data:     Lista de WaveFrontData a comparar.
                          Si None, usa los datos cargados previamente.
            experimental: Lista de datos experimentales adicionales.
            field:        Métrica a comparar ('front_position', 'fluid_area', etc.).

        Returns:
            ComparisonResult con métricas y datos listos para graficar.
        """
        sims = sim_data or self._loaded_data
        exps = experimental or self._experimental

        if not sims and not exps:
            self._on_error(
                "No hay datos para comparar. "
                "Cargue al menos una simulación o datos experimentales."
            )
            return ComparisonResult([], [], [])

        # Construir etiquetas
        labels = []
        for d in sims:
            labels.append(d.fluid_name or d.config_name or f"Sim {len(labels)+1}")
        for e in exps:
            labels.append(e.label or f"Exp {len(labels)-len(sims)+1}")

        # Calcular métricas de comparación (sim vs cada dataset experimental)
        metrics = {}
        for sim in sims:
            for exp in exps:
                if exp.field == field:
                    key = f"{sim.config_name} vs {exp.label}"
                    metrics[key] = self._extractor.compare_with_experimental(sim, exp)

        result = ComparisonResult(
            simulations  = sims,
            experimental = exps,
            labels       = labels,
            metrics      = metrics,
        )

        # Preparar datos de gráfica
        plot_data = self._build_comparison_plot_data(result, field)
        self._on_plot_data_ready(plot_data)
        self._on_comparison_ready(result)

        return result

    # ── Exportación ───────────────────────────────────────────────────────────

    def export(
        self,
        format:      ExportFormat,
        prefix:      str         = "simulation",
        output_dir:  str | None  = None,
        data:        WaveFrontData | None = None,
        config:      SimulationConfig | None = None,
        async_:      bool        = False,
    ) -> dict | None:
        """
        Exporta los datos al formato especificado.

        Args:
            format:     Formato de exportación.
            prefix:     Prefijo del nombre del archivo.
            output_dir: Directorio de salida. Si None, usa el directorio del caso.
            data:       Datos a exportar. Si None, usa los últimos cargados.
            config:     Configuración de la simulación (para metadatos).
            async_:     Si True, exporta en hilo secundario.

        Returns:
            Dict {formato → path} si async_=False, None si async_=True.
        """
        export_data = data or (self._loaded_data[-1] if self._loaded_data else None)

        if export_data is None:
            self._on_error("No hay datos para exportar. Cargue una simulación primero.")
            return None

        # Determinar directorio de salida
        if output_dir is None:
            cfg = config or self._last_config
            if cfg:
                output_dir = str(cfg.case_dir / "resultados")
            else:
                output_dir = "."

        if async_:
            threading.Thread(
                target = self._export_worker,
                args   = (export_data, format, prefix, output_dir, config),
                daemon = True,
            ).start()
            return None
        else:
            return self._export_worker(export_data, format, prefix, output_dir, config)

    def export_all(
        self,
        prefix:     str         = "simulation",
        output_dir: str | None  = None,
        data:       WaveFrontData | None = None,
        config:     SimulationConfig | None = None,
        formats:    list[ExportFormat] | None = None,
    ) -> dict | None:
        """Exporta en todos los formatos especificados."""
        export_data = data or (self._loaded_data[-1] if self._loaded_data else None)
        if export_data is None:
            self._on_error("No hay datos para exportar.")
            return None

        if output_dir is None:
            cfg = config or self._last_config
            output_dir = str(cfg.case_dir / "resultados") if cfg else "."

        formats = formats or [
            ExportFormat.CSV, ExportFormat.JSON,
            ExportFormat.EXCEL, ExportFormat.PNG,
        ]

        threading.Thread(
            target = self._export_all_worker,
            args   = (export_data, prefix, output_dir, config, formats),
            daemon = True,
        ).start()

    def _export_worker(
        self,
        data:       WaveFrontData,
        format:     ExportFormat,
        prefix:     str,
        output_dir: str,
        config:     SimulationConfig | None,
    ) -> dict:
        try:
            exporter = Exporter(output_dir=output_dir, log_callback=self._on_log)
            path = exporter.export(data, format, prefix, config, self._experimental)
            result = {format: path}
            self._on_export_done(result)
            return result
        except Exception as e:
            self._on_error(f"Error exportando [{format.value}]: {e}")
            return {}

    def _export_all_worker(
        self,
        data:       WaveFrontData,
        prefix:     str,
        output_dir: str,
        config:     SimulationConfig | None,
        formats:    list[ExportFormat],
    ) -> None:
        try:
            exporter = Exporter(output_dir=output_dir, log_callback=self._on_log)
            paths = exporter.export_all(
                data         = data,
                prefix       = prefix,
                config       = config,
                experimental = self._experimental,
                formats      = formats,
            )
            self._on_export_done(paths)
        except Exception as e:
            self._on_error(f"Error en exportación múltiple: {e}")

    # ── Preparación de datos para gráficas ───────────────────────────────────

    def _build_single_plot_data(self, data: WaveFrontData) -> dict:
        """
        Construye los datos para graficar una simulación.

        Para simulaciones 3D (data.is_3d=True) incluye paneles adicionales:
            - plan_view:         vista en planta alpha(x,z) — cámara superior
            - transversal:       perfil h(z) — simetría transversal
            - fluid_volume:      volumen 3D real vs tiempo
            - height_all_times:  evolución temporal del perfil lateral h(x,t)
        """
        # ── Perfil lateral final h(x) ─────────────────────────────────────
        final_profile = None
        if data.height_profiles:
            last_t = max(data.height_profiles.keys())
            xs, hs = data.height_profiles[last_t]
            final_profile = {
                "x":     xs.tolist(),
                "y":     hs.tolist(),
                "time":  last_t,
                "label": f"t = {last_t:.2f} s",
            }

        # ── Perfiles laterales en múltiples tiempos ───────────────────────
        lateral_series = []
        n_times = len(data.height_profiles)
        cmap_colors = ["#B5D4F4", "#6AAAE0", "#2C5F8A",
                       "#1A3D5C", "#0D2030"]
        for i, (t, (xs, hs)) in enumerate(
            sorted(data.height_profiles.items())
        ):
            color = cmap_colors[min(i, len(cmap_colors)-1)]
            lateral_series.append({
                "x": xs.tolist(), "y": hs.tolist(),
                "label": f"t={t:.2f}s", "color": color,
                "style": "-", "alpha": 0.4 + 0.6 * (i / max(n_times-1, 1)),
            })

        # ── Vista en planta (3D) ──────────────────────────────────────────
        plan_panel = None
        if data.is_3d and data.plan_view_profiles:
            last_t_plan = max(data.plan_view_profiles.keys())
            plan_arr    = data.plan_view_profiles[last_t_plan]
            gi          = data.geometry_info
            plan_panel  = {
                "array":  plan_arr.astype(float).tolist(),
                "x_edges": [i * gi["dx"] for i in range(gi["nx"] + 1)],
                "z_edges": [k * gi["dz"] for k in range(gi["nz"] + 1)],
                "time":  last_t_plan,
                "label": f"t = {last_t_plan:.2f} s",
                "domain_length": gi["length"],
                "domain_width":  gi["width"],
            }

        # ── Perfil transversal h(z) (3D) ──────────────────────────────────
        transversal_series = []
        if data.is_3d and data.transversal_profiles:
            gi = data.geometry_info
            zs = [(k + 0.5) * gi["dz"] for k in range(gi["nz"])]
            for i, (t, h_z) in enumerate(
                sorted(data.transversal_profiles.items())
            ):
                color = cmap_colors[min(i, len(cmap_colors)-1)]
                transversal_series.append({
                    "x": zs, "y": h_z.tolist(),
                    "label": f"t={t:.2f}s", "color": color,
                    "style": "-o",
                })

        cfg = self._plot_config
        return {
            "type":   "single",
            "is_3d":  data.is_3d,
            "title":  f"{data.config_name} — {data.fluid_name}",
            "panels": {
                "front_position": {
                    "title":  "Posición del frente X(t)",
                    "xlabel": "Tiempo [s]",
                    "ylabel": "Posición [m]",
                    "series": [{
                        "x": data.times, "y": data.front_position,
                        "label": data.fluid_name or data.config_name,
                        "color": cfg.color_sim, "style": "-o",
                    }],
                },
                "front_velocity": {
                    "title":  "Velocidad del frente V(t)",
                    "xlabel": "Tiempo [s]",
                    "ylabel": "Velocidad [m/s]",
                    "series": [{
                        "x": data.times, "y": data.front_velocity,
                        "label": "V(t)", "color": cfg.color_secondary,
                        "style": "-o",
                    }],
                },
                "fluid_volume": {
                    "title":  "Volumen del fluido Vol(t)",
                    "xlabel": "Tiempo [s]",
                    "ylabel": "Volumen [m³]",
                    "series": [{
                        "x": data.times, "y": data.fluid_volume,
                        "label": "Vol(t)", "color": cfg.color_sim,
                        "style": "-", "fill": True,
                    }],
                },
                "height_profile": {
                    "title":  "Perfil de altura lateral h(x)",
                    "xlabel": "Posición x [m]",
                    "ylabel": "Altura h [m]",
                    "series": lateral_series,
                    "show_last_bold": True,
                },
                # ── Paneles 3D ────────────────────────────────────────────
                "plan_view": {
                    "title":  "Vista en planta — cámara superior",
                    "type":   "heatmap",
                    "data":   plan_panel,
                    "is_3d":  data.is_3d,
                },
                "transversal": {
                    "title":  "Perfil transversal h(z)",
                    "xlabel": "Posición z [m]",
                    "ylabel": "Altura h [m]",
                    "series": transversal_series,
                    "is_3d":  data.is_3d,
                },
            },
            "summary": {
                "final_extent":  data.final_extent,
                "max_velocity":  data.max_front_velocity,
                "final_area":    data.final_area,
                "final_volume":  data.final_volume,
                "n_time_steps":  data.n_time_steps,
                "is_3d":         data.is_3d,
            },
            "plot_config": {
                "show_grid":   cfg.show_grid,
                "show_legend": cfg.show_legend,
                "line_width":  cfg.line_width,
                "marker_size": cfg.marker_size,
            },
        }

    def build_plan_view_data(
        self,
        data: WaveFrontData,
        time: float | None = None,
    ) -> dict | None:
        """
        Construye datos para renderizar la vista en planta alpha(x,z).

        Para comparar con cámara superior del experimento.

        Args:
            data: WaveFrontData con plan_view_profiles.
            time: Tiempo deseado. Si None, usa el último disponible.

        Returns:
            Dict con array 2D, ejes x/z y metadatos.
            None si no hay datos 3D.
        """
        if not data.is_3d or not data.plan_view_profiles:
            return None

        gi = data.geometry_info
        if time is None:
            t = max(data.plan_view_profiles.keys())
        else:
            t = min(data.plan_view_profiles, key=lambda tt: abs(tt - time))

        plan_arr = data.plan_view_profiles[t]
        return {
            "array":         plan_arr.astype(float).tolist(),
            "x_centers":     [(i + 0.5) * gi["dx"] for i in range(gi["nx"])],
            "z_centers":     [(k + 0.5) * gi["dz"] for k in range(gi["nz"])],
            "x_edges":       [i * gi["dx"] for i in range(gi["nx"] + 1)],
            "z_edges":       [k * gi["dz"] for k in range(gi["nz"] + 1)],
            "domain_length": gi["length"],
            "domain_width":  gi["width"],
            "time":          t,
            "config_name":   data.config_name,
            "fluid_name":    data.fluid_name,
        }

    def build_transversal_data(
        self,
        data: WaveFrontData,
        time: float | None = None,
    ) -> dict | None:
        """
        Construye datos para el perfil transversal h(z).

        Para verificar simetría lateral y comparar con sensores en z.

        Args:
            data: WaveFrontData con transversal_profiles.
            time: Tiempo deseado. Si None, usa el último.

        Returns:
            Dict con perfil z-h y simetría calculada.
            None si no hay datos 3D.
        """
        if not data.is_3d or not data.transversal_profiles:
            return None

        gi = data.geometry_info
        if time is None:
            t = max(data.transversal_profiles.keys())
        else:
            t = min(data.transversal_profiles, key=lambda tt: abs(tt - time))

        h_z     = np.array(data.transversal_profiles[t])
        z_cents = np.array([(k + 0.5) * gi["dz"] for k in range(gi["nz"])])

        # Índice de simetría: qué tan simétrico es h(z) respecto al centro
        h_flip  = h_z[::-1]
        h_mean  = h_z.mean()
        sym_idx = float(1.0 - np.abs(h_z - h_flip).mean() / (h_mean + 1e-9))

        return {
            "z":            z_cents.tolist(),
            "h":            h_z.tolist(),
            "domain_width": gi["width"],
            "time":         t,
            "symmetry_index": sym_idx,   # 1.0 = perfectamente simétrico
            "h_mean":       float(h_mean),
            "h_std":        float(h_z.std()),
            "config_name":  data.config_name,
        }

    def _build_comparison_plot_data(
        self,
        result: ComparisonResult,
        field:  str = "front_position",
    ) -> dict:
        """
        Construye datos para graficar N simulaciones superpuestas.

        Returns:
            Dict con series de datos de todas las simulaciones y datos experimentales.
        """
        series = []

        # Series de simulaciones
        for i, sim in enumerate(result.simulations):
            color = self._COLORS[i % len(self._COLORS)]
            label = result.labels[i] if i < len(result.labels) else f"Sim {i+1}"

            field_data = {
                "front_position": sim.front_position,
                "front_velocity": sim.front_velocity,
                "fluid_area":     sim.fluid_area,
                "fluid_volume":   sim.fluid_volume,
            }.get(field, sim.front_position)

            series.append({
                "x":      sim.times,
                "y":      field_data,
                "label":  label,
                "color":  color,
                "style":  "-o",
                "type":   "simulation",
            })

        # Series de datos experimentales
        n_sims = len(result.simulations)
        for i, exp in enumerate(result.experimental):
            color = self._COLORS[(n_sims + i) % len(self._COLORS)]
            label = result.labels[n_sims + i] if (n_sims + i) < len(result.labels) \
                    else exp.label

            if exp.field == field:
                series.append({
                    "x":      exp.times.tolist(),
                    "y":      exp.values.tolist(),
                    "label":  label,
                    "color":  color,
                    "style":  "--s",
                    "type":   "experimental",
                })

        # Etiquetas de ejes según el campo
        axis_labels = {
            "front_position": ("Tiempo [s]", "Posición del frente [m]"),
            "front_velocity": ("Tiempo [s]", "Velocidad [m/s]"),
            "fluid_area":     ("Tiempo [s]", "Área [m²]"),
            "fluid_volume":   ("Tiempo [s]", "Volumen [m³]"),
        }
        xlabel, ylabel = axis_labels.get(field, ("Tiempo [s]", "Valor"))

        # Construir tabla de métricas
        metrics_rows = []
        for key, m in result.metrics.items():
            metrics_rows.append({
                "comparison": key,
                "rmse":  m.get("rmse", 0),
                "mae":   m.get("mae", 0),
                "r2":    m.get("r2", 0),
                "n_pts": m.get("n_points", 0),
            })

        return {
            "type":   "comparison",
            "title":  f"Comparación — {field.replace('_', ' ').title()}",
            "xlabel": xlabel,
            "ylabel": ylabel,
            "field":  field,
            "series": series,
            "metrics": metrics_rows,
            "plot_config": {
                "show_grid":   self._plot_config.show_grid,
                "show_legend": self._plot_config.show_legend,
                "line_width":  self._plot_config.line_width,
                "marker_size": self._plot_config.marker_size,
            },
        }

    # ── Gestión del estado ────────────────────────────────────────────────────

    def clear_data(self) -> None:
        """Limpia todos los datos cargados."""
        self._loaded_data.clear()
        self._experimental.clear()
        self._on_log("Datos limpiados.")

    def remove_simulation(self, index: int) -> bool:
        """Elimina una simulación cargada por índice."""
        if 0 <= index < len(self._loaded_data):
            removed = self._loaded_data.pop(index)
            self._on_log(f"Eliminado: {removed.config_name}")
            return True
        return False

    def remove_experimental(self, index: int) -> bool:
        """Elimina un dataset experimental por índice."""
        if 0 <= index < len(self._experimental):
            removed = self._experimental.pop(index)
            self._on_log(f"Eliminado: {removed.label}")
            return True
        return False

    @property
    def loaded_simulations(self) -> list[WaveFrontData]:
        """Lista de simulaciones actualmente cargadas."""
        return list(self._loaded_data)

    @property
    def loaded_experimental(self) -> list[ExperimentalData]:
        """Lista de datos experimentales actualmente cargados."""
        return list(self._experimental)

    @property
    def plot_config(self) -> PlotConfig:
        """Configuración visual de las gráficas."""
        return self._plot_config

    @plot_config.setter
    def plot_config(self, config: PlotConfig) -> None:
        self._plot_config = config

    def __repr__(self) -> str:
        return (
            f"ResultsController("
            f"simulations={len(self._loaded_data)}, "
            f"experimental={len(self._experimental)})"
        )
