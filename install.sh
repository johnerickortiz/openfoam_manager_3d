#!/bin/bash
# ============================================================
# OpenFOAM Manager 3D — Script de instalación automática
# Compatible con: Ubuntu 20.04, 22.04 y WSL2
#
# Uso:
#   chmod +x install.sh
#   bash install.sh
# ============================================================

set -e

BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}   OpenFOAM Manager 3D — Instalación           ${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# ── 1. Verificar Python 3.10+ ────────────────────────────────
echo -e "${YELLOW}[1/5] Verificando Python...${NC}"
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}✗ Python 3 no encontrado.${NC}"
    echo "  Instalar con: sudo apt-get install python3 python3-pip"
    exit 1
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo $PY_VER | cut -d. -f1)
PY_MINOR=$(echo $PY_VER | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]); then
    echo -e "${RED}✗ Python $PY_VER detectado. Se requiere Python 3.10+${NC}"
    echo "  Instalar versión más reciente: sudo apt-get install python3.11"
    exit 1
fi
echo -e "${GREEN}✓ Python $PY_VER${NC}"

# ── 2. Instalar dependencias Python ─────────────────────────
echo ""
echo -e "${YELLOW}[2/5] Instalando dependencias Python...${NC}"

# Intentar pip normal primero, luego con --break-system-packages (Ubuntu 23+)
pip3 install -r requirements.txt --quiet 2>/dev/null || \
pip3 install -r requirements.txt --quiet --break-system-packages 2>/dev/null || \
{
    echo -e "${YELLOW}  pip global falló, probando con apt...${NC}"
    sudo apt-get install -y -q python3-pyqt5 python3-matplotlib python3-numpy \
        python3-pandas python3-scipy python3-openpyxl 2>/dev/null
}

# Verificar PyQt5
if python3 -c "from PyQt5.QtWidgets import QApplication" 2>/dev/null; then
    echo -e "${GREEN}✓ Dependencias Python instaladas${NC}"
else
    echo -e "${RED}✗ PyQt5 no disponible.${NC}"
    echo "  Intentar: sudo apt-get install python3-pyqt5 libxcb-xinerama0"
    exit 1
fi

# ── 3. Verificar/instalar OpenFOAM 9 ────────────────────────
echo ""
echo -e "${YELLOW}[3/5] Verificando OpenFOAM 9...${NC}"

if [ -f "/opt/openfoam9/etc/bashrc" ]; then
    echo -e "${GREEN}✓ OpenFOAM 9 ya está instalado${NC}"
    source /opt/openfoam9/etc/bashrc
else
    echo -e "${YELLOW}  OpenFOAM 9 no encontrado. Instalando...${NC}"
    echo "  (Puede tardar 5-15 minutos dependiendo de la conexión)"

    sudo sh -c "wget -q -O - https://dl.openfoam.org/gpg.key \
        > /etc/apt/trusted.gpg.d/openfoam.asc"
    sudo add-apt-repository -y http://dl.openfoam.org/ubuntu 2>/dev/null
    sudo apt-get update -q
    sudo apt-get install -y openfoam9

    if [ -f "/opt/openfoam9/etc/bashrc" ]; then
        echo -e "${GREEN}✓ OpenFOAM 9 instalado${NC}"
    else
        echo -e "${YELLOW}⚠ No se pudo instalar OpenFOAM automáticamente.${NC}"
        echo "  Instalar manualmente según README.md"
        echo "  La aplicación detectará OpenFOAM al simular."
    fi
fi

# Añadir source al .bashrc si no está
if ! grep -q "openfoam9" ~/.bashrc 2>/dev/null; then
    echo "" >> ~/.bashrc
    echo "# OpenFOAM 9" >> ~/.bashrc
    echo "source /opt/openfoam9/etc/bashrc" >> ~/.bashrc
    echo -e "${GREEN}✓ OpenFOAM añadido a ~/.bashrc${NC}"
fi

# ── 4. Verificar ParaView (informativo) ─────────────────────
echo ""
echo -e "${YELLOW}[4/5] Verificando ParaView...${NC}"

if command -v paraview &>/dev/null; then
    PV_VER=$(paraview --version 2>/dev/null | head -1 || echo "desconocida")
    echo -e "${GREEN}✓ ParaView encontrado: $PV_VER${NC}"
else
    echo -e "${YELLOW}  ParaView no detectado en PATH.${NC}"
    echo "  • Linux: sudo apt-get install paraview"
    echo "  • Windows: descargar desde https://www.paraview.org/download/"
    echo "  La aplicación permite seleccionar la ruta manualmente."
fi

# ── 5. Verificar entorno gráfico ─────────────────────────────
echo ""
echo -e "${YELLOW}[5/5] Verificando entorno gráfico...${NC}"

IS_WSL=false
if grep -qi "microsoft\|wsl" /proc/version 2>/dev/null; then
    IS_WSL=true
    echo "  Detectado: WSL2"
fi

if [ -n "$DISPLAY" ]; then
    echo -e "${GREEN}✓ DISPLAY configurado: $DISPLAY${NC}"
elif [ "$IS_WSL" = true ]; then
    echo -e "${YELLOW}⚠ DISPLAY no configurado.${NC}"
    echo ""
    echo "  Opciones para activar el display en WSL2:"
    echo ""
    echo "  A) Windows 11 con WSLg (recomendado):"
    echo "     El soporte gráfico está incluido. Asegúrate de tener"
    echo "     WSL2 actualizado: wsl --update (en PowerShell como admin)"
    echo ""
    echo "  B) Windows 10 con VcXsrv:"
    echo "     1. Instalar VcXsrv en Windows (sourceforge.net/projects/vcxsrv)"
    echo "     2. Ejecutar XLaunch con 'Disable access control' marcado"
    echo "     3. Ejecutar en WSL2:"
    NAMESERVER=$(cat /etc/resolv.conf 2>/dev/null | grep nameserver | awk '{print $2}')
    echo "        export DISPLAY=${NAMESERVER:-<ip_windows>}:0"
    echo "        # Añadir permanentemente a ~/.bashrc"
else
    echo -e "${YELLOW}⚠ DISPLAY no configurado (Linux sin sesión gráfica activa).${NC}"
    echo "  Ejecutar desde una sesión de escritorio."
fi

# ── Resumen ──────────────────────────────────────────────────
echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${GREEN}✅ Instalación completada${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo -e "Para ejecutar la aplicación:"
echo -e "  ${YELLOW}python3 main.py${NC}"
echo ""

if [ "$IS_WSL" = true ] && [ -z "$DISPLAY" ]; then
    echo -e "${YELLOW}Nota:${NC} Configura DISPLAY antes de ejecutar (ver pasos arriba)"
    echo ""
fi

if [ -f "/opt/openfoam9/etc/bashrc" ]; then
    echo -e "Verificación rápida de OpenFOAM:"
    echo -e "  ${YELLOW}source /opt/openfoam9/etc/bashrc && interFoam -help | head -1${NC}"
    echo ""
fi
