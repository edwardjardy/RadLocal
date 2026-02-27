#!/usr/bin/env bash
# =============================================================================
# install.sh – RadLocal Linux Installer
# =============================================================================
# Instalación con un solo comando para jugadores de EVE Online:
#
#   curl -fsSL https://raw.githubusercontent.com/TU_USUARIO/RadLocal/main/install.sh | bash
#
# O descargando manualmente:
#   chmod +x install.sh && ./install.sh
#
# Qué hace:
#   1. Detecta la última versión desde GitHub Releases API
#   2. Descarga el tarball del release
#   3. Extrae en ~/.local/share/radlocal/
#   4. Crea entrada en el menú de aplicaciones (.desktop)
#   5. Crea symlink en ~/.local/bin/radlocal
# =============================================================================

set -euo pipefail

# ─── Configuración ────────────────────────────────────────────────────────────
GITHUB_USER="edwardjardy"    # <- Cambia esto
GITHUB_REPO="RadLocal"
APP_NAME="RadLocal"
INSTALL_DIR="${HOME}/.local/share/radlocal"
BIN_DIR="${HOME}/.local/bin"
DESKTOP_DIR="${HOME}/.local/share/applications"

# ─── Colores ─────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No color

log_info()    { echo -e "${CYAN}▶${NC} $*"; }
log_success() { echo -e "${GREEN}✓${NC} $*"; }
log_warn()    { echo -e "${YELLOW}⚠${NC} $*"; }
log_error()   { echo -e "${RED}✗${NC} $*" >&2; }

# ─── Banner ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${CYAN}"
echo "  ██████╗  █████╗ ██████╗ ██╗      ██████╗  ██████╗ █████╗ ██╗"
echo "  ██╔══██╗██╔══██╗██╔══██╗██║     ██╔═══██╗██╔════╝██╔══██╗██║"
echo "  ██████╔╝███████║██║  ██║██║     ██║   ██║██║     ███████║██║"
echo "  ██╔══██╗██╔══██║██║  ██║██║     ██║   ██║██║     ██╔══██║██║"
echo "  ██║  ██║██║  ██║██████╔╝███████╗╚██████╔╝╚██████╗██║  ██║███████╗"
echo "  ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚══════╝ ╚═════╝  ╚═════╝╚═╝  ╚═╝╚══════╝"
echo -e "${NC}"
echo -e "  Instalador para Linux – EVE Online Intel Tool"
echo ""

# ─── Verificar dependencias del sistema ──────────────────────────────────────
log_info "Verificando herramientas necesarias..."

for cmd in curl tar; do
    if ! command -v "$cmd" &>/dev/null; then
        log_error "Herramienta requerida no encontrada: $cmd"
        echo "  Instálala con: sudo apt install $cmd"
        exit 1
    fi
done
log_success "Herramientas OK"

# ─── Obtener la última versión desde GitHub API ───────────────────────────────
log_info "Consultando GitHub por la última versión..."

LATEST_RELEASE=$(curl -fsSL \
    "https://api.github.com/repos/${GITHUB_USER}/${GITHUB_REPO}/releases/latest" \
    2>/dev/null || echo "")

if [ -z "$LATEST_RELEASE" ]; then
    log_error "No se pudo contactar GitHub. Verifica tu conexión a internet."
    exit 1
fi

# Parsear la versión usando grep/sed (sin jq para no tener dependencias extra)
VERSION=$(echo "$LATEST_RELEASE" | grep '"tag_name"' | sed -E 's/.*"tag_name": *"([^"]+)".*/\1/')
if [ -z "$VERSION" ]; then
    log_error "No se encontró ninguna release publicada en GitHub."
    log_warn "Visita: https://github.com/${GITHUB_USER}/${GITHUB_REPO}/releases"
    exit 1
fi

TARBALL_NAME="radlocal-${VERSION}-linux.tar.gz"
DOWNLOAD_URL="https://github.com/${GITHUB_USER}/${GITHUB_REPO}/releases/download/${VERSION}/${TARBALL_NAME}"

echo ""
log_success "Versión más reciente: ${BOLD}${VERSION}${NC}"
log_info "URL de descarga: ${DOWNLOAD_URL}"
echo ""

