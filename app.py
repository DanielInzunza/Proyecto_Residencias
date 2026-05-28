import math
from collections import deque
from datetime import datetime
import os

import pandas as pd
from dash import (
    Dash, dcc, html, dash_table,
    Input, Output, State, callback_context
)
import plotly.graph_objects as go
import google.generativeai as genai

from config import (
    MODO_FUENTE,
    PUERTO_SERIAL,
    BAUDRATE,
    TIMEOUT_SERIAL,
    LONGITUD_INICIAL,
    AREA_INICIAL,
    INTERVALO_MS,
    MAX_PUNTOS_GRAFICA,
    MAX_REGISTROS_MEMORIA,
    CARPETA_EXPORTACION,
    NOMBRE_BASE_CSV,
    MAX_CICLOS_SIN_DATOS,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    CHAT_INSTRUCCIONES,
    GPIO_FUERZA_A,
    GPIO_FUERZA_B,
    GPIO_DESPLAZAMIENTO_A,
    GPIO_DESPLAZAMIENTO_B,
    ESCALAS_SENSOR,
    MATERIALES_PROBETA,
)

from simulador import SimuladorEnsayo
from adquisicion_serial import LectorSerialEnsayo
from adquisicion_gpio import LectorGPIOEnsayo

#Configuracion de conexion serial y GPIO
def crear_fuente_datos():
    if MODO_FUENTE == "serial":
        return LectorSerialEnsayo(PUERTO_SERIAL, BAUDRATE, TIMEOUT_SERIAL)

    if MODO_FUENTE == "gpio":
        return LectorGPIOEnsayo(
            GPIO_FUERZA_A,
            GPIO_FUERZA_B,
            GPIO_DESPLAZAMIENTO_A,
            GPIO_DESPLAZAMIENTO_B
        )

    return SimuladorEnsayo()


fuente = crear_fuente_datos()
datos = deque(maxlen=MAX_REGISTROS_MEMORIA)
ultimo_archivo_guardado = {"ruta": None}

app = Dash(__name__)
app.title = "Ensayo de Tracción"

TEMA_CLARO = {
    "fondo": "#ffffff",
    "texto": "#111827",
    "panel": "#fcfcfc",
    "borde": "#d9d9d9",
    "tabla_header": "#f3f4f6",
    "tabla_cell": "#ffffff",
    "plotly": "plotly_white",
}

TEMA_OSCURO = {
    "fondo": "#111827",
    "texto": "#f3f4f6",
    "panel": "#1f2937",
    "borde": "#374151",
    "tabla_header": "#374151",
    "tabla_cell": "#1f2937",
    "plotly": "plotly_dark",
}

tema_actual = {"valor": "claro"}

genai.configure(api_key=GEMINI_API_KEY)

modelo_gemini = genai.GenerativeModel(GEMINI_MODEL)


def asegurar_carpeta_exportacion():
    os.makedirs(CARPETA_EXPORTACION, exist_ok=True)


def generar_nombre_csv():
    marca_tiempo = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(CARPETA_EXPORTACION, f"{NOMBRE_BASE_CSV}_{marca_tiempo}.csv")


#Calculo de variables en base al diametro y la longitud 
def calcular_variables(df, diametro=4.0, longitud=50.0):
    if df.empty:
        return df

    df = df.copy()

    try:
        diametro = float(diametro)
    except:
        diametro = 4.0

    try:
        longitud = float(longitud)
    except:
        longitud = 50.0

    if diametro <= 0:
        diametro = 4.0

    if longitud <= 0:
        longitud = 50.0

    # Área circular de la probeta
    area = math.pi * (diametro ** 2) / 4

    # Cálculos mecánicos
    df["deformacion"] = df["desplazamiento"] / longitud
    df["esfuerzo"] = df["fuerza"] / area

    df["deformacion"] = df["deformacion"].round(6)
    df["esfuerzo"] = df["esfuerzo"].round(6)

    return df


def guardar_csv_automatico():
    if len(datos) == 0:
        return None

    asegurar_carpeta_exportacion()
    ruta = generar_nombre_csv()

    df = pd.DataFrame(datos)
    df = calcular_variables(df)
    df.to_csv(ruta, index=False, encoding="utf-8")

    ultimo_archivo_guardado["ruta"] = ruta
    return ruta


def crear_figura_fuerza_desplazamiento(df):
    fig = go.Figure()

    if not df.empty:
        fig.add_trace(
            go.Scatter(
                x=df["desplazamiento"],
                y=df["fuerza"],
                mode="lines+markers",
                name="Tolque vs Deformacion angular"
            )
        )

    fig.update_layout(
        title="Tolque vs Deformacion angular",
        xaxis_title="Deformacion (grados)",
        yaxis_title="Tolque (Kg/cm)",
        template=TEMA_OSCURO["plotly"] if tema_actual["valor"] == "oscuro" else TEMA_CLARO["plotly"],
        height=320,
        autosize=True,
        margin=dict(l=40, r=20, t=60, b=40)
    )
    return fig


