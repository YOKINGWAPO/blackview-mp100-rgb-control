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
sudo ./setup-linux.sh        # una sola vez por equipo
./bin/RGBLedControl-linux
```

`setup-linux.sh` instala una regla udev para el chip CH340, añade tu usuario al
grupo del puerto serie (`dialout` o `uucp`, según la distribución) y da permiso
de ejecución al binario. **Sin ejecutarlo obtendrás `Permission denied`** al
aplicar cualquier modo, porque `/dev/ttyUSB*` no es accesible por defecto.

> Requiere **Ubuntu 22.04 / Debian 12 o posterior** (glibc 2.35+).
> En sistemas más antiguos, ejecuta la app desde el código fuente.

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

> **Nota sobre los 10000 baudios.** No es una velocidad estándar de Linux, y la
> vía que usa `pyserial` para aplicarla falla con `EINVAL` (error 22) en Python
> 3.12 y anteriores — lo que rompía los ejecutables de PyInstaller. Por eso el
> código abre el puerto a una velocidad estándar y fija la real con el `ioctl`
> `TCSETS2`, que funciona con cualquier versión de Python.

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

# Linux (instala python3-tk)
pyinstaller --onefile --name RGBLedControl-linux rgb_gui.py
```

> El binario de Linux es para **x64 (glibc)**. Para Raspberry Pi (ARM) hay que
> recompilarlo en un equipo ARM.

**Compila en la distribución más antigua que quieras soportar.** PyInstaller
enlaza con la glibc del sistema donde compilas y el resultado solo es compatible
hacia arriba: un binario hecho en Ubuntu 26.04 falla en 22.04 con
`version GLIBC_2.38 not found`. El binario que se distribuye aquí se compila en
un contenedor de Ubuntu 22.04:

```bash
docker run --rm -v "$PWD":/src:ro -v "$PWD/bin":/out ubuntu:22.04 bash -c '
  apt-get update -qq && apt-get install -y -qq python3-pip python3-tk binutils
  pip3 install -q pyinstaller pyserial
  cd /tmp && pyinstaller --onefile --name RGBLedControl-linux \
      --distpath /out --workpath /tmp/w --specpath /tmp /src/rgb_gui.py'
```

---

## Aviso

Proyecto no oficial, sin relación con Blackview ni con CYX. Se ofrece "tal cual",
sin garantías. Úsalo bajo tu responsabilidad.

## Licencia

[MIT](LICENSE)

---

_Proyecto de la comunidad para el Blackview MP100._
