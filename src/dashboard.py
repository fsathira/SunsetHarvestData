"""
Fermentation dashboard — Brix and must temperature by days, stacked with Fairfield weather.
Data from Google Sheets (live). Notes on hover/click. Sunset Cellars styling.
"""

from pathlib import Path
from datetime import date, timedelta

import dash
from dash import dcc, html, Input, Output, State
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

from .config import PROJECT_ROOT
from .load_data import get_raw_data
from .qc import run_qc
from .weather import fetch_fairfield_weather


# ——— Sunset Cellars styling ———
COLORS = {
    "bg": "#F8F5F0",
    "card_bg": "#FFFFFF",
    "primary": "#5C2C2E",
    "primary_light": "#8B4042",
    "accent": "#2D5016",
    "text": "#2C2C2C",
    "text_muted": "#5C5C5C",
    "border": "#D4C4B0",
}

FONT_FAMILY = "'Cormorant Garamond', 'Georgia', serif"
FONT_BODY = "'Lato', 'Helvetica Neue', sans-serif"

EXTERNAL_STYLESHEETS = [
    "https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=Lato:wght@400;700&display=swap",
]


def _add_days(df: pd.DataFrame) -> pd.DataFrame:
    """Add 'day' (days since first measurement) per (Varietal, Bin, vintage)."""
    out = df.copy()
    out["day"] = None
    for (varietal, bin_val, vint), g in df.groupby(["Varietal", "Bin", "vintage"]):
        g = g.dropna(subset=["Date of Measurement"])
        if g.empty:
            continue
        start = g["Date of Measurement"].min()
        mask = (out["Varietal"] == varietal) & (out["Bin"] == bin_val) & (out["vintage"] == vint)
        out.loc[mask, "day"] = (out.loc[mask, "Date of Measurement"] - start).dt.days
    return out


