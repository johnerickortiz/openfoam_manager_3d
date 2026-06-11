"""
Servicio de extracción de datos post-simulación.

Coordina FoamReader y WaveFrontExtractor para producir WaveFrontData
completo desde el directorio de un caso OpenFOAM.

También gestiona la carga de datos experimentales (CSV/Excel)
para comparación con los resultados de simulación.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

from core.postprocessing import FoamReader, WaveFrontExtractor, WaveFrontData
from core.simulation import GeometryConfig, SimulationConfig


@dataclass
class ExperimentalData:
    """
    Datos experimentales cargados desde CSV o Excel.

    Atributos:
        source_file: Ruta al archivo de origen.
        label:       Etiqueta para mostrar en las gráficas.
        times:       Array de tiempos [s].
        values:      Array de valores (posición, velocidad, etc.).
        field:       Tipo de dato ('front_position', 'fluid_area', etc.).
        units:       Unidades del campo.
    """
    source_file: str
    label:       str
    times:       np.ndarray
    values:      np.ndarray
    field:       str  = "front_position"
    units:       str  = "m"


class DataExtractor:
    """
    Extrae métricas post-simulación y carga datos experimentales.

    Args:
        log_callback: Función opcional para mensajes de progreso.

    Ejemplo:
        extractor = DataExtractor(log_callback=print)
        data = extractor.extract_from_config(config)
        print(f"Frente final: {data.final_extent:.4f} m")
        print(f"Tiempos: {data.times}")
    """

    def __init__(
        self,
        log_callback: Callable[[str], None] | None = None,
    ) -> None:
        self._log = log_callback or (lambda msg: None)

    # ── Extracción de resultados de simulación ────────────────────────────────

    def extract_from_config(
        self,
        config:    SimulationConfig,
        threshold: float = 0.5,
    ) -> WaveFrontData:
        """
        Extrae métricas del frente de onda desde el directorio del caso.

        Args:
            config:    Configuración de la simulación (incluye case_dir y geometry).
            threshold: Umbral de alpha para definir la interfaz (default: 0.5).

        Returns:
            WaveFrontData con todas las métricas calculadas.

        Raises:
            FileNotFoundError: Si el directorio del caso no existe.
            RuntimeError: Si no se encuentran resultados.
        """
        case_dir = config.case_dir

        if not case_dir.exists():
            raise FileNotFoundError(
                f"Directorio del caso no encontrado: {case_dir}"
            )

        return self.extract_from_dir(
            case_dir    = case_dir,
            geometry    = config.geometry,
            field_name  = config.alpha_field_name,
            threshold   = threshold,
            config_name = config.name,
            fluid_name  = config.fluid.display_name,
        )

    def extract_from_dir(
        self,
        case_dir:    Path | str,
        geometry:    GeometryConfig,
        field_name:  str   = "alpha.lodo",
        threshold:   float = 0.5,
        config_name: str   = "",
        fluid_name:  str   = "",
    ) -> WaveFrontData:
        """
        Extrae métricas 3D directamente desde un directorio de caso OpenFOAM.

        Args:
            case_dir:    Directorio del caso OpenFOAM.
            geometry:    Configuración geométrica 3D del dominio.
            field_name:  Nombre del campo alpha.
            threshold:   Umbral de la interfaz (default 0.5).
            config_name: Nombre del caso (metadatos).
            fluid_name:  Nombre del fluido (metadatos).

        Returns:
            WaveFrontData con métricas 3D (frente, perfiles, vista en planta,
            perfil transversal, volumen real).
        """
        case_dir = Path(case_dir)
        self._log(f"Extrayendo datos 3D de: {case_dir.name}")
        self._log(f"  Malla: {geometry.nx}×{geometry.ny}×{geometry.nz} = "
                  f"{geometry.cell_count:,} celdas")

        reader = FoamReader(case_dir)
        info   = reader.case_info()

        self._log(f"  Pasos de tiempo: {info['time_steps']}")
        if info['t_start'] is not None:
            self._log(f"  t: [{info['t_start']:.3f}s → {info['t_end']:.3f}s]")

        if info["time_steps"] == 0:
            raise RuntimeError(
                f"Sin resultados en {case_dir}. "
                "Verifique que la simulación corrió correctamente."
            )

        alpha_series = reader.read_all_alpha(field_name)
        self._log(f"  Campos alpha leídos: {len(alpha_series)}")

        extractor = WaveFrontExtractor(geometry=geometry, threshold=threshold)
        data      = extractor.extract_from_series(
            alpha_series = alpha_series,
            config_name  = config_name,
            fluid_name   = fluid_name,
        )

        self._log(f"  Frente final: {data.final_extent:.4f} m")
        self._log(f"  V_max:        {data.max_front_velocity:.4f} m/s")
        self._log(f"  Vol. final:   {data.final_volume:.6f} m³")
        if data.is_3d:
            self._log(f"  Vista en planta: {len(data.plan_view_profiles)} frames")
            self._log(f"  Perfiles transv: {len(data.transversal_profiles)} frames")

        return data

    # ── Carga de datos experimentales ─────────────────────────────────────────

    def load_experimental_csv(
        self,
        file_path:    str | Path,
        time_col:     str | int = 0,
        value_col:    str | int = 1,
        label:        str | None = None,
        field:        str = "front_position",
        units:        str = "m",
        skip_rows:    int = 0,
        delimiter:    str = ",",
    ) -> ExperimentalData:
        """
        Carga datos experimentales desde un archivo CSV.

        Formato esperado del CSV:
            tiempo_1, valor_1
            tiempo_2, valor_2
            ...

        Args:
            file_path:  Ruta al archivo CSV.
            time_col:   Índice o nombre de la columna de tiempo.
            value_col:  Índice o nombre de la columna de valores.
            label:      Etiqueta para la gráfica. Si None, usa el nombre del archivo.
            field:      Tipo de dato ('front_position', 'fluid_area', etc.).
            units:      Unidades del campo.
            skip_rows:  Filas a omitir al inicio (encabezados).
            delimiter:  Separador de columnas.

        Returns:
            ExperimentalData listo para comparar con simulaciones.

        Raises:
            FileNotFoundError: Si el archivo no existe.
            ValueError: Si las columnas especificadas no se encuentran.
        """
        import pandas as pd

        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

        self._log(f"Cargando datos experimentales: {file_path.name}")

        try:
            df = pd.read_csv(
                file_path,
                skiprows  = skip_rows,
                comment   = "#",      # Salta líneas que empiezan con # (nuestros comentarios)
                delimiter = delimiter,
                header    = 0,        # Primera fila no-comentario = cabecera
            )
        except Exception as e:
            raise ValueError(f"Error al leer CSV: {e}")

        # Auto-mapear columnas si el CSV fue generado por esta aplicación
        our_cols = {"tiempo_s", "frente_x_m", "velocidad_frente_m_s",
                    "area_fluido_m2", "volumen_fluido_m3"}
        if our_cols.issubset(set(df.columns)):
            # Mapeo automático de columnas propias → campos de comparación
            col_map = {
                "front_position": ("tiempo_s", "frente_x_m",       "m"),
                "front_velocity": ("tiempo_s", "velocidad_frente_m_s", "m/s"),
                "fluid_area":     ("tiempo_s", "area_fluido_m2",    "m²"),
                "fluid_volume":   ("tiempo_s", "volumen_fluido_m3", "m³"),
            }
            t_col, v_col, auto_units = col_map.get(field, ("tiempo_s", "frente_x_m", "m"))
            time_col  = t_col
            value_col = v_col
            units     = units if units != "m" else auto_units
            self._log(f"  Formato reconocido: columnas '{t_col}' y '{v_col}'")

        times, values = self._extract_columns(df, time_col, value_col)

        label = label or file_path.stem
        self._log(f"  Cargados {len(times)} puntos de datos")
        self._log(f"  t: [{times.min():.3f}, {times.max():.3f}] s")
        self._log(f"  valores: [{values.min():.4f}, {values.max():.4f}] {units}")

        return ExperimentalData(
            source_file = str(file_path),
            label       = label,
            times       = times,
            values      = values,
            field       = field,
            units       = units,
        )

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
    ) -> ExperimentalData:
        """
        Carga datos experimentales desde un archivo Excel.

        Args:
            file_path:  Ruta al archivo .xlsx o .xls.
            sheet_name: Nombre o índice de la hoja.
            time_col:   Columna de tiempo.
            value_col:  Columna de valores.
            label:      Etiqueta para la gráfica.
            field:      Tipo de dato.
            units:      Unidades.
            skip_rows:  Filas a omitir.

        Returns:
            ExperimentalData listo para comparar.
        """
        import pandas as pd

        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

        self._log(f"Cargando Excel: {file_path.name} (hoja: {sheet_name})")

        try:
            df = pd.read_excel(
                file_path,
                sheet_name = sheet_name,
                skiprows   = skip_rows,
            )
        except Exception as e:
            raise ValueError(f"Error al leer Excel: {e}")

        times, values = self._extract_columns(df, time_col, value_col)

        label = label or f"{file_path.stem} ({sheet_name})"
        self._log(f"  Cargados {len(times)} puntos")

        return ExperimentalData(
            source_file = str(file_path),
            label       = label,
            times       = times,
            values      = values,
            field       = field,
            units       = units,
        )

    # ── Comparación ───────────────────────────────────────────────────────────

    def compare_with_experimental(
        self,
        sim_data:   WaveFrontData,
        exp_data:   ExperimentalData,
    ) -> dict:
        """
        Compara métricas de la simulación con datos experimentales.

        Args:
            sim_data: Datos de la simulación (WaveFrontData).
            exp_data: Datos experimentales (ExperimentalData).

        Returns:
            Dict con métricas de comparación: RMSE, MAE, R², bias.
        """
        sim_values = WaveFrontExtractor.interpolate_at_times(
            sim_data,
            exp_data.times,
            field = exp_data.field,
        )
        exp_values = exp_data.values

        residuals = sim_values - exp_values
        rmse      = float(np.sqrt(np.mean(residuals ** 2)))
        mae       = float(np.mean(np.abs(residuals)))
        bias      = float(np.mean(residuals))

        # R² (coeficiente de determinación)
        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((exp_values - exp_values.mean()) ** 2)
        r2     = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

        return {
            "rmse": rmse,
            "mae":  mae,
            "bias": bias,
            "r2":   r2,
            "n_points": len(exp_data.times),
        }

    # ── Utilidades internas ───────────────────────────────────────────────────

    @staticmethod
    def _extract_columns(
        df:        "pd.DataFrame",
        time_col:  str | int,
        value_col: str | int,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Extrae columnas de tiempo y valor de un DataFrame."""
        # Seleccionar por nombre o índice
        if isinstance(time_col, int):
            t_series = df.iloc[:, time_col]
        else:
            t_series = df[time_col]

        if isinstance(value_col, int):
            v_series = df.iloc[:, value_col]
        else:
            v_series = df[value_col]

        # Convertir y limpiar NaN
        times  = t_series.to_numpy(dtype=np.float64, na_value=np.nan)
        values = v_series.to_numpy(dtype=np.float64, na_value=np.nan)

        # Eliminar filas con NaN
        mask   = ~(np.isnan(times) | np.isnan(values))
        times  = times[mask]
        values = values[mask]

        # Ordenar por tiempo
        order  = np.argsort(times)
        return times[order], values[order]

    def __repr__(self) -> str:
        return "DataExtractor()"
