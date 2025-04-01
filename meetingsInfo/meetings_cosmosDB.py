import requests
import json
import urllib.parse
from datetime import datetime, timezone
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from azure.cosmos import CosmosClient, exceptions
from bson import ObjectId
from summary_utils import generate_summary

app = Flask(__name__)
CORS(app)  # 啟用CORS

def load_config():
    """從配置文件中讀取 API_KEY 和 ASSISTANT_ID"""
    with open('config.json', 'r') as config_file:
        config_data = json.load(config_file)
        return config_data['API_KEY'], config_data['ASSISTANT_ID']
    
class JSONEncoder(json.JSONEncoder):
    """自定義 JSON 編碼器，用於處理 ObjectId"""
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        return super().default(o)

app.json_encoder = JSONEncoder

def load_access_token():
    """從檔案中讀取存取令牌"""
    with open('../token.json', 'r') as token_file:
        token_data = json.load(token_file)
        return token_data.get('access_token')

def load_cosmos_connection_string():
    """從檔案中讀取Cosmos DB連接字串"""
    with open('../params/cosmosDB.json', 'r') as params_file:
        params_data = json.load(params_file)
        return params_data.get('connection_string')

def get_user_info(token):
    """使用存取令牌取得使用者資訊"""
    url = "https://graph.microsoft.com/v1.0/me"
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

def get_meetings(token, user_id):
    """使用存取令牌來取得過往會議資訊並生成會議總結"""
    events_url = 'https://graph.microsoft.com/v1.0/me/events'
    headers = {'Authorization': f'Bearer {token}'}
    events_r = requests.get(events_url, headers=headers)
    events = events_r.json()

    # 取得目前的 UTC 時間
    current_time = datetime.now(timezone.utc)

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
                        print(meeting['subject'])
                        join_url = online_meeting_info.get('joinUrl')
                        decoded_url = urllib.parse.unquote(join_url)
                        print(f'joinUrl: {decoded_url}')
                        get_meeting_id_url = (
                            f"https://graph.microsoft.com/v1.0/users/{user_id}/onlineMeetings"
                            f"?$filter=JoinWebUrl eq '{decoded_url}'"
                        )
                        response = requests.get(get_meeting_id_url, headers=headers)
                        meetings_data = response.json()
                        if 'value' in meetings_data and len(meetings_data['value']) > 0:
                            meeting_id = meetings_data['value'][0]['id']
                            print(f"Meeting ID: {meeting_id}")
                            meeting['meeting_id'] = meeting_id
                            transcripts_url = f"https://graph.microsoft.com/v1.0/me/onlineMeetings/{meeting_id}/transcripts"
                            transcripts_response = requests.get(transcripts_url, headers=headers)
                            transcripts_data = transcripts_response.json()
                            
                            if 'value' in transcripts_data and len(transcripts_data['value']) > 0:
                                transcript_content_url = transcripts_data['value'][0].get('transcriptContentUrl')
                                if transcript_content_url:
                                    meeting['transcript_content_url'] = transcript_content_url
                                    print(f"Transcript Content URL: {transcript_content_url}")
                                    
                                    # 獲取文字記錄
                                    transcript_response = requests.get(f"{transcript_content_url}?$format=text/vtt", headers=headers)
                                    if transcript_response.status_code == 200:
                                        transcript_content = transcript_response.text
                                        print("Transcript content retrieved successfully.")
                                        
                                        # 使用 OpenAI API 生成會議總結
                                        API_KEY, ASSISTANT_ID = load_config()
                                        summary = generate_summary(transcript_content, API_KEY, ASSISTANT_ID)
                                        meeting['summary'] = summary
                                        print(f"Meeting Summary: {summary}")
                                        
                                        # 將有文字紀錄的會議存入 Cosmos DB
                                        save_to_cosmos(meeting)
                                    else:
                                        print(f"Failed to retrieve transcript content. Status code: {transcript_response.status_code}")
                                else:
                                    print("No transcript content URL available.")
                            else:
                                print("No transcripts available for this meeting.")
                        else:
                            print("Meeting not found or no valid meeting ID returned.")
                        
                        meetings.append(meeting)
                    else:
                        print("No online meeting details available.")
    return meetings

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
        print("Meeting updated in Cosmos DB.")
    else:
        # 插入新的會議記錄
        container.create_item(meeting)
        print("Meeting saved to Cosmos DB.")

@app.route('/getMeetings', methods=['GET'])
def meetings_list():
    """返回所有會議資訊"""
    token = load_access_token()
    user_id = get_user_info(token)
    if user_id:
        meetings = get_meetings(token, user_id)

        # 連接到 Cosmos DB 並取出所有現有的會議記錄
        connection_string = load_cosmos_connection_string()
        client = CosmosClient.from_connection_string(connection_string)
        database_name = 'summary'
        container_name = 'meetings'
        database = client.get_database_client(database_name)
        container = database.get_container_client(container_name)
        existing_meetings = list(container.read_all_items())

        # 確保所有 ObjectId 被轉換為字符串
        existing_meetings = [
            {key: (str(value) if isinstance(value, ObjectId) else value) for key, value in meeting.items()}
            for meeting in existing_meetings
        ]

        # 確保新 meetings 中的 ObjectId 也被轉換為字符串（如果有）
        meetings = [
            {key: (str(value) if isinstance(value, ObjectId) else value) for key, value in meeting.items()}
            for meeting in meetings
        ]

        # 返回所有會議記錄，包括新加入的和原有的
        return jsonify({'meetings': existing_meetings + meetings})
    else:
        return jsonify({'error': 'Failed to retrieve user information.'}), 401

@app.route("/openapi.yaml", methods=["GET"])
def openapi_spec():
    """提供 OpenAPI 規範文件"""
    try:
        with open("openapi.yaml", "r", encoding="utf-8") as f:
            text = f.read()
            return Response(text, mimetype="text/yaml")
    except FileNotFoundError:
        return jsonify({"error": "OpenAPI specification file not found."}), 1204   

def main():
    app.run(debug=True, host="127.0.0.1", port=5010)

if __name__ == "__main__":
    main()