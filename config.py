import os

MODO_FUENTE = "simulador"
# Cambiar a "gpio" solo cuando este ejecutando el programa en raspberry o "serial" cuando se use la máquina real

#Slot de conexion a GPIO a raso}pberry para la fuerza
GPIO_FUERZA_A = 22
GPIO_FUERZA_B = 23

#Slot de conexion a GPIO a raspberry para la fuerza
GPIO_DESPLAZAMIENTO_A = 19
GPIO_DESPLAZAMIENTO_B = 21

PUERTO_SERIAL = "COM3"
# En Raspberry Pi normalmente es: "/dev/ttyUSB0"

BAUDRATE = 9600
TIMEOUT_SERIAL = 1.0

AREA_INICIAL = 12.0
# mm^2

LONGITUD_INICIAL = 50.0
# mm

INTERVALO_MS = 1000
MAX_PUNTOS_GRAFICA = 150
MAX_REGISTROS_MEMORIA = 5000

CARPETA_EXPORTACION = "exportados"
NOMBRE_BASE_CSV = "ensayo_traccion"

# Si pasan demasiados ciclos sin datos en modo serial,
# el sistema asume posible fin de ensayo o pérdida de conexión.
MAX_CICLOS_SIN_DATOS = 8

#Configuracion por defecto de escalas
ESCALAS_SENSOR = {
    "escala_1": {
        "nombre": "Escala 1",
        "factor_fuerza": 1.0,
        "factor_desplazamiento": 1.0
    },
    "escala_2": {
        "nombre": "Escala 2",
        "factor_fuerza": 2.0,
        "factor_desplazamiento": 0.5
    }
}

#Lista de materiales para la probeta
MATERIALES_PROBETA = {
    "acero": {
        "nombre": "Acero",
        "escala": "escala_2",
        "factor_fuerza": 2.0,
        "factor_desplazamiento": 1.0
    },
    "aluminio": {
        "nombre": "Aluminio",
        "escala": "escala_1",
        "factor_fuerza": 1.2,
        "factor_desplazamiento": 1.0
    },
    "cobre": {
        "nombre": "Cobre",
        "escala": "escala_1",
        "factor_fuerza": 1.3,
        "factor_desplazamiento": 1.0
    },
    "laton": {
        "nombre": "Latón",
        "escala": "escala_1",
        "factor_fuerza": 1.3,
        "factor_desplazamiento": 1.0
    },
    "titanio": {
        "nombre": "Titanio",
        "escala": "escala_2",
        "factor_fuerza": 2.2,
        "factor_desplazamiento": 1.0
    },
    "abs": {
        "nombre": "ABS",
        "escala": "escala_1",
        "factor_fuerza": 0.7,
        "factor_desplazamiento": 1.2
    },
    "pla": {
        "nombre": "PLA",
        "escala": "escala_1",
        "factor_fuerza": 0.8,
        "factor_desplazamiento": 1.2
    },
    "nylon": {
        "nombre": "Nylon",
        "escala": "escala_1",
        "factor_fuerza": 0.9,
        "factor_desplazamiento": 1.3
    },
    "fibra_carbono": {
        "nombre": "Fibra de carbono",
        "escala": "escala_2",
        "factor_fuerza": 2.5,
        "factor_desplazamiento": 0.9
    },
    "grafeno": {
        "nombre": "Grafeno",
        "escala": "escala_2",
        "factor_fuerza": 3.0,
        "factor_desplazamiento": 0.8
    }
}

# --- Chat ---
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = "gemini-2.0-flash"
CHAT_INSTRUCCIONES = """
Eres un asistente técnico para una interfaz de ensayos de tracción.
Responde en español, de forma clara y breve.
Ayuda a interpretar fuerza, desplazamiento, esfuerzo, deformación y resultados básicos.
Si faltan datos para responder algo, dilo claramente.
"""