def crear_figura_esfuerzo_deformacion(df):
    fig = go.Figure()

    if not df.empty:
        fig.add_trace(
            go.Scatter(
                x=df["deformacion"],
                y=df["esfuerzo"],
                mode="lines+markers",
                name="Esfuerzo vs deformación"
            )
        )

    fig.update_layout(
        title="Esfuerzo vs deformación",
        xaxis_title="Deformación",
        yaxis_title="Esfuerzo (N/mm²)",
        template=TEMA_OSCURO["plotly"] if tema_actual["valor"] == "oscuro" else TEMA_CLARO["plotly"],
        height=320,
        autosize=True,
        margin=dict(l=40, r=20, t=60, b=40)
    )
    return fig


def obtener_resultados(df):
    if df.empty:
        return {
            "fuerza_max": 0,
            "desplazamiento_max": 0,
            "esfuerzo_max": 0,
            "deformacion_max": 0,
            "total_muestras": 0,
            "ultimo_tiempo": 0
        }

    ultima = df.iloc[-1]
    return {
        "fuerza_max": round(df["fuerza"].max(), 3),
        "desplazamiento_max": round(df["desplazamiento"].max(), 3),
        "esfuerzo_max": round(df["esfuerzo"].max(), 6),
        "deformacion_max": round(df["deformacion"].max(), 6),
        "total_muestras": int(len(df)),
        "ultimo_tiempo": round(float(ultima["tiempo"]), 3)
    }


def obtener_estado_texto():
    if getattr(fuente, "finalizado", False):
        return "FINALIZADO"
    if getattr(fuente, "activo", False):
        return "EN EJECUCIÓN"
    return "DETENIDO"


def tarjeta_resultado(titulo, valor):
    return html.Div(
        style={
            "border": "1px solid #d9d9d9",
            "borderRadius": "8px",
            "padding": "12px",
            "backgroundColor": "#fafafa"
        },
        children=[
            html.Div(titulo, style={"fontSize": "13px", "color": "#555"}),
            html.Div(valor, style={"fontSize": "20px", "fontWeight": "bold", "marginTop": "6px"})
        ]
    )


def construir_panel_resultados(df):
    resultados = obtener_resultados(df)
    return html.Div(
        style={
            "display": "grid",
            "gridTemplateColumns": "repeat(3, minmax(160px, 1fr))",
            "gap": "12px"
        },
        children=[
            tarjeta_resultado("Fuerza máxima", f"{resultados['fuerza_max']} N"),
            tarjeta_resultado("Desplazamiento máximo", f"{resultados['desplazamiento_max']} mm"),
            tarjeta_resultado("Esfuerzo máximo", f"{resultados['esfuerzo_max']} N/mm²"),
            tarjeta_resultado("Deformación máxima", f"{resultados['deformacion_max']}"),
            tarjeta_resultado("Muestras", f"{resultados['total_muestras']}"),
            tarjeta_resultado("Último tiempo", f"{resultados['ultimo_tiempo']} s"),
        ]
    )


def resumen_contexto_para_chat(df):
    if df.empty:
        return "No hay datos del ensayo todavía."

    ult = df.iloc[-1]
    res = obtener_resultados(df)

    return f"""
Estado del sistema: {obtener_estado_texto()}
Último dato:
- tiempo: {ult['tiempo']} s
- fuerza: {ult['fuerza']} N
- desplazamiento: {ult['desplazamiento']} mm
- deformación: {ult['deformacion']}
- esfuerzo: {ult['esfuerzo']} N/mm²

Resultados acumulados:
- fuerza máxima: {res['fuerza_max']} N
- desplazamiento máximo: {res['desplazamiento_max']} mm
- esfuerzo máximo: {res['esfuerzo_max']} N/mm²
- deformación máxima: {res['deformacion_max']}
- total de muestras: {res['total_muestras']}
"""


def consultar_gemini(pregunta, df):

    contexto = resumen_contexto_para_chat(df)

    prompt = f"""
    {CHAT_INSTRUCCIONES}

    Contexto del ensayo:
    {contexto}

    Pregunta del usuario:
    {pregunta}
    """

    respuesta = modelo_gemini.generate_content(prompt)

    return respuesta.text


def render_chat(historial):
    bloques = []
    for msg in historial:
        es_usuario = msg["role"] == "user"
        bloques.append(
            html.Div(
                style={
                    "marginBottom": "10px",
                    "display": "flex",
                    "justifyContent": "flex-end" if es_usuario else "flex-start"
                },
                children=[
                    html.Div(
                        msg["content"],
                        style={
                            "maxWidth": "85%",
                            "padding": "10px",
                            "borderRadius": "10px",
                            "backgroundColor": "#dbeafe" if es_usuario else "#f3f4f6",
                            "whiteSpace": "pre-wrap"
                        }
                    )
                ]
            )
        )
    return bloques


