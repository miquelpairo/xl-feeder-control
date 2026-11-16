from flask import Flask, request, jsonify
import pythoncom
from win32com.client import dynamic
import win32com.client
import time
from datetime import datetime
import logging
from logging.handlers import TimedRotatingFileHandler
import os

RUTA_PAR = r"C:\XL Feeder Control\dll.par"
CANAL_ACTIVACION = 100
CANAL_VELOCIDAD = 104

# Rango admisible de la salida analógica de velocidad (voltios)
VELOCIDAD_MIN_V = 0.0
VELOCIDAD_MAX_V = 10.0
# Velocidad fija que se aplica al activar (la del flujo se ajusta luego con /velocidad)
VELOCIDAD_ACTIVAR_V = 6

app = Flask(__name__)

# --- Registro de eventos en memoria, consultable por Node-RED ---
server_log = []
MAX_LOG = 50

LOG_DIR = r"C:\XL Feeder Control\logs"
os.makedirs(LOG_DIR, exist_ok=True)

file_logger = logging.getLogger("datalab_file")
file_logger.setLevel(logging.INFO)

file_handler = TimedRotatingFileHandler(
    filename=os.path.join(LOG_DIR, "servidor_datalab.log"),
    when="midnight",      # rota cada día a medianoche
    interval=1,
    backupCount=30,       # conserva 30 días, borra automáticamente lo más antiguo
    encoding="utf-8"
)
file_handler.setFormatter(logging.Formatter("%(asctime)s — %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
file_logger.addHandler(file_handler)

def log(mensaje):
    hora = datetime.now().strftime("%H:%M:%S")
    linea = f"{hora} — {mensaje}"
    server_log.insert(0, linea)
    del server_log[MAX_LOG:]
    try:
        print(linea)
    except Exception:
        pass
    file_logger.info(mensaje)   # <-- nueva línea: persiste a disco


class DataLabEvents:
    def OnInputRead(self, CommunicationState, InputIndex, ErrorCode, Value):
        log(f"[EVENTO] Input leído -> índice={InputIndex} estado={CommunicationState} error={ErrorCode} valor={Value}")
    def OnOutputWritten(self, CommunicationState, OutputIndex, ErrorCode):
        log(f"[EVENTO] Output escrito -> índice={OutputIndex} estado={CommunicationState} error={ErrorCode}")


log("Conectando al DataLab...")
datalab = dynamic.Dispatch("ControlWeb.DrvAxDlUsb")
error_msg = ""
ok = datalab.LoadPARFile(RUTA_PAR, error_msg)
if not ok:
    log(f"✗ ERROR al cargar el .par: {error_msg}")
    raise RuntimeError(f"No se pudo cargar el .par: {error_msg}")
log("✓ DataLab conectado y .par cargado")

win32com.client.WithEvents(datalab, DataLabEvents)
log("✓ Eventos enlazados")

log("=" * 50)
log(f"SERVIDOR INICIADO — PID {os.getpid()}")
log("=" * 50)



def bombear(segundos=0.5):
    fin = time.time() + segundos
    while time.time() < fin:
        pythoncom.PumpWaitingMessages()
        time.sleep(0.05)


def voltios_a_counts(voltios):
    return str(round(voltios * 400))


def validar_velocidad(valor):
    """Convierte a float y comprueba el rango. Lanza ValueError si no es válido."""
    try:
        v = float(valor)
    except (TypeError, ValueError):
        raise ValueError(f"velocidad no numérica: {valor!r}")
    if v != v or not (VELOCIDAD_MIN_V <= v <= VELOCIDAD_MAX_V):   # v != v -> NaN
        raise ValueError(f"velocidad fuera de rango ({VELOCIDAD_MIN_V}-{VELOCIDAD_MAX_V} V): {v}")
    return v


# Último resultado de comunicación con el DataLab (lo devuelve /estado)
estado_datalab = {"ultima_operacion": None, "ultimo_ok": None, "ultimo_error": None}


def registrar(ok, error=None):
    estado_datalab["ultima_operacion"] = datetime.now().isoformat(timespec="seconds")
    estado_datalab["ultimo_ok"] = ok
    estado_datalab["ultimo_error"] = None if ok else str(error)

@app.route('/activar', methods=['POST'])
def activar():
    data = request.get_json(silent=True) or {}
    try:
        datalab.MarkOutput(CANAL_ACTIVACION, voltios_a_counts(9))
        datalab.MarkOutput(CANAL_VELOCIDAD, voltios_a_counts(VELOCIDAD_ACTIVAR_V))
        datalab.WriteOutputs()
        bombear()
        registrar(True)
        log(f"Activado. Velocidad={VELOCIDAD_ACTIVAR_V}V (fija al activar)")
        return jsonify({"status": "ok", "velocidad": VELOCIDAD_ACTIVAR_V})
    except Exception as e:
        registrar(False, e)
        log(f"✗ ERROR en /activar: {e}")
        return jsonify({"status": "error", "detalle": str(e)}), 500

@app.route('/velocidad', methods=['POST'])
def set_velocidad():
    data = request.get_json(silent=True) or {}
    try:
        velocidad_v = validar_velocidad(data.get('velocidad', 3))
    except ValueError as e:
        log(f"✗ /velocidad rechazada: {e}")
        return jsonify({"status": "error", "detalle": str(e)}), 400
    try:
        datalab.MarkOutput(CANAL_VELOCIDAD, voltios_a_counts(velocidad_v))
        datalab.WriteOutputs()
        bombear()
        registrar(True)
        log(f"Velocidad ajustada a {velocidad_v}V")
        return jsonify({"status": "ok", "velocidad": velocidad_v})
    except Exception as e:
        registrar(False, e)
        log(f"✗ ERROR en /velocidad: {e}")
        return jsonify({"status": "error", "detalle": str(e)}), 500

@app.route('/desactivar', methods=['POST'])
def desactivar():
    try:
        datalab.MarkOutput(CANAL_ACTIVACION, "0")
        datalab.WriteOutputs()
        bombear()
        registrar(True)
        log("Desactivado.")
        return jsonify({"status": "ok"})
    except Exception as e:
        registrar(False, e)
        log(f"✗ ERROR en /desactivar: {e}")
        return jsonify({"status": "error", "detalle": str(e)}), 500


@app.route('/estado', methods=['GET'])
def estado():
    # "status" se mantiene igual (Node-RED solo mira que responda).
    # "datalab" refleja la última escritura: "conectado", "error" o "sin operaciones".
    if estado_datalab["ultimo_ok"] is None:
        dl = "sin operaciones"
    else:
        dl = "conectado" if estado_datalab["ultimo_ok"] else "error"
    return jsonify({"status": "servidor activo", "datalab": dl, **estado_datalab})


@app.route('/log', methods=['GET'])
def obtener_log():
    return jsonify(server_log)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, threaded=False)