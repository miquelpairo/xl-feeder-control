# XL Feeder Control

Control automático del motor del XL-Feeder (pre-purga) a partir del estado del NIR-Online SX-Center.

```
SX-Center (localhost:10034)  ──GET /1──▶  Node-RED  ──HTTP──▶  servidor_datalab.py (Flask, 127.0.0.1:5000)
                                                                      │ COM (pywin32)
                                                                      ▼
                                                        DataLab-IO USB  (driver ControlWeb.DrvAxDlUsb)
                                                          canal 100 = activación · canal 104 = velocidad
```

Node-RED lee el *LeadIn* del SX-Center; cuando faltan ≤ 10 s para medir arranca el motor, y lo para al acabar la medición o tras 180 s de seguridad. También hay arranque/paro manual y ajuste de velocidad desde el dashboard.

## Ficheros

| Fichero | Qué es |
|---|---|
| `flow_XL FEEDER control_14072026.json` | Flujo Node-RED (pestaña *XL Feeder Control*) |
| `servidor_datalab.py` | Servidor Flask que habla con el DataLab por COM |
| `arrancar_servidor.bat` | Arranca el servidor con consola (para depurar) |
| `arrancar_servidor_oculto.bat` | Arranca el servidor sin ventana (`pythonw`). Lleva la ruta de Python del PC donde se instaló: ajústala en cada equipo |
| `test_datalab.py` | Prueba manual de conexión: carga el `.par`, lee el canal 99 y activa el 100 |

## Requisitos

- Windows con el driver DataLab-IO (ControlWeb) instalado.
- **Python 3.13 de 32 bits** (el componente COM del driver es de 32 bits): `py -3.13-32`.
- `py -3.13-32 -m pip install flask pywin32`
- Carpeta `C:\XL Feeder Control\` con `dll.par` (configuración del DataLab de ese PC; no se versiona).

## API del servidor (solo escucha en 127.0.0.1)

| Método | Ruta | Cuerpo | Efecto |
|---|---|---|---|
| POST | `/activar` | — | Canal 100 a 9 V y velocidad fija a 6 V (`VELOCIDAD_ACTIVAR_V`) |
| POST | `/velocidad` | `{"velocidad": 0–10}` | Ajusta el canal 104. Fuera de rango o no numérico → 400 sin tocar la salida |
| POST | `/desactivar` | — | Canal 100 a 0 (la velocidad no se toca) |
| GET | `/estado` | — | `status`, `datalab` (`conectado` / `error` / `sin operaciones`) y el último error |
| GET | `/log` | — | Últimos 50 eventos |

Conversión: `counts = voltios × 400`. Logs diarios en `C:\XL Feeder Control\logs\` (se guardan 30 días).

## Notas

- Node-RED envía `{"velocidad": …}` también a `/activar`, pero el servidor la ignora y arranca siempre a 6 V; la velocidad del dashboard se aplica después vía `/velocidad`. Si se quiere arrancar directamente a la velocidad del flujo, hay que cambiarlo en `activar()` y probarlo en planta.
- `/desactivar` no pone la velocidad a 0.
