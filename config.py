MODO_FUENTE = "simulador"
# Cambiar a "serial" cuando se use la máquina real

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
OPENAI_MODEL = "gpt-5"
CHAT_INSTRUCCIONES = """
Eres un asistente técnico para una interfaz de ensayos de tracción.
Responde en español, de forma clara y breve.
Ayuda a interpretar fuerza, desplazamiento, esfuerzo, deformación y resultados básicos.
Si faltan datos para responder algo, dilo claramente.
"""