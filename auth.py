from flask import Flask, request, redirect
import requests
import json
import webbrowser
import threading

app = Flask(__name__)

client_id = 'a32aa8f6-8805-44dd-8541-168864721a64'
tenant_id = 'cdb587e9-824c-41b5-b47f-5af9864b075b'
redirect_uri = 'http://127.0.0.1:5005/auth-response'
scope = 'Calendars.Read OnlineMeetings.Read OnlineMeetingTranscript.Read.All offline_access'  # 添加 offline_access 以獲取刷新令牌

@app.route('/')
def home():
    # 檢查是否已經有有效的訪問令牌
    try:
        with open('token.json', 'r') as token_file:
            tokens = json.load(token_file)
            access_token = tokens.get('access_token')
            refresh_token = tokens.get('refresh_token')
            if access_token:
                # 檢查訪問令牌是否有效
                return f'Access Token: {access_token}'
    except FileNotFoundError:
        pass

    # 構建授權 URL 並重定向
    auth_url = (
        f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize'
        f'?client_id={client_id}'
        f'&response_type=code'
        f'&redirect_uri={redirect_uri}'
        f'&response_mode=query'
        f'&scope={scope}'
    )
    return redirect(auth_url)

@app.route('/auth-response')
def auth_response():
    code = request.args.get('code')
    if not code:
        return "Authorization code not found. Please check the redirect URI and try again."

    token_url = f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token'
    token_data = {
        'grant_type': 'authorization_code',
        'client_id': client_id,
        'code': code,
        'redirect_uri': redirect_uri,
        'scope': scope
    }
    token_r = requests.post(token_url, data=token_data)
    token_response = token_r.json()

    access_token = token_response.get('access_token')
    refresh_token = token_response.get('refresh_token')
    if not access_token:
        return f"Failed to obtain access token. Error: {token_response.get('error_description', 'Unknown error')}"

    # 保存新的存取令牌和刷新令牌到 token.json
    with open('token.json', 'w') as token_file:
        json.dump({'access_token': access_token, 'refresh_token': refresh_token}, token_file)

    return f'Access Token: {access_token}'

def open_browser():
    webbrowser.open_new('http://127.0.0.1:5005/')

def main():
    # 在新執行緒中啟動瀏覽器，以避免阻塞 Flask 應用程式
    threading.Timer(1, open_browser).start()
    app.run(debug=True, host="127.0.0.1", port=5005)

if __name__ == "__main__":
    main()