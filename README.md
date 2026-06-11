# OpenFOAM Manager 3D

Aplicación de escritorio (Python/PyQt5) para configurar, ejecutar y analizar simulaciones CFD 3D de rompimiento de presas con fluidos no newtonianos usando **OpenFOAM 9**.

Desarrollado para comparar simulaciones numéricas con experimentos físicos en canal de laboratorio, enfocado en flujos de lodo volcánico (lahares) modelados con el modelo reológico **Herschel-Bulkley**.

---

## Características

- **Simulación 3D** con malla `nx × ny × nz` y paredes laterales físicas (frontWall / backWall)
- **Fluidos soportados**: Herschel-Bulkley viscoplástico (lodo/lahar) y Newtoniano (agua)
- **Turbulencia automática**: laminar para HB, k-ε para Newtoniano (configurable)
- **Interfaz por panel**: resumen siempre visible + diálogos de edición por sección
- **Post-procesamiento 3D**: frente X(t), velocidad V(t), perfil lateral h(x,t), vista en planta alpha(x,z), perfil transversal h(z,t), volumen Vol(t)
- **Visualización 3D interactiva**: cortes x-y, x-z y y-z con slider temporal y animación
- **Comparación**: N simulaciones + datos experimentales (CSV/Excel)
- **Exportación**: CSV, Excel, JSON, PNG
- **Gestor de casos**: cargar, limpiar y guardar proyectos

---

## Requisitos del sistema

### Sistema operativo

| Plataforma | Soporte |
|---|---|
| **Windows 10/11 + WSL2** (Ubuntu 22.04) | ✅ Recomendado |
| **Linux** (Ubuntu 20.04, 22.04, Debian 11+) | ✅ Nativo |
| macOS | ❌ No soportado (OpenFOAM 9 no disponible) |

### Software requerido

| Software | Versión mínima | Notas |
|---|---|---|
| **Python** | 3.10 | 3.11 o 3.12 recomendado |
| **OpenFOAM 9** | 9 | Instalado en Linux/WSL2 |
| **ParaView** | 5.10 | Para visualización avanzada (opcional) |

---

## Instalación

### Opción A — Windows 10/11 con WSL2 (Recomendada)

Esta es la configuración utilizada en el desarrollo. La aplicación corre en Windows (Python nativo) y llama a OpenFOAM a través de WSL2.

#### 1. Instalar WSL2 con Ubuntu 22.04

Abrir PowerShell como administrador:

```powershell
wsl --install -d Ubuntu-22.04
```

Reiniciar el equipo cuando se solicite. Completar la configuración inicial de Ubuntu (usuario y contraseña).

Verificar que WSL2 está activo:

```powershell
wsl --list --verbose
# Debe mostrar Ubuntu-22.04 con VERSION 2
```

#### 2. Instalar OpenFOAM 9 en WSL2

Abrir la terminal de Ubuntu (desde el menú inicio o `wsl` en PowerShell):

```bash
# Agregar repositorio oficial de OpenFOAM
sudo sh -c "wget -O - https://dl.openfoam.org/gpg.key \
    > /etc/apt/trusted.gpg.d/openfoam.asc"
sudo add-apt-repository http://dl.openfoam.org/ubuntu
sudo apt-get update

# Instalar OpenFOAM 9
sudo apt-get install -y openfoam9

# Verificar instalación
source /opt/openfoam9/etc/bashrc
interFoam -help | head -3
```

Añadir el source automático al `.bashrc` de WSL:

```bash
echo "source /opt/openfoam9/etc/bashrc" >> ~/.bashrc
```

#### 3. Instalar Python 3.10+ en Windows

