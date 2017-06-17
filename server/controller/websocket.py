"""
WebSocket Controller
"""

import json
import datetime
import controller

from bottle import route, request, abort
from geventwebsocket import WebSocketError

from parsing_lib import LogParser
from helpers import util

# Store a dictionary of string -> function
_ws_routes = {}
_web_ui_ws_connections = {}


@route('/ws')
def handle_websocket():
    """ Handle an incomming WebSocket connection.

    This function handles incomming WebSocket connections and waits for
    incoming messages from the connection. When a message is recieved, it calls
    the appropriate function.
    """

    websocket = request.environ.get('wsgi.websocket')
    if not websocket:
        abort(400, 'Expected WebSocket request.')

    print('connection recieved')

    websocket_metadata = {}

    while not websocket.closed:
        try:
            message = websocket.receive()
            if message is None:
                continue

            decoded_message = json.loads(message)
            message_type = decoded_message.get('messageType', None)
            if message_type not in _ws_routes:
                print('Unrecognized message_type %s' % message_type)
                continue

            _ws_routes[message_type](decoded_message, websocket,
                                     websocket_metadata)
        except WebSocketError:
            break

    # If we have the API key, we can waste a little less time searching for the
    # WebSocket.
    ws_api_key = websocket_metadata.get('apiKey', '')
    if (ws_api_key and ws_api_key in _web_ui_ws_connections and
            websocket in _web_ui_ws_connections[ws_api_key]):
        _web_ui_ws_connections[ws_api_key].remove(websocket)
    # ... Otherwise we have to search everywhere to find and delete it.
    else:
        for api_key, websockets_for_api_key in _web_ui_ws_connections.items():
            if websocket in websockets_for_api_key:
                websockets_for_api_key.remove(websocket)
                break

    for api_key, websockets in list(_web_ui_ws_connections.items()):
        if not websockets:
            del _web_ui_ws_connections[api_key]


def ws_router(message_type):
    """ Provide a decorator for adding functions to the _ws_route dictionary.
    """

    def decorator(function):
        _ws_routes[message_type] = function

    return decorator


@ws_router('startSession')
def start_session(message, websocket, metadata):
    """ Marks the start of a logging session, and attaches metadata to the
        WebSocket receiving the raw logs.
    """

    for attribute, value in message.items():
        metadata[attribute] = value

    metadata['startTime'] = str(datetime.datetime.now())


@ws_router('logDump')
def log_dump(message, websocket, metadata):
    """ Handles Log Dumps from the Mobile API.

    When a log dump comes in from the Mobile API, this function takes the raw
    log data, parses it and sends the parsed data to all connected web clients.

    Args:
        message: the decoded JSON message from the Mobile API
        websocket: the full websocket connection
        metadata: the metadata object for the WebSocket connection
    """
    log_entries = list(
        LogParser.parse(message['rawLogData'], metadata['osType']))

    api_key = metadata.get('apiKey', '')

    # Send to database and convert to HTML.
    controller.datastore_interface.store_logs(
        api_key, metadata['deviceName'], metadata['appName'],
        metadata['startTime'], metadata['osType'], log_entries)

    # Create a message to send to the web clients.
    send_logs = {
        'messageType': 'logData',
        'osType': metadata['osType'],
        'logEntries': LogParser.convert_to_html(log_entries),
    }

    for connection in _get_associated_websockets(api_key):
        connection.send(util.serialize_to_json(send_logs))


@ws_router('endSession')
def end_session(message, websocket, metadata):
    """Set session is over and add to the device/app collection."""
    api_key = metadata.get('apiKey', '')
    controller.datastore_interface.set_session_over(
        api_key, metadata['deviceName'], metadata['appName'],
        metadata['startTime'])
    controller.datastore_interface.add_device_app(
        api_key, metadata['deviceName'], metadata['appName'])


@ws_router('associateUser')
def associate_user(message, websocket, metadata):
    """ Associates a WebSocket connection with a session.

    When a browser requests to be associated with a session, add the associated
    WebSocket connection to the list connections for that session.

    Args:
        message: The decoded JSON message from the Mobile API. Contains the API
            key for the user.
        websocket: The WebSocket connection object where the log is being
            received.
    """

    api_key = message.get('apiKey', '')

    _web_ui_ws_connections.setdefault(api_key, []).append(websocket)


@ws_router('deviceMetrics')
def device_metrics(message, websocket, metadata):
    """ Handles Device Metrics sent from Mobile API.

    When device metrics come in from the Mobile API, this function takes the
    device metrics and sends it to all connect web clients.

    Args:
        message: the device metrics in a JSON object
        websocket: the full websocket connection
    """
    for connection in _get_associated_websockets(metadata.get('apiKey', '')):
        connection.send(util.serialize_to_json(message))


def _get_associated_websockets(api_key):
    """ Gets the WebSocket connections assoicated with the given API Key.

    This calls to the User Management Interface which is configured in the
    config.yaml file.
    """
    return controller.user_management_interface.find_associated_websockets(
        api_key, _web_ui_ws_connections)
