import requests
import json
import urllib.parse

# 從檔案中讀取存取令牌
with open('token.json', 'r') as token_file:
    token_data = json.load(token_file)
    token = token_data.get('access_token')

url = "https://graph.microsoft.com/v1.0/me"
headers = {
    'Authorization': f'Bearer {token}'
}
response = requests.get(url, headers=headers)
user_info = response.json()
user_id = user_info['id']
print(f"User ID: {user_id}")

# 使用存取令牌來取得過往會議資訊
events_url = 'https://graph.microsoft.com/v1.0/me/events'
events_r = requests.get(events_url, headers=headers)
events = events_r.json()

# 列印會議資訊
meetings = []

for event in events.get('value', []):
    if event['isOnlineMeeting']:
        online_meeting_info = event.get('onlineMeeting')
        if online_meeting_info:
            # 初始化 meeting 字典
            meeting = {}
            meeting['subject'] = event['subject']
            print(meeting['subject'])
            # Join URL
            join_url = online_meeting_info.get('joinUrl')
            # 解碼 URL
            decoded_url = urllib.parse.unquote(join_url)
            print(f'joinUrl: {decoded_url}')
            get_meeting_id_url = (
                f"https://graph.microsoft.com/v1.0/users/{user_id}/onlineMeetings"
                f"?$filter=JoinWebUrl eq '{decoded_url}'"
            )
            # 檢查響應並提取會議 ID
            response = requests.get(get_meeting_id_url, headers=headers)
            meetings_data = response.json()
            if 'value' in meetings_data and len(meetings_data['value']) > 0:
                meeting_id = meetings_data['value'][0]['id']
                print(f"Meeting ID: {meeting_id}")
                meeting['Meeting ID'] = meeting_id
                # 使用會議 ID 來獲取轉錄
                transcripts_url = f"https://graph.microsoft.com/v1.0/me/onlineMeetings/{meeting_id}/transcripts"
                transcripts_response = requests.get(transcripts_url, headers=headers)
                transcripts_data = transcripts_response.json()
                
                # 檢查是否有可用的轉錄
                if 'value' in transcripts_data and len(transcripts_data['value']) > 0:
                    transcript_content_url = transcripts_data['value'][0].get('transcriptContentUrl')
                    if transcript_content_url:
                        meeting['transcript_content_url'] = transcript_content_url
                        print(f"Transcript Content URL: {transcript_content_url}")
                    else:
                        print("No transcript content URL available.")
                else:
                    print("No transcripts available for this meeting.")
            else:
                print("Meeting not found or no valid meeting ID returned.")
            
            # 將 meeting 添加到 meetings 列表
            meetings.append(meeting)
        else:
            print("No online meeting details available.")