import os
import requests
import json
from azure.identity import DefaultAzureCredential
from azure.mgmt.web import WebSiteManagementClient
import jwt
from datetime import datetime, timezone
import logging
import msal
def construct_auth_url(tenant_id, client_id, redirect_uri, scope):
    return (
        f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize'
        f'?client_id={client_id}'
        f'&response_type=code'
        f'&redirect_uri={redirect_uri}'
        f'&response_mode=query'
        f'&scope={scope}'
    )

def request_access_token(tenant_id, Client_ID, client_secret):
    app = msal.ConfidentialClientApplication(
        client_id=Client_ID,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        client_credential= client_secret
    )
    result = app.acquire_token_for_client(scopes=[f"{Client_ID}/.default"])
    token = result["access_token"]
    return token

def refresh_access_token(tenant_id, client_id, refresh_token, redirect_uri, scope):
    token_url = f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token'
    token_data = {
        'grant_type': 'refresh_token',
        'client_id': client_id,
        'refresh_token': refresh_token,
        'redirect_uri': redirect_uri,
        'scope': scope
    }
    token_r = requests.post(token_url, data=token_data)
    token_response = token_r.json()
    return token_response.get('access_token'), token_response.get('refresh_token')

def update_function_app_settings(subscription_id, resource_group_name, function_app_name, access_token, refresh_token):
    credential = DefaultAzureCredential()
    web_client = WebSiteManagementClient(credential, subscription_id)

    app_settings = web_client.web_apps.list_application_settings(resource_group_name, function_app_name)
    app_settings.properties['ACCESS_TOKEN'] = access_token
    app_settings.properties['REFRESH_TOKEN'] = refresh_token

    web_client.web_apps.update_application_settings(resource_group_name, function_app_name, app_settings)

def get_config():
    client_id = os.getenv('CLIENT_ID')
    tenant_id = os.getenv('TENANT_ID')
    redirect_uri = os.getenv('REDIRECT_URI')
    scope = os.getenv('SCOPE')
    subscription_id = os.getenv('SUBSCRIPTION_ID')
    resource_group_name = os.getenv('RESOURCE_GROUP_NAME')
    function_app_name = os.getenv('FUNCTION_APP_NAME')

    return {
        'client_id': client_id,
        'tenant_id': tenant_id,
        'redirect_uri': redirect_uri,
        'scope': scope,
        'subscription_id': subscription_id,
        'resource_group_name': resource_group_name,
        'function_app_name': function_app_name
    }


def is_token_expired(token):
    """檢查存取令牌是否過期"""
    try:
        # 解碼 JWT，不需要驗證簽名
        decoded_token = jwt.decode(token, options={"verify_signature": False})
        exp = decoded_token.get('exp')

        if exp is None:
            # 如果沒有 exp 字段，假設令牌無效
            return True

        # 獲取當前的 UTC 時間
        current_time = datetime.now(timezone.utc).timestamp()

        # 檢查 exp 是否小於當前時間
        return current_time >= exp
    except jwt.DecodeError:
        # 如果解碼失敗，假設令牌無效
        return True

def get_valid_access_token():
    """獲取有效的存取令牌，必要時刷新或重新授權"""
    token = os.getenv('ACCESS_TOKEN')
    refresh_token = os.getenv('REFRESH_TOKEN')
    config = get_config()

    if not token or is_token_expired(token):
        try:
            # 嘗試使用 refresh_token 獲取新的 access_token
            token, refresh_token = refresh_access_token(config['tenant_id'], config['client_id'], refresh_token, config['redirect_uri'], config['scope'])
            update_function_app_settings(config['subscription_id'], config['resource_group_name'], config['function_app_name'], token, refresh_token)
        except Exception as e:
            logging.error(f"Failed to refresh access token: {str(e)}")
            # 如果 refresh_token 也過期，返回 None 以指示需要重新授權
            return None

    return token