def make_layout(df: pd.DataFrame) -> html.Div:
    if df is None or len(df) == 0:
        vintages = []
        varietals = []
        bins = []
    else:
        vintages = sorted(df["vintage"].dropna().astype(int).unique().tolist())
        varietals = sorted(df["Varietal"].dropna().unique().tolist())
        bins = sorted(df["Bin"].dropna().unique().astype(int).tolist())

    return html.Div(
        className="app-container",
        style={"backgroundColor": COLORS["bg"], "minHeight": "100vh", "fontFamily": FONT_BODY},
        children=[
            html.Link(rel="stylesheet", href="/assets/sunset_cellars.css"),
            html.Link(rel="icon", href="/assets/favicon.ico", type="image/x-icon"),
            html.Header(
                className="dashboard-header",
                style={
                    "backgroundColor": COLORS["primary"],
                    "color": "white",
                    "padding": "1.5rem 2rem",
                    "marginBottom": "2rem",
                },
                children=[
                    html.Img(
                        src="/assets/SUNSET_LOGO_white.png",
                        alt="Sunset Cellars",
                        style={
                            "height": "48px",
                            "width": "auto",
                            "display": "block",
                            "marginBottom": "0.75rem",
                        },
                    ),
                    html.H1(
                        "Fermentation Tracking",
                        style={"fontFamily": FONT_FAMILY, "fontWeight": 600, "margin": 0, "fontSize": "1.75rem"},
                    ),
                    html.P(
                        "Sunset Cellars — Suisun Valley, Fairfield, CA · Data from Google Sheets",
                        style={"margin": "0.25rem 0 0", "opacity": 0.9, "fontSize": "0.95rem"},
                    ),
                ],
            ),
            html.Div(
                className="dashboard-body",
                style={"maxWidth": "1200px", "margin": "0 auto", "padding": "0 1.5rem 2rem"},
                children=[
                    html.Div(
                        className="filters",
                        style={
                            "display": "grid",
                            "gridTemplateColumns": "repeat(auto-fit, minmax(180px, 1fr))",
                            "gap": "1rem",
                            "marginBottom": "1.5rem",
                        },
                        children=[
                            html.Div([
                                html.Label("Vintage", style={"display": "block", "marginBottom": "0.35rem", "color": COLORS["text_muted"], "fontSize": "0.85rem"}),
                                dcc.Dropdown(id="filter-vintage", options=[{"label": str(y), "value": y} for y in vintages], value=vintages[-1] if vintages else None, clearable=False, style={"fontFamily": FONT_BODY}),
                            ]),
                            html.Div([
                                html.Label("Varietal / Vineyard", style={"display": "block", "marginBottom": "0.35rem", "color": COLORS["text_muted"], "fontSize": "0.85rem"}),
                                dcc.Dropdown(id="filter-varietal", options=[{"label": v, "value": v} for v in varietals], value=varietals[0] if varietals else None, clearable=False, style={"fontFamily": FONT_BODY}),
                            ]),
                            html.Div([
                                html.Label("Bin", style={"display": "block", "marginBottom": "0.35rem", "color": COLORS["text_muted"], "fontSize": "0.85rem"}),
                                dcc.Dropdown(id="filter-bin", options=[{"label": f"Bin {b}", "value": b} for b in bins], value=bins[0] if bins else None, clearable=False, style={"fontFamily": FONT_BODY}),
                            ]),
                        ],
                    ),
                    html.Div(
                        className="stacked-charts",
                        style={"marginBottom": "1.5rem"},
                        children=[
                            html.Div(
                                className="card",
                                style={"backgroundColor": COLORS["card_bg"], "padding": "1.25rem", "borderRadius": "8px", "boxShadow": "0 1px 3px rgba(0,0,0,0.08)", "border": f"1px solid {COLORS['border']}"},
                                children=[
                                    dcc.Graph(id="graph-stacked", config={"displayModeBar": True, "displaylogo": False}, style={"height": "720px"}),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        id="note-detail",
                        style={
                            "marginTop": "1rem",
                            "padding": "1rem 1.25rem",
                            "backgroundColor": COLORS["card_bg"],
                            "borderRadius": "8px",
                            "border": f"1px solid {COLORS['border']}",
                            "minHeight": "60px",
                            "display": "none",
                        },
                    ),
                    html.Footer(
                        style={"marginTop": "2rem", "textAlign": "center", "color": COLORS["text_muted"], "fontSize": "0.8rem"},
                        children=["Brix & must temp by fermentation day · Fairfield weather from Open-Meteo"],
                    ),
                ],
            ),
        ],
    )


def build_stacked_figure(
    ferm: pd.DataFrame,
    weather_df: pd.DataFrame,
) -> go.Figure:
    """One figure: row1 Brix vs days, row2 Must temp vs days, row3 Fairfield temp + rain vs days."""
    ferm = ferm.sort_values("day").dropna(subset=["day"])
    if ferm.empty:
        return go.Figure()

    days = ferm["day"].astype(int).tolist()
    brix = ferm["Brix"].tolist()
    must_temp = ferm["Temperature"].tolist()
    hover_brix = []
    hover_temp = []
    for _, r in ferm.iterrows():
        note = (r.get("Notes") or "") if pd.notna(r.get("Notes")) else ""
        rep = (r.get("Reported by") or "") if pd.notna(r.get("Reported by")) else ""
        d = r["Date of Measurement"]
        dstr = d.strftime("%Y-%m-%d") if pd.notna(d) else ""
        hover_brix.append(f"Day {int(r['day'])} · {dstr}<br>Brix: {r['Brix']}<br>{rep}<br>{note[:150]}{'…' if len(str(note)) > 150 else ''}")
        hover_temp.append(f"Day {int(r['day'])} · {dstr}<br>Must: {r['Temperature']} °F<br>{rep}<br>{note[:150]}{'…' if len(str(note)) > 150 else ''}")

    specs = [[{}], [{}], [{"secondary_y": True}]]
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=("Brix (sugar) by day", "Must temperature by day", "Fairfield weather"),
        row_heights=[0.35, 0.35, 0.3],
        specs=specs,
    )
    # Row 1: Brix
    fig.add_trace(
        go.Scatter(x=days, y=brix, mode="lines+markers", name="Brix", line=dict(width=2, color=COLORS["primary"]), marker=dict(size=8), hovertext=hover_brix, hoverinfo="text", customdata=ferm.index.tolist()),
        row=1,
        col=1,
    )
    # Row 2: Must temp
    fig.add_trace(
        go.Scatter(x=days, y=must_temp, mode="lines+markers", name="Must temp (°F)", line=dict(width=2, color=COLORS["primary_light"]), marker=dict(size=8), hovertext=hover_temp, hoverinfo="text", customdata=ferm.index.tolist()),
        row=2,
        col=1,
    )
    # Row 3: Weather — temp (left) + rain (right, secondary y)
    if not weather_df.empty:
        wdays = weather_df["day_index"].tolist()
        fig.add_trace(
            go.Scatter(x=wdays, y=weather_df["temp_mean_f"].tolist(), mode="lines+markers", name="Air temp (°F)", line=dict(width=2, color=COLORS["accent"]), marker=dict(size=6)),
            row=3,
            col=1,
            secondary_y=False,
        )
        fig.add_trace(
            go.Bar(x=wdays, y=weather_df["precip_in"].tolist(), name="Rain (in)", marker_color="rgba(100,149,237,0.7)"),
            row=3,
            col=1,
            secondary_y=True,
        )
        fig.update_yaxes(title_text="Rain (in)", row=3, col=1, secondary_y=True, gridcolor=COLORS["border"], showline=True, linecolor=COLORS["border"])
    else:
        fig.add_annotation(text="Weather data unavailable for this range", row=3, col=1, xref="x domain", yref="y domain", x=0.5, y=0.5, showarrow=False)

    fig.update_xaxes(title_text="Day (fermentation)", row=1, col=1, gridcolor=COLORS["border"], showline=True, linecolor=COLORS["border"])
    fig.update_xaxes(title_text="Day (fermentation)", row=2, col=1, gridcolor=COLORS["border"], showline=True, linecolor=COLORS["border"])
    fig.update_xaxes(title_text="Day (fermentation)", row=3, col=1, gridcolor=COLORS["border"], showline=True, linecolor=COLORS["border"])
    fig.update_yaxes(title_text="Brix (°)", row=1, col=1, gridcolor=COLORS["border"], showline=True, linecolor=COLORS["border"])
    fig.update_yaxes(title_text="Must temp (°F)", row=2, col=1, gridcolor=COLORS["border"], showline=True, linecolor=COLORS["border"])
    fig.update_yaxes(title_text="Air temp (°F)", row=3, col=1, secondary_y=False, gridcolor=COLORS["border"], showline=True, linecolor=COLORS["border"])
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT_BODY, size=12, color=COLORS["text"]),
        margin=dict(t=80, b=50, l=60, r=50),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
    )
    return fig


