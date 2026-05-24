import time
from gpiozero import DigitalInputDevice


class LectorGPIOEnsayo:
    def __init__(self, pin_fuerza_a, pin_fuerza_b, pin_despl_a, pin_despl_b):
        self.pin_fuerza_a = DigitalInputDevice(pin_fuerza_a)
        self.pin_fuerza_b = DigitalInputDevice(pin_fuerza_b)
        self.pin_despl_a = DigitalInputDevice(pin_despl_a)
        self.pin_despl_b = DigitalInputDevice(pin_despl_b)

        self.tiempo = 0
        self.activo = False
        self.finalizado = False
        self.ciclos_sin_datos = 0

        self.contador_fuerza = 0
        self.contador_desplazamiento = 0

        self.estado_fuerza_anterior = self.pin_fuerza_a.value
        self.estado_despl_anterior = self.pin_despl_a.value

    def iniciar(self):
        self.activo = True
        self.finalizado = False

    def detener(self):
        self.activo = False

    def reset(self):
        self.tiempo = 0
        self.activo = False
        self.finalizado = False
        self.ciclos_sin_datos = 0
        self.contador_fuerza = 0
        self.contador_desplazamiento = 0

    def leer_dato(self):
        if not self.activo:
            return None

        estado_fuerza = self.pin_fuerza_a.value
        estado_despl = self.pin_despl_a.value

        if estado_fuerza != self.estado_fuerza_anterior:
            self.contador_fuerza += 1
            self.estado_fuerza_anterior = estado_fuerza

        if estado_despl != self.estado_despl_anterior:
            self.contador_desplazamiento += 1
            self.estado_despl_anterior = estado_despl

        self.tiempo += 1

        fuerza = self.contador_fuerza
        desplazamiento = self.contador_desplazamiento

        return {
            "tiempo": self.tiempo,
            "fuerza": round(fuerza, 3),
            "desplazamiento": round(desplazamiento, 3),
            "timestamp": round(time.time(), 3)
        }