app.layout = html.Div(
    id="contenedor-app",
    style={"fontFamily": "Arial", "margin": "16px"},
    children=[
        html.Button(
            "🌙",
            id="btn-tema",
            n_clicks=0,
            title="Cambiar tema",
            style={
                "position": "fixed",
                "top": "16px",
                "right": "16px",
                "width": "52px",
                "height": "52px",
                "borderRadius": "50%",
                "border": "1px solid #d9d9d9",
                "backgroundColor": "#ffffff",
                "fontSize": "22px",
                "cursor": "pointer",
                "zIndex": "2000",
                "boxShadow": "0 4px 12px rgba(0,0,0,0.2)"
            }
        ),
        html.H1("Sistema de adquisición y visualización de datos"),
        html.Div(f"Fuente: {MODO_FUENTE}", style={"marginBottom": "14px", "color": "#444"}),

        html.Div(
            id="contenedor-principal",
            style={"display": "grid", "gridTemplateColumns": "3fr 1.2fr", "gap": "18px"},
            children=[
                html.Div(
                    children=[
                        html.Div(
                            style={
                                "display": "flex",
                                "gap": "10px",
                                "flexWrap": "wrap",
                                "marginBottom": "18px"
                            },
                            children=[
                                html.Button("Iniciar", id="btn-iniciar", n_clicks=0, style={"padding": "10px 16px"}),
                                html.Button("Detener", id="btn-detener", n_clicks=0, style={"padding": "10px 16px"}),
                                html.Button("Reiniciar", id="btn-reiniciar", n_clicks=0, style={"padding": "10px 16px"}),
                                html.Button("Guardar CSV", id="btn-guardar", n_clicks=0, style={"padding": "10px 16px"}),
                                html.Button("Descargar último CSV", id="btn-descargar", n_clicks=0, style={"padding": "10px 16px"}),
                            ]
                        ),

                        html.Div(
                            id="panel-estado",
                            style={
                                "display": "grid",
                                "gridTemplateColumns": "1fr 2fr",
                                "gap": "16px",
                                "marginBottom": "20px"
                            },
                            children=[
                                html.Div(
                                    style={
                                        "border": "1px solid #d9d9d9",
                                        "borderRadius": "8px",
                                        "padding": "16px",
                                        "backgroundColor": "#fcfcfc"
                                    },
                                    children=[
                                        html.H3("Estado del sistema"),
                                        html.Div(id="estado-sistema", style={"fontSize": "22px", "fontWeight": "bold"}),
                                        html.Hr(),
                                        html.Div(id="mensaje-accion", style={"fontWeight": "bold", "marginBottom": "10px"}),
                                        html.Div(id="indicadores"),

                                        html.Hr(),

                                        html.Div(
                                            children=[
                                                html.Div(
                                                    "Cambiar escala:",
                                                    style={
                                                        "fontWeight": "bold",
                                                        "marginBottom": "8px"
                                                    }
                                                ),

                                                dcc.RadioItems(
                                                    id="selector-escala",
                                                    options=[
                                                        {"label": "Escala 1", "value": "escala_1"},
                                                        {"label": "Escala 2", "value": "escala_2"},
                                                    ],
                                                    value="escala_1",
                                                    labelStyle={
                                                        "display": "block",
                                                        "marginBottom": "6px"
                                                    },
                                                    inputStyle={
                                                        "marginRight": "8px"
                                                    }
                                                )
                                            ],
                                            style={
                                                "marginTop": "12px"
                                            }
                                        )
                                    ]
                                ),

                                html.Div(
                                    id="panel-resumen",
                                    style={
                                        "border": "1px solid #d9d9d9",
                                        "borderRadius": "8px",
                                        "padding": "16px",
                                        "backgroundColor": "#fcfcfc",
                                        "minWidth": "0",
                                        "overflow": "hidden",
                                    },
                                    children=[
                                        dcc.Tabs(
                                            id="tabs-resumen-probeta",
                                            value="tab-resumen",
                                            children=[
                                                dcc.Tab(
                                                    label="Resumen del ensayo",
                                                    value="tab-resumen",
                                                    children=[
                                                        html.Div(
                                                            style={"padding": "12px 0"},
                                                            children=[
                                                                html.Div(id="panel-resultados")
                                                            ]
                                                        )
                                                    ]
                                                ),
                                                dcc.Tab(
                                                    label="Probeta",
                                                    value="tab-probeta",
                                                    children=[
                                                        html.Div(
                                                            style={"padding": "12px 0"},
                                                            children=[
                                                                html.Label("Tipo de material"),
                                                                dcc.Dropdown(
                                                                    id="selector-material",
                                                                    options=[
                                                                        {"label": datos_material["nombre"], "value": clave}
                                                                        for clave, datos_material in MATERIALES_PROBETA.items()
                                                                    ],
                                                                    value="acero",
                                                                    clearable=False,
                                                                    style={
                                                                        "width": "100%",
                                                                        "marginBottom": "12px",
                                                                        "color": "#111827"
                                                                    }
                                                                ),

                                                                html.Label("Diámetro"),
                                                                dcc.Input(
                                                                    id="input-diametro",
                                                                    type="text",
                                                                    placeholder="Ejemplo: 12.5 mm",
                                                                    style={
                                                                        "width": "100%",
                                                                        "padding": "8px",
                                                                        "marginBottom": "12px"
                                                                    }
                                                                ),

                                                                html.Label("Longitud"),
                                                                dcc.Input(
                                                                    id="input-longitud",
                                                                    type="text",
                                                                    placeholder="Ejemplo: 50 mm",
                                                                    style={
                                                                        "width": "100%",
                                                                        "padding": "8px",
                                                                        "marginBottom": "12px"
                                                                    }
                                                                ),
                                                            ]
                                                        )
                                                    ]
                                                )
                                            ]
                                        )
                                    ]
                                )
                            ]
                        ),

                        html.Div(
                            style={
                                "display": "grid",
                                "gridTemplateColumns": "repeat(2, minmax(0, 1fr))",
                                "gap": "16px",
                                "width": "100%",
                                "overflow": "hidden"
                            },
                            children=[
                                dcc.Graph(
                                    id="grafica-fuerza-desplazamiento",
                                    config={"responsive": True},
                                    style={"width": "100%"}
                                ),
                                dcc.Graph(
                                    id="grafica-esfuerzo-deformacion",
                                    config={"responsive": True},
                                    style={"width": "100%"}
)
                            ]
                        ),

                        html.H3("Datos del ensayo", style={"marginTop": "20px"}),
                        dash_table.DataTable(
                            id="tabla-datos",
                            columns=[
                                {"name": "Tiempo", "id": "tiempo"},
                                {"name": "Fuerza (N)", "id": "fuerza"},
                                {"name": "Desplazamiento (mm)", "id": "desplazamiento"},
                                {"name": "Deformación", "id": "deformacion"},
                                {"name": "Esfuerzo (N/mm²)", "id": "esfuerzo"},
                                {"name": "Timestamp", "id": "timestamp"},
                            ],
                            data=[],
                            page_action="none",
                            fixed_rows={"headers": True},
                            style_table={
                                "overflowX": "auto",
                                "overflowY": "auto",
                                "height": "430px"
                            },
                            style_cell={
                                "textAlign": "center",
                                "padding": "8px",
                                "backgroundColor": "#ffffff",
                                "color": "#111827"
                            },
                            style_header={
                                "fontWeight": "bold",
                                "backgroundColor": "#f3f4f6",
                                "color": "#111827"
                            }
                        )
                    ]
                ),

                html.Div(
                    id="contenedor-chat-lateral",
                    style={
                        "display": "flex",
                        "alignItems": "flex-start",
                        "gap": "0px"
                    },
                    children=[
                        html.Button(
                            "▶",
                            id="btn-toggle-chat",
                            n_clicks=0,
                            style={
                                "height": "48px",
                                "width": "32px",
                                "border": "1px solid #d9d9d9",
                                "borderRight": "0px",
                                "borderRadius": "8px 0 0 8px",
                                "backgroundColor": "#fcfcfc",
                                "cursor": "pointer",
                                "fontSize": "18px",
                                "fontWeight": "bold",
                                "marginTop": "0px"
                            }
                        ),

                        html.Div(
                            id="panel-chat",
                            style={
                                "border": "1px solid #d9d9d9",
                                "borderRadius": "0 8px 8px 8px",
                                "padding": "14px",
                                "backgroundColor": "#fcfcfc",
                                "height": "calc(100vh - 120px)",
                                "display": "flex",
                                "flexDirection": "column",
                                "minWidth": "320px",
                                "width": "100%",
                                "boxSizing": "border-box",
                                "overflow": "hidden"
                            },
                            children=[
                                html.H3("Asistente técnico"),
                                html.Div(
                                    "Puedes preguntar sobre los datos del ensayo, esfuerzo, deformación o interpretación básica.",
                                    style={"fontSize": "14px", "color": "#555", "marginBottom": "10px"}
                                ),
                                html.Div(
                                    id="chat-box",
                                    style={
                                        "flex": "1",
                                        "overflowY": "auto",
                                        "border": "1px solid #e5e7eb",
                                        "borderRadius": "8px",
                                        "padding": "10px",
                                        "backgroundColor": "white",
                                        "marginBottom": "10px"
                                    }
                                ),
                                dcc.Textarea(
                                    id="chat-input",
                                    placeholder="Escribe tu pregunta...",
                                    style={
                                        "width": "100%",
                                        "height": "90px",
                                        "resize": "none",
                                        "marginBottom": "8px"
                                    }
                                ),
                                html.Button(
                                    "Enviar pregunta",
                                    id="btn-chat",
                                    n_clicks=0,
                                    style={"padding": "10px"}
                                ),
                            ]
                        )
                    ]
                )
            ]
        ),

        html.Button(
            "⚙",
            id="btn-configuracion",
            n_clicks=0,
            title="Configuración avanzada",
            style={
                "position": "fixed",
                "left": "18px",
                "bottom": "18px",
                "width": "52px",
                "height": "52px",
                "borderRadius": "50%",
                "border": "1px solid #d9d9d9",
                "backgroundColor": "#111827",
                "color": "white",
                "fontSize": "24px",
                "cursor": "pointer",
                "zIndex": "1001",
                "boxShadow": "0 4px 12px rgba(0,0,0,0.25)"
            }
        ),

        html.Div(
            id="panel-configuracion",
            style={
                "position": "fixed",
                "left": "18px",
                "bottom": "84px",
                "width": "320px",
                "padding": "18px",
                "border": "1px solid #d9d9d9",
                "borderRadius": "12px",
                "backgroundColor": "#ffffff",
                "boxShadow": "0 8px 24px rgba(0,0,0,0.25)",
                "zIndex": "1000",
                "display": "none"
            },
            children=[
                html.H3(
                    "Configuración avanzada",
                    style={"marginTop": "0px"}
                ),

                html.Label("Factor a"),
                dcc.Input(
                    id="input-factor-a",
                    type="text",
                    value=1.0,
                    placeholder="Ingrese Factor a",
                    style={
                        "width": "100%",
                        "padding": "8px",
                        "marginBottom": "12px"
                    }
                ),

                html.Label("Factor b"),
                dcc.Input(
                    id="input-factor-b",
                    type="text",
                    value=1.0,
                    placeholder="Ingrese Factor b",
                    style={
                        "width": "100%",
                        "padding": "8px",
                        "marginBottom": "12px"
                    }
                ),

                html.Div(
                    "Estos parámetros aún no afectan los cálculos del sistema.",
                    style={
                        "fontSize": "13px",
                        "color": "#666",
                        "marginTop": "8px"
                    }
                )
            ]
        ),

        dcc.Interval(id="intervalo-actualizacion", interval=INTERVALO_MS, n_intervals=0),
        dcc.Store(id="store-mensaje", data=""),
        dcc.Store(id="store-chat", data=[]),
        dcc.Store(id="store-chat-visible", data=True, storage_type="local"),
        dcc.Store(id="store-config-visible", data=False),
        dcc.Store(id="store-tema", data="claro", storage_type="local"),
        dcc.Download(id="descarga-csv")
    ]
)


