# Blackview MP100 RGB Control

Aplicación portable (Windows y Linux) para controlar la iluminación **RGB** del
mini PC **Blackview MP100** sin depender del software de fábrica.

El programa original (*CYX RGB LED Control Tool*) **no guarda la configuración**:
en cada arranque el firmware vuelve a poner el efecto arcoíris y hay que apagarlo
a mano. Esta app permite aplicar el modo que quieras —incluido **apagado**—
y dejarlo configurado para que se aplique **automáticamente al iniciar el equipo**.

> Compatible con la placa RGB que usa el **chip CH340** (USB‑Serial,
> VID `1A86` / PID `7523`) y el software CYX. Probado en el **Blackview MP100**.

---

## Descargas (portables, no necesitan Python)

| Sistema | Archivo |
|---|---|
| Windows | [`bin/RGBLedControl-windows.exe`](bin/RGBLedControl-windows.exe) |
| Linux x64 | [`bin/RGBLedControl-linux`](bin/RGBLedControl-linux) |

### Windows
1. Ejecuta `RGBLedControl-windows.exe`.
2. Pulsa el modo deseado (p. ej. **Apagar**).
3. Marca **"Aplicar automáticamente"** y elige el modo para dejarlo fijo en cada arranque.

> Si aparece SmartScreen (por ser un `.exe` nuevo y sin firmar):
> *Más información → Ejecutar de todas formas*.

### Linux
```bash
chmod +x RGBLedControl-linux
sudo usermod -aG dialout $USER   # permiso al puerto serie (una vez; reinicia sesión)
./RGBLedControl-linux
```
La casilla **"Aplicar automáticamente"** crea el autoarranque en `~/.config/autostart/`.

---

## Funciones

- Modos: **Apagar, Arcoíris, Respiración, Ciclo, Auto**
- Ajuste de **brillo** y **velocidad** (1–5)
- Selección/refresco del **puerto serie**
- **Acción al arranque** configurable (elige qué modo aplicar)
- Recuerda la configuración (`config.json` en la carpeta de configuración del usuario)

> **Nota sobre el color:** el firmware de esta placa **no admite color personalizado**.
> Su protocolo solo contempla los 5 efectos predefinidos más brillo y velocidad
> (por eso el software de fábrica tampoco tiene selector de color).

---

## Uso por línea de comandos

Además de la GUI, `rgb_led.py` permite controlarlo desde terminal:

```bash
python rgb_led.py off          # apagar
python rgb_led.py rainbow      # arcoíris
python rgb_led.py breathing    # respiración
python rgb_led.py cycle        # ciclo de color
python rgb_led.py auto         # automático
python rgb_led.py off -b 3 -s 3   # brillo y velocidad (1..5)
python rgb_led.py --list          # listar puertos serie
```

---

## Protocolo (ingeniería inversa)

El software de fábrica es una app .NET que se comunica por **puerto serie** con
el chip CH340. Cada comando es una trama de **5 bytes**:

```
[ 0xFA , modo , brillo , velocidad , checksum ]
```

| Campo | Valor |
|---|---|
| Cabecera | `0xFA` (250) |
| modo | `1`=Arcoíris · `2`=Respiración · `3`=Ciclo · `4`=Apagar · `5`=Auto |
| brillo | `6 - nivel` (nivel 1..5) |
| velocidad | `6 - nivel` (nivel 1..5) |
| checksum | `(suma de los 4 primeros bytes) & 0xFF` |

**Puerto serie:** 10000 baudios, 8 bits, sin paridad, 1 bit de stop.
Los bytes se envían **uno a uno** con ~5 ms de separación.

Ejemplo (apagar, brillo 3, velocidad 3): `250, 4, 3, 3, 4`.

---

## Compilar desde el código

Requiere Python 3 con `tkinter` (incluido) y `pyserial`.

```bash
pip install pyserial
python rgb_gui.py        # ejecuta la interfaz
```

### Generar los portables con PyInstaller

```bash
pip install pyinstaller

# Windows
pyinstaller --onefile --noconsole --name RGBLedControl rgb_gui.py

# Linux (preferiblemente dentro de Linux/contenedor; instala python3-tk)
pyinstaller --onefile --name RGBLedControl-linux rgb_gui.py
```

> El binario de Linux es para **x64 (glibc)**. Para Raspberry Pi (ARM) hay que
> recompilarlo en un equipo ARM.

---

## Aviso

Proyecto no oficial, sin relación con Blackview ni con CYX. Se ofrece "tal cual",
sin garantías. Úsalo bajo tu responsabilidad.

## Licencia

[MIT](LICENSE)

---

_Proyecto de la comunidad para el Blackview MP100._