Descargar el instalador desde [python.org/downloads](https://www.python.org/downloads/).

Durante la instalación marcar **"Add Python to PATH"**.

Verificar en PowerShell:

```powershell
python --version
# Python 3.11.x o superior
```

#### 4. Instalar ParaView en Windows (opcional)

Descargar desde [paraview.org/download](https://www.paraview.org/download/) e instalar normalmente. La aplicación lo detecta automáticamente o puedes indicar la ruta manualmente con el botón **📂 Buscar ParaView...** en la pestaña Visualización 3D.

#### 5. Clonar e instalar la aplicación

En PowerShell:

```powershell
# Clonar el repositorio
git clone https://github.com/johnerickortiz/openfoam_manager_3d.git
cd openfoam_manager_3d

# Instalar dependencias Python
pip install -r requirements.txt

# Ejecutar
python main.py
```

---

### Opción B — Linux nativo (Ubuntu 20.04 / 22.04)

#### 1. Instalar OpenFOAM 9

```bash
sudo sh -c "wget -O - https://dl.openfoam.org/gpg.key \
    > /etc/apt/trusted.gpg.d/openfoam.asc"
sudo add-apt-repository http://dl.openfoam.org/ubuntu
sudo apt-get update
sudo apt-get install -y openfoam9

# Activar en sesión actual y en futuras sesiones
source /opt/openfoam9/etc/bashrc
echo "source /opt/openfoam9/etc/bashrc" >> ~/.bashrc
```

#### 2. Instalar Python y dependencias del sistema

```bash
sudo apt-get install -y \
    python3 python3-pip python3-venv \
    python3-pyqt5 python3-pyqt5.qtsvg \
    libglib2.0-0 libgl1-mesa-glx
```

#### 3. Instalar ParaView (opcional)

```bash
sudo apt-get install -y paraview
```

O descargar la versión más reciente desde [paraview.org/download](https://www.paraview.org/download/).

#### 4. Clonar e instalar la aplicación

```bash
git clone https://github.com/johnerickortiz/openfoam_manager_3d.git
cd openfoam_manager_3d

# Opción A: instalar en el sistema (Ubuntu 23+ con PEP 668)
pip install -r requirements.txt --break-system-packages

# Opción B: entorno virtual (recomendado)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Ejecutar
python3 main.py
```

---

### Opción C — WSL2 directo (aplicación en Linux dentro de WSL)

Usar si se prefiere ejecutar todo (incluyendo la UI) desde WSL2, con soporte gráfico via **WSLg** (Windows 11) o **VcXsrv** (Windows 10).

#### Requisitos adicionales para WSL2 directo

**Windows 11 (WSLg):** el soporte gráfico está incluido. La aplicación debería funcionar sin configuración adicional.

**Windows 10 (VcXsrv):**

1. Instalar [VcXsrv](https://sourceforge.net/projects/vcxsrv/) en Windows
2. Ejecutar XLaunch con la opción **"Disable access control"** marcada
3. En WSL2, configurar la variable DISPLAY:

```bash
# Añadir al ~/.bashrc de WSL2:
export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0
export LIBGL_ALWAYS_INDIRECT=1
```

#### Instalación (dentro de WSL2)

Seguir los mismos pasos de la **Opción B** pero dentro de la terminal de WSL2. Verificar que el entorno gráfico funciona antes de ejecutar:

```bash
# Probar que el display funciona
xeyes   # debe aparecer una ventana con ojos
```

---

## Verificación rápida de la instalación

Antes de ejecutar la aplicación, verificar que los componentes críticos están disponibles:

```bash
# En WSL2 / Linux
source /opt/openfoam9/etc/bashrc

# OpenFOAM
interFoam -help | head -1
find /opt/openfoam9 -name "HerschelBulkley.C" | head -1

# Python y dependencias
python3 -c "import PyQt5, matplotlib, numpy, pandas; print('OK')"
```

---

## Ejecución

### Windows + WSL2

```powershell
cd C:\ruta\al\openfoam_manager_3d
python main.py
```

### Linux / WSL2 directo

```bash
cd ~/openfoam_manager_3d
# Si usas entorno virtual:
source .venv/bin/activate
python3 main.py
```

---

## Uso básico

### Primer uso — nueva simulación

1. **Panel izquierdo → Fluido [Editar]:** seleccionar modelo (Herschel-Bulkley o Newtoniano) y ajustar parámetros.
2. **Geometría [Editar]:** configurar dimensiones del canal (L × H × W) y resolución de malla.
3. **Simulación [Editar]:** establecer nombre del caso, directorio de salida y tiempo final.
4. **▶ Ejecutar simulación:** genera los archivos OpenFOAM y lanza la simulación en WSL.
5. **Pestaña Resultados:** ver gráficas de X(t), V(t), Vol(t), h(x,t) con el selector desplegable.
6. **Pestaña Visualización 3D:** explorar los campos alpha con los tres modos de vista.

### Cargar simulación existente

1. **📂 Cargar caso...** en el panel izquierdo.
2. Seleccionar el caso de la lista (muestra pasos y rango de tiempo disponibles).
3. Los resultados y campos se cargan automáticamente.

### Comparar con datos experimentales

1. **Pestaña Comparación → Cargar CSV:** cargar datos experimentales.
2. Seleccionar la métrica a comparar (posición del frente, velocidad, etc.).
3. **Comparar:** genera la gráfica superpuesta simulación vs experimento.

---

## Estructura del proyecto

```
openfoam_manager_3d/
│
├── main.py                         # Punto de entrada
├── requirements.txt
├── install.sh                      # Script de instalación automática (Linux/WSL)
│
├── core/                           # Lógica de dominio (sin dependencias UI)
│   ├── models/                     # Modelos de fluido (HB, Newtoniano)
│   ├── simulation/                 # GeometryConfig, SimulationConfig
│   └── postprocessing/             # FoamReader, WaveFrontExtractor 3D
│
├── services/                       # Servicios de infraestructura
│   ├── case_generator.py           # Genera archivos OpenFOAM
│   ├── simulation_runner.py        # Ejecuta blockMesh/setFields/interFoam
│   ├── data_extractor.py           # Extrae métricas de resultados
│   ├── exporter.py                 # Exporta a CSV/Excel/JSON/PNG
│   ├── paraview_launcher.py        # Detecta y lanza ParaView
│   └── openfoam_detector.py        # Detecta OpenFOAM en WSL/Linux
│
├── controllers/                    # Coordinan servicios y UI
│   ├── simulation_controller.py    # Flujo de simulación
│   └── results_controller.py       # Carga y comparación de resultados
│
└── ui/                             # Interfaz gráfica (PyQt5)
    ├── main_window.py
    ├── panels/                     # Panel lateral de configuración
    ├── dialogs/                    # Diálogos de edición (Fluido, Geometría, etc.)
    ├── tabs/                       # Pestañas (Resultados, Comparación, Visualización)
    └── widgets/                    # Widgets reutilizables (PlotWidget, Preview, etc.)
```

---

## Parámetros del modelo Herschel-Bulkley

El modelo reológico utilizado para lodo viscoplástico es:

```
τ = (τ₀ + k·|γ̇|ⁿ) · γ̇/|γ̇|   si |τ| > τ₀   (zona de flujo)
γ̇ = 0                           si |τ| ≤ τ₀   (zona plug)
```

| Parámetro | Símbolo | Descripción | Unidades | Valor típico lodo |
|---|---|---|---|---|
| Esfuerzo de fluencia | τ₀ | Umbral mínimo para fluir | Pa | 20 – 200 |
| Consistencia | k | Resistencia al flujo | Pa·sⁿ | 5 – 50 |
| Índice de flujo | n | Tipo de comportamiento (< 1 pseudoplástico) | — | 0.3 – 0.6 |
| Densidad | ρ | Densidad del fluido | kg/m³ | 1500 – 2200 |

**Nota:** OpenFOAM trabaja con viscosidad cinemática. La aplicación convierte automáticamente τ₀ y k dividiendo por ρ.

---

## Resolución de problemas comunes

### La simulación falla en `setFields`

Verificar que el entorno de OpenFOAM está activo en WSL:

```bash
source /opt/openfoam9/etc/bashrc
interFoam -help | head -1
```

### ParaView no se detecta automáticamente

Usar el botón **📂 Buscar ParaView...** en la pestaña Visualización 3D y navegar hasta `paraview.exe` en `C:\Program Files\ParaView X.X.X\bin\`.

### La ventana no aparece en WSL2 (Windows 10)

Verificar que VcXsrv está ejecutándose y que `$DISPLAY` está configurado:

```bash
echo $DISPLAY   # debe mostrar algo como 172.16.x.x:0
xeyes           # prueba básica de la interfaz gráfica
```

### Error de PyQt5 en Linux

```bash
sudo apt-get install -y python3-pyqt5 libxcb-xinerama0
# o con pip:
pip install PyQt5 --break-system-packages
```

---

## Instalación automática (Linux / WSL2)

El script `install.sh` automatiza los pasos 1–4 de la instalación en Linux:

```bash
chmod +x install.sh
bash install.sh
```

---

## Referencias

- [OpenFOAM 9 Documentation](https://openfoam.org/version/9/)
- Herschel, W.H. & Bulkley, R. (1926). *Konsistenzmessungen von Gummi-Benzollösungen*. Kolloid Zeitschrift, 39, 291–300.
- Ancey, C. (2007). *Plasticity and geophysical flows: A review*. J. Non-Newtonian Fluid Mech., 142(1–3), 4–35.

---

## Licencia

MIT License — ver [LICENSE](LICENSE) para detalles.