@app.callback(
    Output("store-mensaje", "data"),
    Input("btn-iniciar", "n_clicks"),
    Input("btn-detener", "n_clicks"),
    Input("btn-reiniciar", "n_clicks"),
    Input("btn-guardar", "n_clicks"),
    prevent_initial_call=True
)
def manejar_botones(n_iniciar, n_detener, n_reiniciar, n_guardar):
    ctx = callback_context
    if not ctx.triggered:
        return ""

    boton = ctx.triggered[0]["prop_id"].split(".")[0]

    if boton == "btn-iniciar":
        try:
            fuente.iniciar()
            return "Ensayo iniciado."
        except Exception as e:
            return f"Error al iniciar: {e}"

    if boton == "btn-detener":
        try:
            fuente.detener()
            return "Ensayo detenido."
        except Exception as e:
            return f"Error al detener: {e}"

    if boton == "btn-reiniciar":
        try:
            fuente.reset()
            datos.clear()
            ultimo_archivo_guardado["ruta"] = None
            return "Ensayo reiniciado. Datos en memoria borrados."
        except Exception as e:
            return f"Error al reiniciar: {e}"

    if boton == "btn-guardar":
        try:
            ruta = guardar_csv_automatico()
            if ruta is None:
                return "No hay datos para guardar."
            return f"CSV guardado en: {ruta}"
        except Exception as e:
            return f"Error al guardar CSV: {e}"

    return ""


