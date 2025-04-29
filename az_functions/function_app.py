import azure.functions as func
import logging
import json
from utils import load_access_token, get_user_info, fetch_meetings, get_specific_meeting_record

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.route(route="get_user_id", auth_level=func.AuthLevel.ANONYMOUS)
def get_user_id(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing get_user_id request.')
    token = load_access_token()
    try:
        data = req.get_json()
        email = data.get('email')
        logging.info(f"Received email: {email}")

        if not email:
            logging.error("User email is missing.")
            return func.HttpResponse(
                json.dumps({"error": "User email is required."}),
                status_code=400,
                mimetype="application/json"
            )

        user_id = get_user_info(token, email)
        logging.info(f"Retrieved user ID: {user_id}")

        if user_id:
            response = func.HttpResponse(
                json.dumps({"user_id": user_id}),
                mimetype="application/json"
            )
            # 使用 Set-Cookie 標頭設置 Cookie
            response.headers['Set-Cookie'] = f"user_id={user_id}; Path=/; HttpOnly"
            return response
        else:
            logging.error("Failed to retrieve user ID from Graph API.")
            return func.HttpResponse(
                json.dumps({"error": "Failed to retrieve user ID."}),
                status_code=500,
                mimetype="application/json"
            )

    except ValueError as ve:
        logging.error(f"Invalid JSON input: {ve}")
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON input."}),
            status_code=400,
            mimetype="application/json"
        )
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Internal server error."}),
            status_code=500,
            mimetype="application/json"
        )

@app.route(route="get_user_id/openapi.yaml", auth_level=func.AuthLevel.ANONYMOUS)
def openapi_userid(req: func.HttpRequest) -> func.HttpResponse:
    try:
        with open('get_user_id/openapi.yaml', 'r', encoding='utf-8') as f:
            content = f.read()
        return func.HttpResponse(content, mimetype='text/plain', status_code=200)
    except FileNotFoundError:
        error_response = {"error": "OpenAPI specification file not found."}
        return func.HttpResponse(json.dumps(error_response), status_code=666, mimetype='application/json')

@app.route(route="get_meetings", auth_level=func.AuthLevel.ANONYMOUS)
def get_meetings(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    token = load_access_token()

    # 從 headers 中提取 Set-Cookie，並解析 user_id
    cookie_header = req.headers.get('Cookie')
    user_id = None
    if cookie_header:
        cookies = {cookie.split('=')[0]: cookie.split('=')[1] for cookie in cookie_header.split('; ')}
        user_id = cookies.get('user_id')

    if token and user_id:
        meetings = fetch_meetings(token, user_id)
        return func.HttpResponse(json.dumps({'meetings': meetings}), mimetype="application/json")
    else:
        return func.HttpResponse(
            json.dumps({'error': 'Failed to retrieve user information.'}),
            status_code=401,
            mimetype="application/json"
        )
@app.route(route="get_meetings/openapi.yaml", auth_level=func.AuthLevel.ANONYMOUS)
def openapi_meetings(req: func.HttpRequest) -> func.HttpResponse:
    try:
        with open('get_meetings/openapi.yaml', 'r', encoding='utf-8') as f:
            content = f.read()
        return func.HttpResponse(content, mimetype='text/plain', status_code=200)
    except FileNotFoundError:
        error_response = {"error": "OpenAPI specification file not found."}
        return func.HttpResponse(json.dumps(error_response), status_code=666, mimetype='application/json')

@app.route(route="conclusion", auth_level=func.AuthLevel.ANONYMOUS)
def conclusion(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing conclusion request.')
    try:
        data = req.get_json()
        subject = data.get('subject')

        if not subject:
            return func.HttpResponse(json.dumps({"error": "Meeting subject is required."}), status_code=400, mimetype="application/json")

        meeting_record = get_specific_meeting_record(subject)

        if not meeting_record:
            return func.HttpResponse(json.dumps({"error": "Meeting not found in database. Please input the identical Meeting Subject again."}), status_code=404, mimetype="application/json")

        meeting_info = {
            "subject": meeting_record.get('subject'),
            "date": meeting_record.get('date'),
            "summary": meeting_record.get('summary')
        }
        return func.HttpResponse(json.dumps(meeting_info), mimetype="application/json")

    except ValueError:
        return func.HttpResponse(json.dumps({"error": "Invalid JSON input."}), status_code=400, mimetype="application/json")

@app.route(route="conclusion/openapi.yaml", auth_level=func.AuthLevel.ANONYMOUS)
def openapi_conclude(req: func.HttpRequest) -> func.HttpResponse:
    try:
        with open('conclusion/openapi.yaml', 'r', encoding='utf-8') as f:
            content = f.read()
        return func.HttpResponse(content, mimetype='text/plain', status_code=200)
    except FileNotFoundError:
        error_response = {"error": "OpenAPI specification file not found."}
        return func.HttpResponse(json.dumps(error_response), status_code=666, mimetype='application/json')