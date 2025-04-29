import os
import logging
import requests
from azure.cosmos import CosmosClient, exceptions, PartitionKey
from datetime import datetime, timezone
import urllib.parse
from summary_utils import generate_summary
from azure.identity import DefaultAzureCredential
import msal
from bson import ObjectId
def load_config():
    """從環境變數中讀取 API_KEY 和 ASSISTANT_ID"""
    api_key = os.getenv('API_KEY')
    assistant_id = os.getenv('ASSISTANT_ID')
    return api_key, assistant_id
def load_cosmos_connection_string():
    """從環境變數中讀取Cosmos DB連接字串"""
    return os.getenv('COSMOS_CONNECTION_STRING')
def get_user_id(): #設定在環境變數
    return os.getenv('USER_ID')
def get_user_info(token,userPrincipalName):
    """使用存取令牌取得使用者資訊"""
    url = f"https://graph.microsoft.com/v1.0/users/{userPrincipalName}"
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        user_info = response.json()
        user_id = user_info['id']
        print(f"User ID: {user_id}")
        return user_id
    else:
        error_info = response.json()
        error_message = error_info.get('error', {}).get('message', 'Unknown error occurred.')
        print(f"Error: {error_message}")
        return None

def load_access_token():
    client_ID = os.getenv('CLIENT_ID')
    tenent_ID = os.getenv('TENANT_ID')
    client_SECRET = os.getenv('CLIENT_SECRET')
    app = msal.ConfidentialClientApplication(
        client_id= client_ID, #Azure App Registration >> Application (client) ID
        authority=f"https://login.microsoftonline.com/{tenent_ID}", #https://login.microsoftonline.com/<Directory (tenant) ID>
        client_credential= client_SECRET #Azure App Registration >> Client secrets
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"]) 
    token = result["access_token"]
    return token

def fetch_meetings(token, user_id):
    """使用存取令牌來取得過往會議資訊並生成會議總結"""
    events_url = f'https://graph.microsoft.com/v1.0/users/{user_id}/calendar/events'
    headers = {'Authorization': f'Bearer {token}'}
    events_r = requests.get(events_url, headers=headers)
    events = events_r.json()

    # 取得目前的 UTC 時間
    current_time = datetime.now(timezone.utc)

    # 連接到 Cosmos DB
    connection_string = load_cosmos_connection_string()
    client = CosmosClient.from_connection_string(connection_string)
    database_name = 'summary'
    container_name = 'meetings'
    database = client.get_database_client(database_name)
    container = database.get_container_client(container_name)

    # 讀取現有的會議記錄
    existing_meetings = list(container.read_all_items())

    # 確保所有 ObjectId 被轉換為字符串
    existing_meetings = [
        {key: (str(value) if isinstance(value, ObjectId) else value) for key, value in meeting.items()}
        for meeting in existing_meetings
    ]

    meetings = []
    for event in events.get('value', []):
        # 取得事件的開始時間
        start_info = event.get('start', {})
        start_datetime_str = start_info.get('dateTime')
        
        # 將開始時間轉換為有時區資訊的 datetime 物件
        if start_datetime_str:
            start_datetime = datetime.fromisoformat(start_datetime_str)
            if start_datetime.tzinfo is None:
                # 如果 start_datetime 是無時區資訊的，假設它是 UTC
                start_datetime = start_datetime.replace(tzinfo=timezone.utc)

            # 比較開始時間和目前時間，過濾掉未來的會議
            if start_datetime < current_time:
                if event['isOnlineMeeting']:
                    online_meeting_info = event.get('onlineMeeting')
                    if online_meeting_info:
                        meeting = {}
                        meeting['subject'] = event['subject']
                        meeting['date'] = start_datetime.isoformat()
                        logging.info(meeting['subject'])
                        join_url = online_meeting_info.get('joinUrl')
                        decoded_url = urllib.parse.unquote(join_url)
                        logging.info(f'joinUrl: {decoded_url}')
                        get_meeting_id_url = (
                            f"https://graph.microsoft.com/v1.0/users/{user_id}/onlineMeetings"
                            f"?$filter=JoinWebUrl eq '{decoded_url}'"
                        )
                        response = requests.get(get_meeting_id_url, headers=headers)
                        meetings_data = response.json()
                        if 'value' in meetings_data and len(meetings_data['value']) > 0:
                            meeting_id = meetings_data['value'][0]['id']
                            logging.info(f"Meeting ID: {meeting_id}")
                            meeting['meeting_id'] = meeting_id

                            # 檢查會議是否已存在於 Cosmos DB
                            query = f"SELECT * FROM c WHERE c.meeting_id = '{meeting_id}'"
                            items = list(container.query_items(query=query, enable_cross_partition_query=True))
                            logging.info(f"Query returned {len(items)} items.")
                            if items:
                                logging.info(f"Meeting with ID {meeting_id} already exists in Cosmos DB.")
                                # 提取已存在的會議資訊
                                existing_meeting = items[0]
                                existing_meeting_info = {
                                    "subject": existing_meeting.get("subject"),
                                    "transcript_content_url": existing_meeting.get("transcript_content_url"),
                                    "date": existing_meeting.get("date")
                                }
                                meetings.append(existing_meeting_info)
                                continue  # 跳過後續的處理

                            transcripts_url = f"https://graph.microsoft.com/v1.0/users/{user_id}/onlineMeetings/{meeting_id}/transcripts"
                            transcripts_response = requests.get(transcripts_url, headers=headers)
                            transcripts_data = transcripts_response.json()
                            
                            if 'value' in transcripts_data and len(transcripts_data['value']) > 0:
                                transcript_content_url = transcripts_data['value'][0].get('transcriptContentUrl')
                                if transcript_content_url:
                                    meeting['transcript_content_url'] = transcript_content_url
                                    logging.info(f"Transcript Content URL: {transcript_content_url}")
                                    
                                    # 獲取文字記錄
                                    transcript_response = requests.get(f"{transcript_content_url}?$format=text/vtt", headers=headers)
                                    if transcript_response.status_code == 200:
                                        transcript_content = transcript_response.text
                                        logging.info("Transcript content retrieved successfully.")
                                        
                                        # 使用 OpenAI API 生成會議總結
                                        API_KEY, ASSISTANT_ID = load_config()
                                        summary = generate_summary(transcript_content, API_KEY, ASSISTANT_ID)
                                        meeting['summary'] = summary
                                        logging.info(f"Meeting Summary: {summary}")
                                        
                                        # 將有文字紀錄的會議存入 Cosmos DB
                                        save_to_cosmos(meeting)
                                    else:
                                        logging.error(f"Failed to retrieve transcript content. Status code: {transcript_response.status_code}")
                                else:
                                    logging.info("No transcript content URL available.")
                            else:
                                logging.info("No transcripts available for this meeting.")
                        
                        meetings.append(meeting)
                    else:
                        logging.info("No online meeting details available.")
    
    # 返回合併後的會議記錄
    return existing_meetings + meetings

def save_to_cosmos(meeting):
    """將會議資訊存入 Cosmos DB，若存在則更新"""
    connection_string = load_cosmos_connection_string()
    client = CosmosClient.from_connection_string(connection_string)
    database_name = 'summary'
    container_name = 'meetings'

    try:
        database = client.get_database_client(database_name)
    except exceptions.CosmosResourceNotFoundError:
        database = client.create_database(database_name)

    try:
        container = database.get_container_client(container_name)
    except exceptions.CosmosResourceNotFoundError:
        container = database.create_container(id=container_name, partition_key=PartitionKey(path="/meeting_id"))

    # 確保每個會議都有一個 'id' 屬性
    if 'id' not in meeting:
        meeting['id'] = meeting['meeting_id']

    # 檢查會議是否已存在
    query = f"SELECT * FROM c WHERE c.meeting_id = '{meeting['meeting_id']}'"
    items = list(container.query_items(query=query, enable_cross_partition_query=True))

    if items:
        # 更新現有的會議記錄
        container.upsert_item(meeting)
        logging.info("Meeting updated in Cosmos DB.")
    else:
        # 插入新的會議記錄
        container.create_item(meeting)
        logging.info("Meeting saved to Cosmos DB.")

def get_specific_meeting_record(subject):
    """從 Cosmos DB 中查找對應的會議記錄"""
    connection_string = load_cosmos_connection_string()
    client = CosmosClient.from_connection_string(connection_string)
    database_name = 'summary'
    container_name = 'meetings'
    database = client.get_database_client(database_name)
    container = database.get_container_client(container_name)

    # 查找會議記錄
    query = f"SELECT * FROM c WHERE c.subject = '{subject}'"
    items = list(container.query_items(query=query, enable_cross_partition_query=True))
    
    return items[0] if items else None