@app.callback(
    Output("descarga-csv", "data"),
    Input("btn-descargar", "n_clicks"),
    prevent_initial_call=True
)
def descargar_csv(n_clicks):
    ruta = ultimo_archivo_guardado["ruta"]
    if ruta and os.path.exists(ruta):
        return dcc.send_file(ruta)
    return None


@app.callback(
    Output("grafica-fuerza-desplazamiento", "figure"),
    Output("grafica-esfuerzo-deformacion", "figure"),
    Output("tabla-datos", "data"),
    Output("estado-sistema", "children"),
    Output("indicadores", "children"),
    Output("panel-resultados", "children"),
    Output("mensaje-accion", "children"),
    Input("intervalo-actualizacion", "n_intervals"),
    State("store-mensaje", "data"),
    State("selector-escala", "value"),
    State("selector-material", "value"),
    State("input-diametro", "value"),
    State("input-longitud", "value"),
    State("input-factor-a", "value"),
    State("input-factor-b", "value")
)
def actualizar_interfaz(n_intervals, mensaje, escala_seleccionada, material_seleccionado, diametro_probeta, longitud_probeta, factor_a, factor_b):
    nuevo_dato = fuente.leer_dato()

    try:
        factor_a = float(factor_a)
    except:
        factor_a = 1.0

    try:
        factor_b = float(factor_b)
    except:
        factor_b = 1.0

    if factor_a <= 0:
        factor_a = 1.0

    if factor_b <= 0:
        factor_b = 1.0

    if nuevo_dato is not None:

        material = MATERIALES_PROBETA.get(
            material_seleccionado,
            MATERIALES_PROBETA["acero"]
        )

        # Escala/material
        fuerza = (
            nuevo_dato["fuerza"]
            * material["factor_fuerza"]
        )

        desplazamiento = (
            nuevo_dato["desplazamiento"]
            * material["factor_desplazamiento"]
        )

        # Factores de calibración
        fuerza *= factor_a
        desplazamiento *= factor_b

        nuevo_dato["fuerza"] = round(fuerza, 3)
        nuevo_dato["desplazamiento"] = round(desplazamiento, 3)

    if nuevo_dato is not None:
        escala = ESCALAS_SENSOR.get(escala_seleccionada, ESCALAS_SENSOR["escala_1"])

        nuevo_dato["fuerza"] = round(
            nuevo_dato["fuerza"] * escala["factor_fuerza"],
            3
        )

        nuevo_dato["desplazamiento"] = round(
            nuevo_dato["desplazamiento"] * escala["factor_desplazamiento"],
            3
        )

    if nuevo_dato is not None:
        datos.append(nuevo_dato)
        if hasattr(fuente, "ciclos_sin_datos"):
            fuente.ciclos_sin_datos = 0
    else:
        if getattr(fuente, "activo", False) and hasattr(fuente, "ciclos_sin_datos"):
            fuente.ciclos_sin_datos += 1

    if (
        MODO_FUENTE == "serial"
        and getattr(fuente, "activo", False)
        and hasattr(fuente, "ciclos_sin_datos")
        and fuente.ciclos_sin_datos >= MAX_CICLOS_SIN_DATOS
        and len(datos) > 0
    ):
        fuente.activo = False
        fuente.finalizado = True
        if ultimo_archivo_guardado["ruta"] is None:
            ruta = guardar_csv_automatico()
            mensaje = f"Ensayo finalizado automáticamente. CSV guardado en: {ruta}"

    if getattr(fuente, "finalizado", False) and ultimo_archivo_guardado["ruta"] is None and len(datos) > 0:
        ruta = guardar_csv_automatico()
        mensaje = f"Ensayo finalizado. CSV exportado automáticamente en: {ruta}"

    if len(datos) == 0:
        df = pd.DataFrame(columns=["tiempo", "fuerza", "desplazamiento", "timestamp"])
    else:
        df = pd.DataFrame(datos)

    df = calcular_variables(
        df,
        diametro=diametro_probeta,
        longitud=longitud_probeta
    )
    df_grafica = df.tail(MAX_PUNTOS_GRAFICA) if not df.empty else df

    fig_1 = crear_figura_fuerza_desplazamiento(df_grafica)
    fig_2 = crear_figura_esfuerzo_deformacion(df_grafica)

    estado = obtener_estado_texto()

    if estado == "EN EJECUCIÓN":
        estado_elemento = html.Div(
            estado,
            className="estado-ejecucion",
            style={
                "fontSize": "22px",
                "fontWeight": "bold"
            }
        )

    elif estado == "DETENIDO":
        estado_elemento = html.Div(
            estado,
            className="estado-detenido",
            style={
                "fontSize": "22px",
                "fontWeight": "bold"
            }
        )

    elif estado == "FINALIZADO":
        estado_elemento = html.Div(
            estado,
            style={
                "fontSize": "22px",
                "fontWeight": "bold",
                "color": "#2563eb"
            }
        )

    else:
        estado_elemento = html.Div(
            estado,
            style={
                "fontSize": "22px",
                "fontWeight": "bold"
        }
    )

    if df.empty:
        indicadores = "Sin datos disponibles."
        panel = html.Div("Aún no hay resultados.")
        tabla = []
    else:
        ultimo = df.iloc[-1]
        indicadores = (
            f"Último dato | Tiempo: {ultimo['tiempo']} s | "
            f"Fuerza: {ultimo['fuerza']} N | "
            f"Desplazamiento: {ultimo['desplazamiento']} mm | "
            f"Deformación: {ultimo['deformacion']} | "
            f"Esfuerzo: {ultimo['esfuerzo']} N/mm²"
        )
        panel = construir_panel_resultados(df)
        tabla = df[
            ["tiempo", "fuerza", "desplazamiento", "deformacion", "esfuerzo", "timestamp"]
        ].to_dict("records")

    return fig_1, fig_2, tabla, estado_elemento, indicadores, panel, mensaje


