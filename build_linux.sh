#!/usr/bin/env bash
# =============================================================================
# build_linux.sh – RadLocal Release Builder
# =============================================================================
# Uso (como desarrollador):
#   chmod +x build_linux.sh
#   ./build_linux.sh 1.2.0
#
# Qué hace:
#   1. Genera version.json con hashes SHA-256 de cada archivo actualizable
#   2. Corre PyInstaller para crear el ejecutable nativo
#   3. Empaqueta el resultado en un .tar.gz listo para el release
#   4. (Opcional, requiere gh CLI) Sube automáticamente a GitHub Releases
# =============================================================================

set -euo pipefail

# ─── Configuración ────────────────────────────────────────────────────────────
GITHUB_USER="edwardjardy"    # <- Cambia esto
GITHUB_REPO="RadLocal"      # <- Cambia esto
GITHUB_BRANCH="main"

# Archivos que el updater puede actualizar en caliente
UPDATABLE_FILES=(
    "map_widget.py"
    "cartographer.py"
    "threat_profiler.py"
    "esi_tracker.py"
    "intel_parser.py"
    "intel_tailer.py"
    "logistics.py"
    "audio_engine.py"
    "auth.py"
    "config_manager.py"
    "systems_cache.json"
    "esi_ids.json"
)

# ─── Validar argumento de versión ─────────────────────────────────────────────
if [ "$#" -ne 1 ]; then
    echo "Uso: $0 <version>"
    echo "  Ejemplo: $0 1.2.0"
    exit 1
fi

VERSION="$1"
TAG="v${VERSION}"
DIST_DIR="dist/radlocal"
TARBALL="radlocal-${TAG}-linux.tar.gz"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║        RadLocal Release Builder – ${TAG}                "
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ─── Paso 1: Verificar dependencias ──────────────────────────────────────────
echo "▶ Verificando dependencias..."
python3 -c "import PyInstaller" 2>/dev/null || {
    echo "  PyInstaller no encontrado. Instalando..."
    pip install pyinstaller --quiet
}

# ─── Paso 2: Generar version.json ────────────────────────────────────────────
echo "▶ Generando version.json con hashes SHA-256..."

DOWNLOAD_BASE="https://raw.githubusercontent.com/${GITHUB_USER}/${GITHUB_REPO}/${GITHUB_BRANCH}/"

# Construir el JSON de archivos con sus hashes
FILES_JSON=""
FIRST=true
for fname in "${UPDATABLE_FILES[@]}"; do
    if [ -f "$fname" ]; then
        HASH=$(sha256sum "$fname" | awk '{print $1}')
        if [ "$FIRST" = true ]; then
            FILES_JSON="\"${fname}\": \"sha256:${HASH}\""
            FIRST=false
        else
            FILES_JSON="${FILES_JSON},\n            \"${fname}\": \"sha256:${HASH}\""
        fi
    else
        echo "  ⚠ Archivo no encontrado: $fname (se omite del manifiesto)"
    fi
done

# Obtener fecha de la release
RELEASE_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

cat > version.json << EOF
{
    "version": "${VERSION}",
    "tag": "${TAG}",
    "release_date": "${RELEASE_DATE}",
    "release_notes": "Nueva versión de RadLocal. Ver CHANGELOG para detalles.",
    "download_base": "${DOWNLOAD_BASE}",
    "files": {
        $(echo -e "$FILES_JSON")
    }
}
EOF

echo "  ✓ version.json generado (versión ${VERSION})"
cat version.json
echo ""

# ─── Paso 3: Limpiar builds anteriores ───────────────────────────────────────
echo "▶ Limpiando builds anteriores..."
rm -rf build/ dist/ __pycache__/ *.spec.bak
echo "  ✓ Limpio"

# ─── Paso 4: PyInstaller ─────────────────────────────────────────────────────
echo "▶ Empaquetando con PyInstaller..."
pyinstaller radlocal.spec --noconfirm --clean

if [ ! -f "${DIST_DIR}/radlocal" ]; then
    echo "❌ ERROR: PyInstaller completó pero no se encontró el ejecutable."
    exit 1
fi

echo "  ✓ Ejecutable generado en ${DIST_DIR}/radlocal"

# ─── Paso 5: Copiar version.json al directorio de distribución ───────────────
echo "▶ Copiando version.json al directorio de distribución..."
cp version.json "${DIST_DIR}/version.json"

# ─── Paso 6: Crear tarball ───────────────────────────────────────────────────
echo "▶ Creando archivo comprimido ${TARBALL}..."
cd dist
tar -czf "../${TARBALL}" radlocal/
cd ..

TARBALL_SIZE=$(du -sh "${TARBALL}" | cut -f1)
echo "  ✓ ${TARBALL} creado (${TARBALL_SIZE})"

# ─── Paso 7: Resumen del release ─────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  ✓ Build completado exitosamente                         ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "  Archivos generados:"
echo "    • ${TARBALL}     ← Para subir a GitHub Releases"
echo "    • version.json         ← Para commitar al repo (rama main)"
echo ""
echo "  Próximos pasos:"
echo "    1. git add version.json && git commit -m 'chore: bump to ${TAG}'"
echo "    2. git tag ${TAG} && git push && git push --tags"
echo "    3. Subir ${TARBALL} a GitHub Releases manualmente, o:"
echo ""

# ─── Paso 8: (Opcional) Subir a GitHub via gh CLI ───────────────────────────
if command -v gh &>/dev/null; then
    echo "  gh CLI detectado. ¿Subir automáticamente a GitHub Releases? [s/N]"
    read -r response
    if [[ "$response" =~ ^[sS]$ ]]; then
        echo "▶ Subiendo a GitHub Releases..."
        gh release create "${TAG}" \
            "${TARBALL}" \
            version.json \
            --title "RadLocal ${TAG}" \
            --notes "$(cat CHANGELOG.md 2>/dev/null | head -50 || echo 'Nueva versión de RadLocal.')" \
            --repo "${GITHUB_USER}/${GITHUB_REPO}"
        echo "  ✓ Release ${TAG} publicado en GitHub"
    fi
else
    echo "    gh CLI no instalado. Sube los archivos manualmente a:"
    echo "    https://github.com/${GITHUB_USER}/${GITHUB_REPO}/releases/new"
fi

echo ""
echo "Done. 🚀"