def create_app(data_path: Path | None = None, use_google_sheets: bool = True) -> dash.Dash:
    """Build Dash app. Load data (Sheets or CSV) → QC → layout."""
    try:
        if data_path:
            raw = get_raw_data(single_file=data_path, use_google_sheets=False)
        else:
            raw = get_raw_data(use_google_sheets=use_google_sheets)
    except Exception as e:
        raw = pd.DataFrame()
        print(f"Data load failed: {e}")

    df, _ = run_qc(raw) if len(raw) > 0 else (raw, None)
    if len(df) > 0:
        df = _add_days(df)

    app = dash.Dash(
        __name__,
        external_stylesheets=EXTERNAL_STYLESHEETS,
        assets_folder=str(PROJECT_ROOT / "assets"),
    )
    app.layout = make_layout(df)
    app._harvest_df = df

    @app.callback(
        Output("filter-bin", "options"),
        Output("filter-bin", "value"),
        Input("filter-vintage", "value"),
        Input("filter-varietal", "value"),
    )
    def set_bin_options(vintage, varietal):
        d = app._harvest_df
        if d is None or len(d) == 0 or vintage is None or varietal is None:
            return [], None
        sub = d[(d["vintage"] == vintage) & (d["Varietal"] == varietal)]
        bins = sorted(sub["Bin"].dropna().unique().astype(int).tolist())
        opts = [{"label": f"Bin {b}", "value": b} for b in bins]
        val = bins[0] if bins else None
        return opts, val

    @app.callback(
        Output("graph-stacked", "figure"),
        Input("filter-vintage", "value"),
        Input("filter-varietal", "value"),
        Input("filter-bin", "value"),
    )
    def update_stacked(vintage, varietal, bin_val):
        d = app._harvest_df
        if d is None or len(d) == 0 or vintage is None or varietal is None or bin_val is None:
            return go.Figure()
        ferm = d[(d["vintage"] == vintage) & (d["Varietal"] == varietal) & (d["Bin"] == bin_val)].copy()
        ferm = ferm.sort_values("Date of Measurement").dropna(subset=["Date of Measurement", "day"])
        if ferm.empty:
            return go.Figure()
        start = ferm["Date of Measurement"].min().date()
        end = ferm["Date of Measurement"].max().date()
        try:
            weather_df = fetch_fairfield_weather(start, end)
        except Exception:
            weather_df = pd.DataFrame()
        return build_stacked_figure(ferm, weather_df)

    @app.callback(
        Output("note-detail", "children"),
        Output("note-detail", "style"),
        Input("graph-stacked", "clickData"),
        State("filter-vintage", "value"),
        State("filter-varietal", "value"),
        State("filter-bin", "value"),
    )
    def show_note_detail(click_data, vintage, varietal, bin_val):
        if not click_data or "points" not in click_data or not click_data["points"]:
            return "", {"display": "none"}
        pt = click_data["points"][0]
        customdata = pt.get("customdata")
        if customdata is None:
            return "", {"display": "none"}
        # customdata is list of indices for that trace; pointIndex picks one
        point_index = pt.get("pointIndex", 0)
        if isinstance(customdata, list):
            if point_index >= len(customdata):
                return "", {"display": "none"}
            row_index = customdata[point_index]
        else:
            row_index = customdata
        d = app._harvest_df
        if d is None or row_index not in d.index:
            return "", {"display": "none"}
        row = d.loc[row_index]
        note = row.get("Notes") or "(No note)"
        reported = row.get("Reported by") or ""
        date_str = row["Date of Measurement"].strftime("%B %d, %Y") if pd.notna(row["Date of Measurement"]) else ""
        content = html.Div([
            html.Strong(f"Day {int(row.get('day', 0))} · {date_str} — Bin {int(row['Bin'])}"),
            html.Br(),
            html.Span(f"Reported by: {reported}", style={"color": COLORS["text_muted"], "fontSize": "0.9rem"}),
            html.Br(),
            html.P(note, style={"margin": "0.5rem 0 0", "whiteSpace": "pre-wrap"}),
        ])
        style = {
            "marginTop": "1rem",
            "padding": "1rem 1.25rem",
            "backgroundColor": COLORS["card_bg"],
            "borderRadius": "8px",
            "border": f"1px solid {COLORS['border']}",
            "minHeight": "60px",
            "display": "block",
        }
        return content, style

    return app


def run_dashboard(host: str = "127.0.0.1", port: int = 8050, debug: bool = True, data_path: Path | None = None, use_google_sheets: bool = True) -> None:
    app = create_app(data_path=data_path, use_google_sheets=use_google_sheets)
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_dashboard()