@app.callback(
    Output("store-chat", "data"),
    Output("chat-input", "value"),
    Input("btn-chat", "n_clicks"),
    State("chat-input", "value"),
    State("store-chat", "data"),
    State("input-diametro", "value"),
    State("input-longitud", "value"),
    prevent_initial_call=True
)
def enviar_pregunta_chat(n_clicks, pregunta, historial):
    historial = historial or []

    if not pregunta or not pregunta.strip():
        return historial, ""

    historial.append({"role": "user", "content": pregunta.strip()})

    if len(datos) == 0:
        df = pd.DataFrame(columns=["tiempo", "fuerza", "desplazamiento", "timestamp"])
    else:
        df = pd.DataFrame(datos)

    df = calcular_variables(
        df,
        diametro=diametro_probeta,
        longitud=longitud_probeta
    )

    try:
        respuesta = consultar_gemini(pregunta.strip(), df)
    except Exception as e:
        respuesta = f"No se pudo consultar el modelo: {e}"

    historial.append({"role": "assistant", "content": respuesta})
    return historial, ""


@app.callback(
    Output("chat-box", "children"),
    Input("store-chat", "data")
)
def actualizar_chat(historial):
    historial = historial or [
        {
            "role": "assistant",
            "content": "Hola. Puedo ayudarte a interpretar el ensayo y los datos mostrados en pantalla."
        }
    ]
    return render_chat(historial)


