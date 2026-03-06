import requests
import pandas as pd
import dash
from dash import dcc, html, Input, Output
import plotly.express as px
from datetime import datetime

# Configuración

df_juegos = pd.read_csv('data_steam.csv')

df_juegos['Última Vez Jugado'] = pd.to_datetime(df_juegos['Última Vez Jugado'], format='mixed', errors='coerce')

df_juegos['Año Última Vez Jugado'] = df_juegos['Última Vez Jugado'].dt.year

# Calcular estadísticas clave
numero_juegos = len(df_juegos)
total_horas = df_juegos["Horas Totales"].sum()
total_logros = df_juegos["Logros Desbloqueados"].sum()

total_horas_por_ano = df_juegos.groupby('Año Última Vez Jugado')['Horas Totales'].sum().reset_index()

# El resto de la aplicación Dash sigue igual


# Crear la aplicación Dash
app = dash.Dash(__name__)

app.layout = html.Div(style={"padding": "20px", "fontFamily": "Arial"}, children=[
    html.H1("Visualización de Juegos de Steam", style={"textAlign": "center"}),

    # Resúmenes
    html.Div(style={"display": "flex", "justifyContent": "space-around", "marginBottom": "20px"}, children=[
        html.Div([
            html.H2("Número de Juegos", style={"textAlign": "center"}),
            html.P(f"{numero_juegos}", style={"textAlign": "center", "fontSize": "24px", "fontWeight": "bold"})
        ], style={"border": "1px solid #ccc", "borderRadius": "10px", "padding": "20px", "width": "30%"}),

        html.Div([
            html.H2("Horas Jugadas", style={"textAlign": "center"}),
            html.P(f"{total_horas:.2f}", style={"textAlign": "center", "fontSize": "24px", "fontWeight": "bold"})
        ], style={"border": "1px solid #ccc", "borderRadius": "10px", "padding": "20px", "width": "30%"}),

        html.Div([
            html.H2("Total Logros", style={"textAlign": "center"}),
            html.P(f"{total_logros}", style={"textAlign": "center", "fontSize": "24px", "fontWeight": "bold"})
        ], style={"border": "1px solid #ccc", "borderRadius": "10px", "padding": "20px", "width": "30%"})
    ]),

    # Filtro y tabla
    html.Div([
        dcc.Dropdown(
            id="juego-dropdown",
            options=[{"label": juego, "value": juego} for juego in df_juegos["Nombre"]],
            value=None,
            placeholder="Selecciona un juego",
            style={"width": "100%", "marginBottom": "20px"}
        ),
        dcc.Graph(id="tabla-datos")
    ]),

    # Gráficos
    html.Div(style={"marginTop": "20px"}, children=[
        dcc.Graph(id="horas-juego"),
        dcc.Graph(id="ultimos-juegos"),
    ])
])

# Callbacks para gráficos dinámicos
@app.callback(
    Output("horas-juego", "figure"),
    Input("juego-dropdown", "value")
)
def actualizar_horas_juego(juego_seleccionado):
    if juego_seleccionado:
        datos_juego = df_juegos[df_juegos["Nombre"] == juego_seleccionado]
        fig = px.bar(
            datos_juego,
            x=["Horas Totales", "Horas Últimas 2 Semanas"],
            y=datos_juego.iloc[0, 2:4].values,
            title=f"Distribución de Horas para {juego_seleccionado}",
            labels={"x": "Tipo de Horas", "y": "Horas"}
        )
        return fig
    else:
        return px.bar(title="Selecciona un juego para ver detalles.")

@app.callback(
    Output("ultimos-juegos", "figure"),
    Input("juego-dropdown", "value")
)
def actualizar_ultimos_juegos(juego_seleccionado):
    df_recientes = df_juegos.sort_values("Última Vez Jugado", ascending=False).head(20)
    fig = px.bar(
        df_recientes,
        x="Nombre",
        y="Horas Totales",
        title="Top 10 Juegos Más Recientes",
        labels={"x": "Juego", "y": "Horas Totales"}
    )
    return fig

@app.callback(
    Output("tabla-datos", "figure"),
    Input("juego-dropdown", "value")
)
def actualizar_tabla(juego_seleccionado):
    if juego_seleccionado:
        datos_filtrados = df_juegos[df_juegos["Nombre"] == juego_seleccionado]
    else:
        datos_filtrados = df_juegos
    fig = px.bar(
        datos_filtrados,
        x="Nombre",
        y="Horas Totales",
        title="Resumen de Juegos",
        labels={"Nombre": "Juego", "Horas Totales": "Horas"}
    )
    return fig

# Ejecutar la app
if __name__ == "__main__":
    app.run_server(debug=True)
