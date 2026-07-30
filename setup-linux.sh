#!/usr/bin/env bash
#
# setup-linux.sh - Prepara un equipo Linux para usar RGBLedControl.
#
# Concede acceso al dispositivo RGB (chip CH340) sin necesidad de ejecutar la
# aplicacion como root. Solo hay que ejecutarlo una vez por equipo.
#
#   sudo ./setup-linux.sh
#
set -euo pipefail

VENDOR_ID="1a86"
PRODUCT_ID="7523"
UDEV_RULE="/etc/udev/rules.d/99-ch340-rgb.rules"
BINARY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/bin/RGBLedControl-linux"

info()  { printf '\033[1;34m::\033[0m %s\n' "$1"; }
ok()    { printf '\033[1;32mOK\033[0m %s\n' "$1"; }
warn()  { printf '\033[1;33m!!\033[0m %s\n' "$1"; }
fail()  { printf '\033[1;31mERROR\033[0m %s\n' "$1" >&2; exit 1; }

# --- 1. Comprobar privilegios ------------------------------------------------
if [ "$(id -u)" -ne 0 ]; then
    fail "Se necesita root para instalar la regla udev. Ejecuta: sudo $0"
fi

# --- 2. Identificar al usuario real (no root) --------------------------------
# Al usar sudo, $USER es root; el usuario de verdad viene en SUDO_USER.
TARGET_USER="${SUDO_USER:-}"
if [ -z "$TARGET_USER" ] || [ "$TARGET_USER" = "root" ]; then
    fail "No se pudo determinar el usuario. Ejecuta con: sudo $0 (no como root directo)."
fi
info "Configurando para el usuario: $TARGET_USER"

# --- 3. Elegir el grupo de puertos serie que exista en esta distribucion ------
# Debian/Ubuntu usan 'dialout'; Arch/Fedora/openSUSE usan 'uucp'.
SERIAL_GROUP=""
for group in dialout uucp; do
    if getent group "$group" >/dev/null 2>&1; then
        SERIAL_GROUP="$group"
        break
    fi
done
[ -n "$SERIAL_GROUP" ] || fail "No existe ni el grupo 'dialout' ni 'uucp'. Distribucion no reconocida."
info "Grupo de puerto serie detectado: $SERIAL_GROUP"

# --- 4. Instalar la regla udev -----------------------------------------------
# uaccess  -> ACL para el usuario de la sesion grafica activa (mecanismo moderno).
# GROUP    -> respaldo por si el sistema no usa systemd-logind.
cat > "$UDEV_RULE" <<EOF
# Blackview MP100 RGB - CH340 USB-Serial ($VENDOR_ID:$PRODUCT_ID)
# Generado por setup-linux.sh
SUBSYSTEM=="tty", ATTRS{idVendor}=="$VENDOR_ID", ATTRS{idProduct}=="$PRODUCT_ID", GROUP="$SERIAL_GROUP", MODE="0660", TAG+="uaccess"
EOF
ok "Regla udev instalada en $UDEV_RULE"

udevadm control --reload-rules
# La accion 'add' es la unica que ejecuta el builtin uaccess sobre un
# dispositivo ya conectado; con 'change' la ACL no se aplica.
udevadm trigger --action=add --subsystem-match=tty
ok "Reglas recargadas y aplicadas al dispositivo conectado"

# --- 5. Añadir el usuario al grupo (respaldo) --------------------------------
if id -nG "$TARGET_USER" | tr ' ' '\n' | grep -qx "$SERIAL_GROUP"; then
    ok "El usuario ya pertenece al grupo $SERIAL_GROUP"
else
    usermod -aG "$SERIAL_GROUP" "$TARGET_USER"
    ok "Usuario añadido al grupo $SERIAL_GROUP"
    warn "Ese cambio solo surte efecto tras cerrar sesion y volver a entrar."
fi

# --- 6. Dar permiso de ejecucion al binario ----------------------------------
if [ -f "$BINARY" ]; then
    chmod +x "$BINARY"
    ok "Permiso de ejecucion aplicado a bin/RGBLedControl-linux"
else
    warn "No se encontro $BINARY (¿ejecutas el script fuera de su carpeta?)"
fi

# --- 7. Comprobar que el dispositivo esta presente ---------------------------
echo
DEVICE="$(
    for dev in /sys/bus/usb/devices/*; do
        [ -f "$dev/idVendor" ] || continue
        if [ "$(cat "$dev/idVendor")" = "$VENDOR_ID" ] &&
           [ "$(cat "$dev/idProduct")" = "$PRODUCT_ID" ]; then
            echo "si"; break
        fi
    done
)"

if [ "$DEVICE" = "si" ]; then
    PORT="$(ls /dev/ttyUSB* 2>/dev/null | head -1 || true)"
    ok "Dispositivo CH340 detectado${PORT:+ en $PORT}"
    echo
    info "Listo. Ya puedes ejecutar: ./bin/RGBLedControl-linux"
else
    warn "No se detecta el dispositivo CH340 ($VENDOR_ID:$PRODUCT_ID)."
    warn "La configuracion queda instalada igualmente y se aplicara al conectarlo."
fi