@app.callback(
    Output("store-chat-visible", "data"),
    Input("btn-toggle-chat", "n_clicks"),
    State("store-chat-visible", "data"),
    prevent_initial_call=True
)
def alternar_chat(n_clicks, visible):
    return not visible


@app.callback(
    Output("contenedor-principal", "style"),
    Output("contenedor-chat-lateral", "style"),
    Output("panel-chat", "style"),
    Output("btn-toggle-chat", "children"),
    Output("btn-toggle-chat", "style"),
    Input("store-chat-visible", "data"),
    State("store-tema", "data")
)
def actualizar_visibilidad_chat(visible, tema):
    estilo_boton_base = {
        "height": "48px",
        "width": "32px",
        "border": "1px solid #d9d9d9",
        "borderRadius": "8px 0 0 8px",
        "backgroundColor": "#fcfcfc",
        "cursor": "pointer",
        "fontSize": "18px",
        "fontWeight": "bold",
        "marginTop": "0px",
        "zIndex": "10"
    }

    if visible:
        estilo_contenedor_principal = {
            "display": "grid",
            "gridTemplateColumns": "minmax(0, 3fr) minmax(360px, 1.2fr)",
            "gap": "18px",
            "alignItems": "start",
            "width": "100%"
        }

        estilo_contenedor_chat = {
            "display": "flex",
            "alignItems": "flex-start",
            "gap": "0px",
            "width": "100%",
            "overflow": "hidden"
        }

        estilo_panel_chat = {
            "border": "1px solid #d9d9d9",
            "borderRadius": "0 8px 8px 8px",
            "padding": "14px",
            "backgroundColor": "#fcfcfc",
            "height": "calc(100vh - 120px)",
            "display": "flex",
            "flexDirection": "column",
            "minWidth": "320px",
            "width": "100%",
            "boxSizing": "border-box",
            "overflow": "hidden"
        }

        estilo_boton = {
            **estilo_boton_base,
            "borderRight": "0px"
        }

        return (
            estilo_contenedor_principal,
            estilo_contenedor_chat,
            estilo_panel_chat,
            "▶",
            estilo_boton
        )

    estilo_contenedor_principal = {
        "display": "grid",
        "gridTemplateColumns": "minmax(0, 1fr) 34px",
        "gap": "8px",
        "alignItems": "start",
        "width": "100%"
    }

    estilo_contenedor_chat = {
        "display": "flex",
        "alignItems": "flex-start",
        "gap": "0px",
        "width": "34px",
        "overflow": "visible"
    }

    estilo_panel_chat = {
        "border": "0px",
        "padding": "0px",
        "margin": "0px",
        "backgroundColor": "transparent",
        "height": "0px",
        "display": "block",
        "minWidth": "0px",
        "width": "0px",
        "maxWidth": "0px",
        "overflow": "hidden",
        "visibility": "hidden",
        "pointerEvents": "none"
    }

    estilo_boton = {
        **estilo_boton_base,
        "borderRight": "1px solid #d9d9d9",
        "borderRadius": "8px"
    }

    return (
        estilo_contenedor_principal,
        estilo_contenedor_chat,
        estilo_panel_chat,
        "◀",
        estilo_boton
    )

