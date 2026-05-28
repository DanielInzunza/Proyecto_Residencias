import random
import time


class SimuladorEnsayo:
    def __init__(self):
        self.reset()

    def reset(self):
        self.tiempo = 0
        self.activo = False
        self.finalizado = False
        self.ciclos_sin_datos = 0

    def iniciar(self):
        if not self.finalizado:
            self.activo = True

    def detener(self):
        self.activo = False

    def leer_dato(self):
        """
        leer_dato:
             Esta funcion se utiliza para..
        Entrada :
        Salida :
        """
        if not self.activo or self.finalizado:
            return None

        self.tiempo += 1
        desplazamiento = self.tiempo * 0.12  # mm

        if self.tiempo <= 50:
            fuerza = 18 * (desplazamiento / 10) + random.uniform(-0.2, 0.2)
        elif self.tiempo <= 90:
            fuerza = 10.8 + 0.06 * (self.tiempo - 50) + random.uniform(-0.2, 0.2)
        elif self.tiempo <= 120:
            fuerza = 13.2 - 0.18 * (self.tiempo - 90) + random.uniform(-0.25, 0.25)
        else:
            self.activo = False
            self.finalizado = True
            return None

        fuerza = max(fuerza, 0)

        return {
            "tiempo": self.tiempo,
            "fuerza": round(fuerza, 3),
            "desplazamiento": round(desplazamiento, 3),
            "timestamp": round(time.time(), 3)
        }