import configparser
import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import logging
import requests

app = dash.Dash(external_stylesheets=[dbc.themes.BOOTSTRAP])

logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True

config = configparser.ConfigParser()
config.read('config.ini')
username = config['auth']['username']
password = config['auth']['password']
apiKey = config['auth']['apiKey']

def authenticate(username, password):
    if username and password:
        authenticate_url = "https://www.lingq.com/api/v2/api-token-auth/"
        headers={
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data={
            'username': username,
            'password': password
        }
        response = requests.post(
            authenticate_url, json=data
        )
        print(response.text)
        if response.status_code == requests.codes.ok:
            return response.json()["token"]
    return

if username and password:
    token = authenticate(username, password)
else:
    token = apiKey

headers = {
    'Authorization': 'Token {}'.format(token),
    'Content-Type': 'application/json',
    'cache-control': 'no-cache'
}


def fetch_data():
    cards_url="https://www.lingq.com/api/v3/de/cards/?page_size=100"
    response = requests.get(cards_url, headers=headers).json()
    cards = []
    while True:
        cards.extend(response["results"])
        if not response["next"]:
            break
        cards_url = response["next"]
        response = requests.get(cards_url, headers=headers).json()

    if cards is not None:
        formatted_data = []
        for item in cards:
            formatted_data.append({
                'PK': item['pk'],
                'Term': item['term'],
                'Fragment': item['fragment'],
                'Hint': item['hints'][0]['text'] if item['hints'] else '',
                'Status': item['status']
            })

        return formatted_data
    else:
        return[]

table = dash_table.DataTable(
        id='editable-table',
        columns=[
            {"name": "PK", "id": "PK", "editable": False},
            {"name": "Term", "id": "Term", "editable": False},
            {"name": "Fragment", "id": "Fragment", "editable": True},
            {"name": "Hint", "id": "Hint", "editable": False},
            {"name": "Status", "id": "Status", "editable": False},
        ],
        data=fetch_data(),
        editable=True,
        page_size=100,
        sort_action="native",
        sort_mode="multi",
        style_cell={'textAlign': 'left'},
        style_data={'whiteSpace': 'normal', 'textAlign': 'left'},
        style_data_conditional=[
            {
                'if': {'filter_query': '{Status} = 0', 'column_id': 'Status'},
                'backgroundColor': '#ffb3ba'
            },
            {
                'if': {'filter_query': '{Status} = 1', 'column_id': 'Status'},
                'backgroundColor': '#ffdfba'
            },
            {
                'if': {'filter_query': '{Status} = 2', 'column_id': 'Status'},
                'backgroundColor': '#ffffba'
            },
            {
                'if': {'filter_query': '{Status} = 3', 'column_id': 'Status'},
                'backgroundColor': '#baffc9'
            }
        ],
        row_deletable=False,
        persistence=True,
    )

app.layout = html.Div([
    dcc.Store(id='memory-output'),
    html.Div([table]),
])

@app.callback(
    Output('editable-table', 'data'),
    Input('editable-table', 'data'),
    State('editable-table', 'data_previous'),
)
def update_table(data, data_previous):
    if data_previous is None:
        # No edits were made
        raise dash.exceptions.PreventUpdate

    for i, (previous_row, current_row) in enumerate(zip(data_previous, data)):
        if previous_row != current_row:
            # Prepare the payload with the changed data
            payload = {
                "fragment": current_row["Fragment"]
            }
            response = requests.patch(f'https://www.lingq.com/api/v3/de/cards/{current_row["PK"]}/', json=payload, headers=headers)
    
            if response.status_code != 200:
                print(f"Failed to update row with ID {current_row['PK']}")
    
    return data

@app.callback(
    Output('memory-output', 'data'),
    Input('editable-table', 'data')
)
def on_data_set_table(data):
    table.data = data
    return data

if __name__ == '__main__':
    app.run_server(debug=True, host='0.0.0.0')