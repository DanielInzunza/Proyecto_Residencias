import time
import serial


class LectorSerialEnsayo:
    def __init__(self, puerto, baudrate):
        self.puerto = puerto
        self.baudrate = baudrate
        self.ser = None
        self.activo = False
        self.finalizado = False
        self.tiempo = 0

    def iniciar(self):
        if self.ser is None or not self.ser.is_open:
            self.ser = serial.Serial(self.puerto, self.baudrate, timeout=1)
        self.activo = True
        self.finalizado = False

    def detener(self):
        self.activo = False

    def reset(self):
        self.detener()
        self.tiempo = 0
        self.finalizado = False
        if self.ser is not None and self.ser.is_open:
            self.ser.close()
        self.ser = None

    def leer_dato(self):
        if not self.activo:
            return None

        if self.ser is None or not self.ser.is_open:
            return None

        if self.ser.in_waiting <= 0:
            return None

        try:
            linea = self.ser.readline().decode("utf-8").strip()
            if not linea:
                return None

            partes = linea.split(",")
            if len(partes) < 2:
                return None

            fuerza = float(partes[0])
            desplazamiento = float(partes[1])

            self.tiempo += 1

            return {
                "tiempo": self.tiempo,
                "fuerza": round(fuerza, 3),
                "desplazamiento": round(desplazamiento, 3),
                "timestamp": round(time.time(), 3)
            }

        except (ValueError, serial.SerialException, UnicodeDecodeError):
            return None