@app.callback(
    Output("store-config-visible", "data"),
    Input("btn-configuracion", "n_clicks"),
    State("store-config-visible", "data"),
    prevent_initial_call=True
)
def alternar_panel_configuracion(n_clicks, visible):
    return not visible


@app.callback(
    Output("panel-configuracion", "style"),
    Input("store-config-visible", "data")
)
def mostrar_ocultar_panel_configuracion(visible):
    estilo_base = {
        "position": "fixed",
        "left": "18px",
        "bottom": "84px",
        "width": "320px",
        "padding": "18px",
        "border": "1px solid #d9d9d9",
        "borderRadius": "12px",
        "backgroundColor": "#ffffff",
        "boxShadow": "0 8px 24px rgba(0,0,0,0.25)",
        "zIndex": "1000"
    }

    if visible:
        return {
            **estilo_base,
            "display": "block"
        }

    return {
        **estilo_base,
        "display": "none"
    }

@app.callback(
    Output("store-tema", "data"),
    Input("btn-tema", "n_clicks"),
    State("store-tema", "data"),
    prevent_initial_call=True
)
def alternar_tema(n_clicks, tema_actual_store):
    return "oscuro" if tema_actual_store == "claro" else "claro"


@app.callback(
    Output("contenedor-app", "style"),
    Output("btn-tema", "children"),
    Output("btn-tema", "style"),
    Output("panel-estado", "style"),
    Output("panel-resumen", "style"),
    Output("panel-chat", "style", allow_duplicate=True),
    Output("tabla-datos", "style_cell"),
    Output("tabla-datos", "style_header"),
    Output("tabla-datos", "style_data"),
    Input("store-tema", "data"),
    State("store-chat-visible", "data"),
    prevent_initial_call=True
)
def actualizar_tema(tema, chat_visible):
    tema_actual["valor"] = tema

    colores = TEMA_OSCURO if tema == "oscuro" else TEMA_CLARO

    estilo_app = {
        "fontFamily": "Arial",
        "margin": "16px",
        "backgroundColor": colores["fondo"],
        "color": colores["texto"],
        "minHeight": "100vh",
        "transition": "all 0.3s ease"
    }

    estilo_boton = {
        "position": "fixed",
        "top": "16px",
        "right": "16px",
        "width": "52px",
        "height": "52px",
        "borderRadius": "50%",
        "border": f"1px solid {colores['borde']}",
        "backgroundColor": colores["panel"],
        "color": colores["texto"],
        "fontSize": "22px",
        "cursor": "pointer",
        "zIndex": "2000",
        "boxShadow": "0 4px 12px rgba(0,0,0,0.4)"
    }

    estilo_panel = {
        "border": f"1px solid {colores['borde']}",
        "borderRadius": "8px",
        "padding": "16px",
        "backgroundColor": colores["panel"],
        "color": colores["texto"]
    }

    if chat_visible:
        estilo_chat = {
            "border": f"1px solid {colores['borde']}",
            "borderRadius": "0 8px 8px 8px",
            "padding": "14px",
            "backgroundColor": colores["panel"],
            "color": colores["texto"],
            "height": "calc(100vh - 120px)",
            "display": "flex",
            "flexDirection": "column",
            "minWidth": "320px",
            "width": "100%",
            "boxSizing": "border-box",
            "overflow": "hidden"
        }
    else:
        estilo_chat = {
            "border": "0px",
            "padding": "0px",
            "margin": "0px",
            "backgroundColor": "transparent",
            "height": "0px",
            "display": "block",
            "minWidth": "0px",
            "width": "0px",
            "maxWidth": "0px",
            "overflow": "hidden",
            "visibility": "hidden",
            "pointerEvents": "none"
        }

    style_cell = {
        "textAlign": "center",
        "padding": "8px",
        "backgroundColor": colores["tabla_cell"],
        "color": colores["texto"],
        "border": f"1px solid {colores['borde']}"
    }

    style_header = {
        "fontWeight": "bold",
        "backgroundColor": colores["tabla_header"],
        "color": colores["texto"],
        "border": f"1px solid {colores['borde']}"
    }

    style_data = {
        "backgroundColor": colores["tabla_cell"],
        "color": colores["texto"],
        "border": f"1px solid {colores['borde']}"
    }

    icono = "☀️" if tema == "oscuro" else "🌙"

    return (
        estilo_app,
        icono,
        estilo_boton,
        estilo_panel,
        estilo_panel,
        estilo_chat,
        style_cell,
        style_header,
        style_data
    )

@app.callback(
    Output("tabs-resumen-probeta", "style"),
    Input("store-tema", "data")
)
def refrescar_tabs(tema):

    if tema == "oscuro":
        return {
            "width": "100%",
            "backgroundColor": "#1f2937",
            "transition": "all 0.2s ease"
        }

    return {
        "width": "100%",
        "backgroundColor": "#fcfcfc",
        "transition": "all 0.2s ease"
    }

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8050)
