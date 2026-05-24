MODO_FUENTE = "simulador"
# Cambiar a "gpio" solo cuando este ejecutando el programa en raspberry o "serial" cuando se use la máquina real

GPIO_FUERZA_A = 22
GPIO_FUERZA_B = 23

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

# --- Chat ---
GEMINI_API_KEY = "AIzaSyCbbtgEH52QdSHc97exEVzXqmxOKmcB3BU"
GEMINI_MODEL = "gemini-1.5-flash"
CHAT_INSTRUCCIONES = """
Eres un asistente técnico para una interfaz de ensayos de tracción.
Responde en español, de forma clara y breve.
Ayuda a interpretar fuerza, desplazamiento, esfuerzo, deformación y resultados básicos.
Si faltan datos para responder algo, dilo claramente.
"""