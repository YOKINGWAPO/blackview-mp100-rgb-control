#!/usr/bin/env python3
"""
rgb_led.py - Control del RGB de la placa CYX (chip CH340) en Windows y Linux.

Replica el protocolo serie del programa "CYX RGB LED Control Tool":
  - Puerto serie del CH340 (VID 1A86 / PID 7523), detectado automaticamente.
  - 10000 baudios, 8 bits, sin paridad, 1 bit de stop.
  - Trama de 5 bytes: [250, modo, brillo, velocidad, checksum]
        brillo    = 6 - nivel(1..5)   (por defecto 3)
        velocidad = 6 - nivel(1..5)   (por defecto 3)
        checksum  = (suma de los 4 primeros bytes) & 0xFF
  - Cada byte se envia por separado con ~5 ms de separacion.

Uso:
    python rgb_led.py off          # apaga el RGB (por defecto)
    python rgb_led.py rainbow      # arcoiris
    python rgb_led.py breathing    # respiracion
    python rgb_led.py cycle        # ciclo de color
    python rgb_led.py auto         # automatico
    python rgb_led.py off -b 3 -s 3   # con brillo y velocidad concretos (1..5)
    python rgb_led.py off -p COM3     # forzar un puerto concreto
    python rgb_led.py --list          # listar puertos serie disponibles
"""

import argparse
import sys
import time

import serial
import serial.tools.list_ports

# Modos del LED (segun el programa original)
MODES = {
    "rainbow": 1,    # CaiHong  - arcoiris
    "breathing": 2,  # HuXi     - respiracion
    "cycle": 3,      # XunHuan  - ciclo de color
    "off": 4,        # guandeng - apagado
    "auto": 5,       # Auto     - automatico
}

CH340_VID = 0x1A86
CH340_PID = 0x7523
BAUDRATE = 10000


def find_port():
    """Devuelve el nombre del puerto serie del CH340, o None si no se encuentra."""
    for p in serial.tools.list_ports.comports():
        if p.vid == CH340_VID and p.pid == CH340_PID:
            return p.device
    # Reserva: por descripcion (algunos sistemas no exponen VID/PID)
    for p in serial.tools.list_ports.comports():
        desc = (p.description or "").lower()
        if "ch340" in desc or "wch" in desc:
            return p.device
    return None


def build_frame(mode, brightness=3, speed=3):
    """Construye la trama de 5 bytes con su checksum."""
    brightness = max(1, min(5, brightness))
    speed = max(1, min(5, speed))
    data = bytearray([250, mode, 6 - brightness, 6 - speed, 0])
    data[4] = sum(data[:4]) & 0xFF
    return data


def _set_custom_baudrate(fd, baudrate):
    """Fija una velocidad no estandar con el ioctl TCSETS2 de Linux."""
    import array
    import fcntl
    import termios

    tcgets2 = getattr(serial.serialposix, "TCGETS2", 0x802C542A)
    tcsets2 = getattr(serial.serialposix, "TCSETS2", 0x402C542B)
    bother = getattr(serial.serialposix, "BOTHER", 0o010000)

    buf = array.array("i", [0] * 64)
    fcntl.ioctl(fd, tcgets2, buf, True)
    buf[2] &= ~termios.CBAUD
    buf[2] |= bother
    buf[9] = baudrate   # c_ispeed
    buf[10] = baudrate  # c_ospeed
    fcntl.ioctl(fd, tcsets2, buf)


def open_port(port):
    """Abre el puerto a BAUDRATE.

    10000 baudios no es una velocidad estandar. La ruta que usa pyserial para
    aplicarla falla con EINVAL en Python 3.12 y anteriores, lo que rompe los
    ejecutables de PyInstaller compilados con esas versiones. En Linux se abre
    a una velocidad estandar y se fija la real con TCSETS2, que funciona con
    cualquier version de Python.
    """
    opts = dict(bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE, timeout=0.2)
    if not sys.platform.startswith("linux"):
        return serial.Serial(port=port, baudrate=BAUDRATE, **opts)

    sp = serial.Serial(port=port, baudrate=9600, **opts)
    try:
        _set_custom_baudrate(sp.fileno(), BAUDRATE)
    except Exception:
        # Reserva: si el ioctl no funciona (otra arquitectura), que lo intente
        # pyserial por su cuenta. Si tambien falla, la excepcion sube.
        sp.close()
        return serial.Serial(port=port, baudrate=BAUDRATE, **opts)
    return sp


def send_frame(port, frame):
    """Abre el puerto, envia la trama byte a byte y cierra."""
    sp = open_port(port)
    try:
        for b in frame:
            time.sleep(0.005)  # ~5 ms entre bytes
            sp.write(bytes([b]))
        sp.flush()
    finally:
        sp.close()


def main():
    parser = argparse.ArgumentParser(
        description="Control del RGB CYX (CH340) para Windows y Linux."
    )
    parser.add_argument(
        "mode", nargs="?", default="off", choices=list(MODES.keys()),
        help="modo del LED (por defecto: off)",
    )
    parser.add_argument("-b", "--brightness", type=int, default=3,
                        help="brillo 1..5 (por defecto 3)")
    parser.add_argument("-s", "--speed", type=int, default=3,
                        help="velocidad 1..5 (por defecto 3)")
    parser.add_argument("-p", "--port", default=None,
                        help="forzar puerto serie (ej. COM3 o /dev/ttyUSB0)")
    parser.add_argument("--list", action="store_true",
                        help="listar puertos serie y salir")
    args = parser.parse_args()

    if args.list:
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            print("No se encontraron puertos serie.")
        for p in ports:
            vidpid = ""
            if p.vid is not None:
                vidpid = " [VID_%04X PID_%04X]" % (p.vid, p.pid or 0)
            print("%s - %s%s" % (p.device, p.description, vidpid))
        return 0

    port = args.port or find_port()
    if not port:
        print("ERROR: no se encontro el dispositivo CH340 (RGB). "
              "Usa --list para ver los puertos o -p para indicar uno.",
              file=sys.stderr)
        return 1

    frame = build_frame(MODES[args.mode], args.brightness, args.speed)
    try:
        send_frame(port, frame)
    except serial.SerialException as e:
        print("ERROR abriendo/escribiendo en %s: %s" % (port, e), file=sys.stderr)
        return 1

    print("OK: modo '%s' enviado a %s (trama: %s)"
          % (args.mode, port, " ".join(str(b) for b in frame)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
