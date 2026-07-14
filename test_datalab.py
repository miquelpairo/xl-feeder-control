import sys, time, pythoncom
from win32com.client import dynamic
import win32com.client

RUTA_PAR = r"C:\XL Feeder Control\dll.par"

class DataLabEvents:
    def OnInputRead(self, CommunicationState, InputIndex, ErrorCode, Value):
        print(f"[EVENTO] Input leído -> índice={InputIndex} estado={CommunicationState} error={ErrorCode} valor={Value}")
    def OnOutputWritten(self, CommunicationState, OutputIndex, ErrorCode):
        print(f"[EVENTO] Output escrito -> índice={OutputIndex} estado={CommunicationState} error={ErrorCode}")

print("Conectando (dinámico puro, sin caché)...")
datalab = dynamic.Dispatch("ControlWeb.DrvAxDlUsb")
print("✓ Dispatch dinámico OK")

error_msg = ""
ok = datalab.LoadPARFile(RUTA_PAR, error_msg)
print("LoadPARFile:", ok)
if not ok:
    sys.exit()

print("Enlazando eventos...")
win32com.client.WithEvents(datalab, DataLabEvents)
print("✓ Eventos enlazados")

def bombear(segundos):
    fin = time.time() + segundos
    while time.time() < fin:
        pythoncom.PumpWaitingMessages()
        time.sleep(0.05)

print("\nLeyendo canal 99 ANTES...")
datalab.MarkInput(99)
datalab.ReadInputs()
bombear(1.5)

print("\nActivando canal 100 a 9V...")
datalab.MarkOutput(100, "9")
datalab.WriteOutputs()
bombear(1.5)

print("\nLeyendo canal 99 DURANTE activación...")
datalab.MarkInput(99)
datalab.ReadInputs()
bombear(1.5)

time.sleep(3)

print("\nDesactivando canal 100...")
datalab.MarkOutput(100, "0")
datalab.WriteOutputs()
bombear(1.5)

print("\nLeyendo canal 99 DESPUÉS...")
datalab.MarkInput(99)
datalab.ReadInputs()
bombear(1.5)

print("\nFin de la prueba.")