# ─── Confirmar instalación ────────────────────────────────────────────────────
echo -e "${BOLD}RadLocal se instalará en:${NC} ${INSTALL_DIR}"
echo -e "${BOLD}Acceso desde:${NC} ${BIN_DIR}/radlocal (comando) y menú de aplicaciones"
echo ""
echo -n "¿Continuar? [S/n] "
read -r response
if [[ "$response" =~ ^[nN]$ ]]; then
    echo "Instalación cancelada."
    exit 0
fi
echo ""

# ─── Desinstalar versión anterior si existe ───────────────────────────────────
if [ -d "$INSTALL_DIR" ]; then
    log_warn "Versión anterior detectada. Actualizando..."
    rm -rf "${INSTALL_DIR}"
fi

# ─── Descargar ────────────────────────────────────────────────────────────────
TMPDIR_INSTALL=$(mktemp -d)
TMPFILE="${TMPDIR_INSTALL}/${TARBALL_NAME}"

log_info "Descargando ${TARBALL_NAME}..."
if ! curl -fsSL --progress-bar -o "$TMPFILE" "$DOWNLOAD_URL"; then
    log_error "Fallo en la descarga. Verifica la URL:"
    log_error "  ${DOWNLOAD_URL}"
    rm -rf "$TMPDIR_INSTALL"
    exit 1
fi
log_success "Descarga completada"

# ─── Extraer ──────────────────────────────────────────────────────────────────
log_info "Extrayendo en ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}"
tar -xzf "$TMPFILE" -C "${INSTALL_DIR}" --strip-components=1

if [ ! -f "${INSTALL_DIR}/radlocal" ]; then
    log_error "El ejecutable 'radlocal' no se encontró en el tarball."
    exit 1
fi

chmod +x "${INSTALL_DIR}/radlocal"
log_success "Archivos extraídos"

# Limpiar temporal
rm -rf "$TMPDIR_INSTALL"

# ─── Crear symlink en ~/.local/bin ────────────────────────────────────────────
mkdir -p "${BIN_DIR}"
ln -sf "${INSTALL_DIR}/radlocal" "${BIN_DIR}/radlocal"
log_success "Symlink creado en ${BIN_DIR}/radlocal"

# ─── Crear entrada en el menú de aplicaciones ────────────────────────────────
mkdir -p "${DESKTOP_DIR}"

cat > "${DESKTOP_DIR}/radlocal.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=RadLocal
GenericName=EVE Online Intel Tool
Comment=Herramienta táctica de inteligencia para EVE Online
Exec=${INSTALL_DIR}/radlocal
Icon=${INSTALL_DIR}/icon.png
Terminal=false
Categories=Game;Utility;
Keywords=EVE;Online;Intel;Map;Radar;
StartupNotify=true
StartupWMClass=radlocal
EOF

update-desktop-database "${DESKTOP_DIR}" 2>/dev/null || true
log_success "Entrada del menú de aplicaciones creada"

# ─── Verificar PATH ───────────────────────────────────────────────────────────
echo ""
if [[ ":$PATH:" != *":${BIN_DIR}:"* ]]; then
    log_warn "${BIN_DIR} no está en tu PATH."
    echo ""
    echo "  Añade esta línea a tu ~/.bashrc o ~/.zshrc:"
    echo ""
    echo -e "    ${BOLD}export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
    echo ""
    echo "  Luego recarga con: source ~/.bashrc"
    echo "  O ejecuta directamente: ${INSTALL_DIR}/radlocal"
else
    log_success "${BIN_DIR} ya está en el PATH"
fi

# ─── Resumen final ────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║  ✓ RadLocal ${VERSION} instalado exitosamente!            ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Puedes iniciar RadLocal de tres formas:"
echo -e "    ${BOLD}1.${NC} Buscando 'RadLocal' en el menú de aplicaciones"
echo -e "    ${BOLD}2.${NC} Ejecutando: radlocal"
echo -e "    ${BOLD}3.${NC} Desde el explorador de archivos: ${INSTALL_DIR}/radlocal"
echo ""
echo "  Las actualizaciones futuras son automáticas — al abrir la"
echo "  app, se comprobará si hay una nueva versión disponible."
echo ""
