from collections import deque
from datetime import datetime
import os

import pandas as pd
from dash import (
    Dash, dcc, html, dash_table,
    Input, Output, State, callback_context
)
import plotly.graph_objects as go
from openai import OpenAI

from config import (
    MODO_FUENTE,
    PUERTO_SERIAL,
    BAUDRATE,
    TIMEOUT_SERIAL,
    AREA_INICIAL,
    LONGITUD_INICIAL,
    INTERVALO_MS,
    MAX_PUNTOS_GRAFICA,
    MAX_REGISTROS_MEMORIA,
    CARPETA_EXPORTACION,
    NOMBRE_BASE_CSV,
    MAX_CICLOS_SIN_DATOS,
    OPENAI_MODEL,
    CHAT_INSTRUCCIONES,
)

from simulador import SimuladorEnsayo
from adquisicion_serial import LectorSerialEnsayo


# -----------------------------
# Fuente de datos
# -----------------------------
def crear_fuente_datos():
    if MODO_FUENTE == "serial":
        return LectorSerialEnsayo(PUERTO_SERIAL, BAUDRATE, TIMEOUT_SERIAL)
    return SimuladorEnsayo()


fuente = crear_fuente_datos()
datos = deque(maxlen=MAX_REGISTROS_MEMORIA)
ultimo_archivo_guardado = {"ruta": None}

# Cliente OpenAI
# Usa OPENAI_API_KEY desde variable de entorno
client = OpenAI()

app = Dash(__name__)
app.title = "Ensayo de Tracción - Prototipo V5"


# -----------------------------
# Utilidades
# -----------------------------
def asegurar_carpeta_exportacion():
    os.makedirs(CARPETA_EXPORTACION, exist_ok=True)


def generar_nombre_csv():
    marca_tiempo = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(CARPETA_EXPORTACION, f"{NOMBRE_BASE_CSV}_{marca_tiempo}.csv")


def calcular_variables(df):
    if df.empty:
        return df

    df = df.copy()
    df["deformacion"] = df["desplazamiento"] / LONGITUD_INICIAL
    df["esfuerzo"] = df["fuerza"] / AREA_INICIAL
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
                name="Fuerza vs desplazamiento"
            )
        )

    fig.update_layout(
        title="Fuerza vs desplazamiento",
        xaxis_title="Desplazamiento (mm)",
        yaxis_title="Fuerza (N)",
        template="plotly_white",
        height=320,
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
        template="plotly_white",
        height=320,
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


def consultar_chatgpt(pregunta, df):
    contexto = resumen_contexto_para_chat(df)

    respuesta = client.responses.create(
        model=OPENAI_MODEL,
        instructions=CHAT_INSTRUCCIONES,
        input=f"""
Contexto del ensayo:
{contexto}

Pregunta del usuario:
{pregunta}
"""
    )
    return respuesta.output_text


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


# -----------------------------
# Layout
# -----------------------------
app.layout = html.Div(
    style={"fontFamily": "Arial", "margin": "16px"},
    children=[
        html.H1("Sistema de adquisición y visualización de datos"),
        html.Div(f"Prototipo V5 | Fuente: {MODO_FUENTE}", style={"marginBottom": "14px", "color": "#444"}),

        html.Div(
            style={"display": "grid", "gridTemplateColumns": "3fr 1.2fr", "gap": "18px"},
            children=[
                # Columna principal
                html.Div(
                    children=[
                        html.Div(
                            style={"display": "flex", "gap": "10px", "flexWrap": "wrap", "marginBottom": "18px"},
                            children=[
                                html.Button("Iniciar", id="btn-iniciar", n_clicks=0, style={"padding": "10px 16px"}),
                                html.Button("Detener", id="btn-detener", n_clicks=0, style={"padding": "10px 16px"}),
                                html.Button("Reiniciar", id="btn-reiniciar", n_clicks=0, style={"padding": "10px 16px"}),
                                html.Button("Guardar CSV", id="btn-guardar", n_clicks=0, style={"padding": "10px 16px"}),
                                html.Button("Descargar último CSV", id="btn-descargar", n_clicks=0, style={"padding": "10px 16px"}),
                            ]
                        ),

                        html.Div(
                            style={"display": "grid", "gridTemplateColumns": "1fr 2fr", "gap": "16px", "marginBottom": "20px"},
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
                                        html.Div(id="indicadores")
                                    ]
                                ),
                                html.Div(
                                    style={
                                        "border": "1px solid #d9d9d9",
                                        "borderRadius": "8px",
                                        "padding": "16px",
                                        "backgroundColor": "#fcfcfc"
                                    },
                                    children=[
                                        html.H3("Resumen del ensayo"),
                                        html.Div(id="panel-resultados")
                                    ]
                                )
                            ]
                        ),

                        html.Div(
                            style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "16px"},
                            children=[
                                dcc.Graph(id="grafica-fuerza-desplazamiento"),
                                dcc.Graph(id="grafica-esfuerzo-deformacion")
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
                            page_size=12,
                            style_table={"overflowX": "auto"},
                            style_cell={"textAlign": "center", "padding": "8px"},
                            style_header={"fontWeight": "bold"}
                        ),
                    ]
                ),

                # Chat lateral
                html.Div(
                    style={
                        "border": "1px solid #d9d9d9",
                        "borderRadius": "8px",
                        "padding": "14px",
                        "backgroundColor": "#fcfcfc",
                        "height": "calc(100vh - 120px)",
                        "display": "flex",
                        "flexDirection": "column"
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
                            style={"width": "100%", "height": "90px", "resize": "none", "marginBottom": "8px"}
                        ),
                        html.Button("Enviar pregunta", id="btn-chat", n_clicks=0, style={"padding": "10px"}),
                    ]
                )
            ]
        ),

        dcc.Interval(id="intervalo-actualizacion", interval=INTERVALO_MS, n_intervals=0),
        dcc.Store(id="store-mensaje", data=""),
        dcc.Store(id="store-chat", data=[]),
        dcc.Download(id="descarga-csv")
    ]
)


# -----------------------------
# Callbacks de control
# -----------------------------
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


# -----------------------------
# Callback de actualización principal
# -----------------------------
@app.callback(
    Output("grafica-fuerza-desplazamiento", "figure"),
    Output("grafica-esfuerzo-deformacion", "figure"),
    Output("tabla-datos", "data"),
    Output("estado-sistema", "children"),
    Output("indicadores", "children"),
    Output("panel-resultados", "children"),
    Output("mensaje-accion", "children"),
    Input("intervalo-actualizacion", "n_intervals"),
    State("store-mensaje", "data")
)
def actualizar_interfaz(n_intervals, mensaje):
    nuevo_dato = fuente.leer_dato()

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

    df = calcular_variables(df)
    df_grafica = df.tail(MAX_PUNTOS_GRAFICA) if not df.empty else df

    fig_1 = crear_figura_fuerza_desplazamiento(df_grafica)
    fig_2 = crear_figura_esfuerzo_deformacion(df_grafica)

    estado = obtener_estado_texto()

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

    return fig_1, fig_2, tabla, estado, indicadores, panel, mensaje


# -----------------------------
# Callback del chat
# -----------------------------
@app.callback(
    Output("store-chat", "data"),
    Output("chat-input", "value"),
    Input("btn-chat", "n_clicks"),
    State("chat-input", "value"),
    State("store-chat", "data"),
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

    df = calcular_variables(df)

    try:
        respuesta = consultar_chatgpt(pregunta.strip(), df)
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


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8050)