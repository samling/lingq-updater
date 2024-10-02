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
                'ID': item['pk'],
                'Term': item['term'],
                'Fragment': item['fragment'],
                'Hint': item['hints'][0]['text'] if item['hints'] else '',
                'Status': item['status']
            })

        return formatted_data
    else:
        return []

initial_data = fetch_data()

app.layout = html.Div([
    dcc.Store(id='stored-data', storage_type='session'),
    html.Div([
        dcc.Input(
            id='search-box',
            type='text',
            placeholder='Search...',
            debounce=True,
            style={'marginBottom': '10px', 'marginRight': '10px'}
        ),
        html.Button('Clear Search', id='clear-search-btn', n_clicks=0, style={'marginRight': '10px'}),
        dash_table.DataTable(
            id='editable-table',
            columns=[
                {"name": "ID", "id": "ID", "editable": False},
                {"name": "Term", "id": "Term", "editable": False},
                {"name": "Fragment", "id": "Fragment", "editable": True},
                {"name": "Hint", "id": "Hint", "editable": False},
                {"name": "Status", "id": "Status", "editable": False},
            ],
            data=[], # handled via callback
            editable=True,
            page_size=20,
            sort_action="native",
            sort_mode="multi",
            style_cell={'textAlign': 'left'},
            style_data={'whiteSpace': 'normal', 'textAlign': 'left'},
            style_data_conditional=[
                {
                    'if': {'filter_query': '{Status} = 0', 'column_id': 'Status'},
                    'backgroundColor': '#ffb2ba'
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
                    'backgroundColor': '#baffc8'
                }
            ],
            row_deletable=False,
            persistence=True,
            persistence_type="local",
        )
    ]),
    dbc.Toast(
        id="update-toast",
        header="Update successful",
        is_open=False,
        duration=3000,
        icon="success",
        dismissable=True,
        style={"position": "fixed", "top": 10, "right": 10}
    )
])

@app.callback(
    [Output('editable-table', 'data'),
    Output('update-toast', 'is_open'),
    Output('stored-data', 'data'),
    Output('search-box', 'value')],
    [Input('stored-data', 'data'),
    Input('editable-table', 'data'),
    Input('search-box', 'value'),
    Input('clear-search-btn', 'n_clicks')],
    [State('editable-table', 'data_previous')],
)
def manage_table(stored_data, data, search_value, clear_btn_clicks, data_previous):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate

    triggered_input = ctx.triggered[0]['prop_id']

    # Handle initial load
    if triggered_input == 'stored-data.data':
        if not stored_data:
            stored_data = initial_data
        return stored_data, False, stored_data, ""

    # Handle updates
    if triggered_input == 'editable-table.data' and data_previous is not None:
        for i, (previous_row, current_row) in enumerate(zip(data_previous, data)):
            if previous_row != current_row:
                # Prepare the payload with the changed data
                payload = {
                    "fragment": current_row["Fragment"]
                }
                response = requests.patch(f'https://www.lingq.com/api/v3/de/cards/{current_row["ID"]}/', json=payload, headers=headers)
        
                if response.status_code == 200:
                    updated_data = data
                    return updated_data, True, updated_data, search_value
                else:
                    print(f"Failed to update row with ID {current_row['ID']}")
                    return data, False, stored_data, search_value

    if triggered_input == 'clear-search-btn.n_clicks':
        return stored_data, False, stored_data, ""

    # TODO: When we search, stored_data is replaced with only the contents of the search, which means we need to clear the search
    # TODO: before we reload, or else handle it better
    if triggered_input == 'search-box.value':
        if not stored_data:
            stored_data = initial_data

        if not search_value:
            return stored_data, False, stored_data, ""

        filtered_data = [
            row for row in stored_data
            if search_value.lower() in row['Term'].lower() or
                search_value.lower() in row['Fragment'].lower() or
                search_value.lower() in row['Hint'].lower()
        ]
        return filtered_data, False, stored_data, search_value

    return data, False, stored_data, search_value

if __name__ == '__main__':
    app.run_server(debug=True, use_reloader=False, host='0.0.0.0')