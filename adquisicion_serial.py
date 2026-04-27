import time
import serial


class LectorSerialEnsayo:
    def __init__(self, puerto, baudrate, timeout=1.0):
        self.puerto = puerto
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        self.activo = False
        self.finalizado = False
        self.tiempo = 0
        self.ciclos_sin_datos = 0

    def conectar(self):
        if self.ser is None or not self.ser.is_open:
            self.ser = serial.Serial(
                port=self.puerto,
                baudrate=self.baudrate,
                timeout=self.timeout
            )

    def iniciar(self):
        self.conectar()
        self.activo = True
        self.finalizado = False

    def detener(self):
        self.activo = False

    def reset(self):
        self.detener()
        self.tiempo = 0
        self.finalizado = False
        self.ciclos_sin_datos = 0
        if self.ser is not None and self.ser.is_open:
            self.ser.close()
        self.ser = None

    def leer_dato(self):
        if not self.activo:
            return None

        try:
            self.conectar()
        except serial.SerialException:
            return None

        try:
            if self.ser.in_waiting <= 0:
                return None

            linea = self.ser.readline().decode("utf-8", errors="ignore").strip()
            if not linea:
                return None

            partes = linea.split(",")
            if len(partes) < 2:
                return None

            fuerza = float(partes[0])
            desplazamiento = float(partes[1])

            self.tiempo += 1
            self.ciclos_sin_datos = 0

            return {
                "tiempo": self.tiempo,
                "fuerza": round(fuerza, 3),
                "desplazamiento": round(desplazamiento, 3),
                "timestamp": round(time.time(), 3)
            }

        except (ValueError, serial.SerialException, OSError):
            return None