# RadLocal – Manual de Instalación

**Herramienta táctica de inteligencia para EVE Online**  
Versión actual: `0.1.0`

---

## ¿Qué es RadLocal?

RadLocal es un programa de escritorio para Linux que te muestra en tiempo real quiénes están en los sistemas cercanos a tu ubicación en EVE Online. Lee los logs de intel del juego, los procesa y te muestra un mapa táctico con alertas de amenazas, Jump Bridges y más.

---

## Requisitos del sistema

| Requisito | Detalle |
|-----------|---------|
| **Sistema operativo** | Linux (Ubuntu 20.04+, Fedora 38+, Debian 11+, Arch, etc.) |
| **Conexión a internet** | Necesaria para autenticarse con EVE Online (ESI) |
| **EVE Online** | El cliente debe estar instalado y haber iniciado sesión al menos una vez para que existan los logs |

> **Nota:** No necesitas tener Python instalado. El instalador descarga un ejecutable listo para usar.

---

## Instalación (método recomendado)

Abre una terminal (`Ctrl + Alt + T` o busca "Terminal" en tu menú) y ejecuta:

```bash
curl -fsSL https://raw.githubusercontent.com/edwardjardy/RadLocal/main/install.sh | bash
```

El instalador se encargará automáticamente de:

1. Detectar la última versión disponible en GitHub
2. Descargar el programa
3. Instalarlo en `~/.local/share/radlocal/`
4. Crear un acceso directo en el menú de aplicaciones
5. Crear el comando `radlocal` para usar desde la terminal

### ¿Qué verás durante la instalación?

```
▶ Verificando herramientas necesarias...
✓ Herramientas OK
▶ Consultando GitHub por la última versión...
✓ Versión más reciente: v0.1.0
▶ Descargando radlocal-v0.1.0-linux.tar.gz...
✓ Descarga completada
✓ Archivos extraídos
✓ Symlink creado en ~/.local/bin/radlocal
✓ Entrada del menú de aplicaciones creada
╔══════════════════════════════════════════════════════════╗
║  ✓ RadLocal v0.1.0 instalado exitosamente!            ║
╚══════════════════════════════════════════════════════════╝
```

---

## Instalación manual (alternativa)

Si prefieres descargar el script primero y ejecutarlo después:

```bash
# 1. Descarga el instalador
curl -fsSL https://raw.githubusercontent.com/TU_USUARIO/RadLocal/main/install.sh -o install.sh

# 2. Dale permisos de ejecución
chmod +x install.sh

# 3. Ejecútalo
./install.sh
```

---

## Cómo abrir RadLocal

Tienes tres formas de iniciarlo:

### Opción 1 – Menú de aplicaciones (más fácil)
Busca **"RadLocal"** en el menú de tu escritorio (igual que cualquier otra aplicación).

### Opción 2 – Desde la terminal
```bash
radlocal
```

> Si el comando no se reconoce, ejecuta primero:
> ```bash
> export PATH="$HOME/.local/bin:$PATH"
> ```
> Y para que sea permanente, agrega esa línea a tu `~/.bashrc` o `~/.zshrc`.

### Opción 3 – Desde el explorador de archivos
Navega a `~/.local/share/radlocal/` y haz doble clic en el archivo `radlocal`.

---

## Primera vez que abres RadLocal

1. **Autenticación con EVE Online** — Se abrirá tu navegador para que autorices a RadLocal a leer tu información de personaje. Acepta los permisos solicitados.
2. **Selecciona tu personaje** — Elige el personaje que usarás para el seguimiento.
3. **Ubica tus logs de intel** — Si RadLocal no los encuentra automáticamente, selecciona la carpeta de logs de EVE Online (normalmente `~/EVE/logs/Chatlogs/`).
4. ¡Listo! El mapa comenzará a actualizarse en tiempo real conforme lleguen mensajes de intel.

---

## Actualizaciones automáticas

Cada vez que abras RadLocal, el programa verificará si hay una nueva versión disponible. Si existe una actualización, descargará **únicamente los archivos modificados** (no el programa completo), por lo que las actualizaciones son rápidas.

---

## Desinstalación

Para quitar RadLocal de tu sistema:

```bash
rm -rf ~/.local/share/radlocal
rm -f ~/.local/bin/radlocal
rm -f ~/.local/share/applications/radlocal.desktop
```

---

## Solución de problemas

### "comando no encontrado: radlocal"
`~/.local/bin` no está en tu PATH. Agrega esto a tu `~/.bashrc`:
```bash
export PATH="$HOME/.local/bin:$PATH"
```
Luego ejecuta `source ~/.bashrc`.

### No se conecta a EVE Online / Error de autenticación
- Verifica tu conexión a internet.
- Asegúrate de que tu firewall no bloquee conexiones HTTPS.
- Intenta cerrar sesión desde el menú de RadLocal y vuelve a autenticarte.

### No detecta mensajes de intel
- Verifica que el cliente de EVE esté corriendo y que el canal de intel esté activo.
- Confirma que la ruta de los logs es correcta: `~/.local/share/radlocal/` → ajustes → carpeta de logs.

### El programa no abre (pantalla en negro o cierra solo)
Ejecuta desde la terminal para ver el error:
```bash
~/.local/share/radlocal/radlocal
```
Copia el mensaje de error y repórtalo en el repositorio de GitHub.

---

## Reportar un problema

Abre un issue en: `https://github.com/edwardjardy/RadLocal/issues`

Incluye:
- Tu distribución de Linux y versión
- El mensaje de error completo (si lo hay)
- Los pasos que realizaste antes del error
