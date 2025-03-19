import requests
import json
from datetime import datetime, timedelta,timezone
import re
import urllib.parse


# 從檔案中讀取存取令牌
with open('token.json', 'r') as token_file:
    token_data = json.load(token_file)
    token = token_data.get('access_token')
user_id ='2e27d936-206d-4810-acc5-cfe9e88025a6'
join_url = 'https://teams.microsoft.com/l/meetup-join/19:meeting_YmJhMTdiOTMtZTg0Ny00OTczLTk3ZWQtOTVhZmZmNThhMzAw@thread.v2/0?context={"Tid":"cdb587e9-824c-41b5-b47f-5af9864b075b","Oid":"f31eb70c-c8b9-4715-9db4-78fed51d9950"}'


# 編碼 Join URL
encoded_join_url = urllib.parse.quote(join_url, safe='')

# API URL 來獲取會議 ID
get_meeting_id_url = (
    f"https://graph.microsoft.com/v1.0/users/{user_id}/onlineMeetings"
    f"?$filter=JoinWebUrl eq '{encoded_join_url}'"
)

# 設置標頭
headers = {
    'Authorization': f'Bearer {token}'
}

# 發送 GET 請求來獲取會議 ID
response = requests.get(get_meeting_id_url, headers=headers)
meetings_data = response.json()

# 檢查響應並提取會議 ID
if 'value' in meetings_data and len(meetings_data['value']) > 0:
    meeting_id = meetings_data['value'][0]['id']
    print(f"Meeting ID: {meeting_id}")
    # 使用會議 ID 來獲取轉錄
    transcripts_url = f"https://graph.microsoft.com/v1.0/me/onlineMeetings/{meeting_id}/transcripts"
    transcripts_response = requests.get(transcripts_url, headers=headers)
    transcripts_data = transcripts_response.json()

else:
    print("Meeting not found or no valid meeting ID returned.")

# 提取 transcriptContentUrl
transcript_content_url = transcripts_data['value'][0]['transcriptContentUrl']

# 設置標頭
headers = {
    'Authorization': f'Bearer {token}'
}

# 發送 GET 請求來讀取內容
response = requests.get(f"{transcript_content_url}?$format=text/vtt", headers=headers)

# 檢查響應狀態碼
if response.status_code == 200:
    transcript_content = response.text
    print(transcript_content)
    
    # 將內容寫入文本文件
    with open('transcript.vtt', 'w', encoding='utf-8') as file:
        file.write(transcript_content)
    print("Transcript content saved to transcript.vtt")
else:
    print(f"Failed to retrieve content. Status code: {response.status_code}")
    print(response.json())