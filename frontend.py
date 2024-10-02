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
    dcc.Store(id='filtered-data', storage_type='memory'),
    dcc.Store(id='selected-row-id', storage_type='memory'),
    dcc.Store(id='sort-state', storage_type='memory'),
    html.Div([
        dcc.Input(
            id='search-box',
            type='text',
            placeholder='Search...',
            debounce=True,
            style={'marginBottom': '10px', 'marginRight': '10px'}
        ),
        html.Button('Clear Search', id='clear-search-btn', n_clicks=0, style={'marginRight': '10px'}),
        html.Div([
            html.Label("Edit Fragment:"),
            dcc.Textarea(id='edit-fragment', style={'width': '100%', 'height': '100%'}),
            html.Button("Save", id="save-button", style={'marginTop': '10px'}),
        ], style={'marginBottom': '20px'}),
        dash_table.DataTable(
            id='editable-table',
            columns=[
                {"name": "ID", "id": "ID", "editable": False},
                {"name": "Term", "id": "Term", "editable": False},
                {"name": "Fragment", "id": "Fragment", "editable": False},
                {"name": "Hint", "id": "Hint", "editable": False},
                {"name": "Status", "id": "Status", "editable": False},
            ],
            data=[], # handled via callback
            editable=True,
            page_size=20,
            sort_action="native",
            sort_mode="single",
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
    Output('edit-fragment', 'value'),
    Output('update-toast', 'is_open'),
    Output('stored-data', 'data'),
    Output('filtered-data', 'data'),
    Output('search-box', 'value'),
    Output('selected-row-id', 'data'),
    Output('sort-state', 'data')],
    [Input('stored-data', 'data'),
    Input('editable-table', 'active_cell'),
    Input('save-button', 'n_clicks'),
    Input('search-box', 'value'),
    Input('clear-search-btn', 'n_clicks'),
    Input('editable-table', 'sort_by')],
    [State('edit-fragment', 'value'),
     State('editable-table', 'data'),
     State('filtered-data', 'data'),
     State('selected-row-id', 'data'),
     State('sort-state', 'data')],
)
def manage_table(stored_data, active_cell, n_clicks, search_value, clear_btn_clicks, sort_by, edited_value, table_data, filtered_data, selected_row_id, sort_state):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate

    triggered_input = ctx.triggered[0]['prop_id']
    update_toast = False

    # Handle initial load with stored data or fall back to initial_data if empty
    if triggered_input == 'stored-data.data':
        if not stored_data or len(stored_data) == 0:
            return initial_data, "", False, initial_data, initial_data, "", None, None
        return stored_data, "", False, stored_data, stored_data, "", None, None

    # Handle sorting
    if triggered_input == 'editable-table.sort_by':
        if sort_by:
            sorted_data = sorted(
                table_data,
                key=lambda x: x[sort_by[0]['column_id']],
                reverse=sort_by[0]['direction'] == 'desc'
            )
            return sorted_data, dash.no_update, False, stored_data, sorted_data, dash.no_update, selected_row_id, sort_by

    # Handle updating the text area based on the clicked Fragment cell
    if triggered_input == 'editable-table.active_cell' and active_cell:
        if active_cell['column_id'] == 'Fragment':
            # Extract ID of the selected row from the current table data
            selected_row_id = table_data[active_cell['row']]['ID']
            # Use the ID to find the correct row in the full stored_data
            row_data = next((row for row in table_data if row['ID'] == selected_row_id), None)
            if row_data:
                return dash.no_update, row_data['Fragment'], False, dash.no_update, dash.no_update, dash.no_update, selected_row_id, dash.no_update

    # Handle saving the edit from the text area
    if triggered_input == 'save-button.n_clicks' and n_clicks and selected_row_id:
        updated_data = [row.copy() for row in table_data]
        for row in updated_data:
            if row['ID'] == selected_row_id:
                row['Fragment'] = edited_value
                payload = {"fragment": edited_value}
                response = requests.patch(f'https://www.lingq.com/api/v3/de/cards/{row["ID"]}/', json=payload, headers=headers)
                if response.status_code == 200:
                    update_toast = True

        # Update stored_data
        updated_stored_data = [row if row['ID'] != selected_row_id else next(r for r in updated_data if r['ID'] == selected_row_id) for row in stored_data]

        return updated_data, "", update_toast, updated_stored_data, updated_data, dash.no_update, None, dash.no_update

    # Handle search functionality
    if triggered_input == 'search-box.value':
        if not search_value:
            return stored_data, "", False, stored_data, stored_data, "", None, None

        filtered_data = [
            row for row in stored_data
            if search_value.lower() in row['Term'].lower() or
               search_value.lower() in row['Fragment'].lower() or
               search_value.lower() in row['Hint'].lower()
        ]
        return filtered_data, "", False, stored_data, filtered_data, search_value, None, None

    # Handle clear search functionality
    if triggered_input == 'clear-search-btn.n_clicks':
        return stored_data, "", False, stored_data, stored_data, "", None, None

    return table_data, "", False, stored_data, filtered_data, search_value, selected_row_id, sort_state


if __name__ == '__main__':
    app.run_server(debug=True, use_reloader=False, host='0.0.0.0')