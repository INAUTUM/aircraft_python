import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go
import pandas as pd
from sqlalchemy import create_engine
import plotly.express as px

app = dash.Dash(__name__)

def fetch_data():
    try:
        engine = create_engine('postgresql://postgres:postgres@db:5432/aviation')
        
        query = """
        SELECT 
            f.flight_icao as icao,
            COALESCE(NULLIF(a.model_name, ''), 'Unknown Model') as model,
            fp.latitude,
            fp.longitude,
            fp.timestamp
        FROM flight_positions fp
        JOIN flights f ON fp.flight_id = f.id
        LEFT JOIN aircrafts a 
            ON UPPER(TRIM(f.aircraft_icao)) = UPPER(TRIM(a.icao_code))
        WHERE 
            fp.timestamp >= NOW() - INTERVAL '1 hour'
            AND fp.latitude BETWEEN -90 AND 90
            AND fp.longitude BETWEEN -180 AND 180
        ORDER BY fp.timestamp DESC
        LIMIT 1000
        """
        
        df = pd.read_sql(query, engine)
        return df
    
    except Exception as e:
        print(f"Database error: {str(e)}")
        return pd.DataFrame()

app.layout = html.Div([
    dcc.Graph(
        id='live-map',
        config={'displayModeBar': False},
        style={'height': '90vh', 'width': '100%'}
    ),
    dcc.Interval(
        id='interval',
        interval=10*1000,
        n_intervals=0
    )
])

@app.callback(
    Output('live-map', 'figure'),
    Input('interval', 'n_intervals')
)
def update_map(n):
    df = fetch_data()
    fig = go.Figure()
    
    if not df.empty:
        df['model'] = df['model'].fillna('Unknown Model')
        models = df['model'].unique()
        colors = px.colors.qualitative.Dark24
        
        for i, model in enumerate(models):
            model_df = df[df['model'] == model]
            
            fig.add_trace(
                go.Scattermap(
                    lat=model_df['latitude'],
                    lon=model_df['longitude'],
                    mode='markers+lines',
                    marker=dict(
                        size=12,
                        color=colors[i],
                        symbol='airport'
                    ),
                    line=dict(width=2, color=colors[i]),
                    name=model,
                    hoverinfo='text+name',
                    text=model_df['icao'],
                    legendgroup=model
                )
            )

        lat_center = df['latitude'].median()
        lon_center = df['longitude'].median()
        zoom = 5
    else:
        lat_center = 44.5
        lon_center = 34.5
        zoom = 3

    fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=lat_center, lon=lon_center),
            zoom=zoom
        ),
        margin={"r":0,"t":40,"l":0,"b":0},
        legend=dict(
            title='<b>Модели самолетов</b>',
            orientation='v',
            yanchor='top',
            xanchor='left',
            x=0.01,
            y=0.99,
            bgcolor='rgba(255,255,255,0.9)'
        )
    )
    
    return fig

if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=False)