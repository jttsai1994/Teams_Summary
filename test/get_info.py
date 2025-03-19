import requests
import json
from datetime import datetime, timedelta,timezone
import re
import urllib.parse


# # 發送請求到 Flask 應用程式以更新 token.json
# def update_token():
#     response = requests.get('http://127.0.0.1:5005/')
#     if response.status_code == 200:
#         print("Token updated successfully.")
#     else:
#         print("Failed to update token. Please check the server.")

# # 更新存取令牌
# update_token()
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

# 從檔案中讀取存取令牌
with open('token.json', 'r') as token_file:
    token_data = json.load(token_file)
    token = token_data.get('access_token')

# 使用存取令牌來取得過往會議資訊
events_url = 'https://graph.microsoft.com/v1.0/me/events'
headers = {
    'Authorization': f'Bearer {token}'
}
events_r = requests.get(events_url, headers=headers)
events = events_r.json()
# 列印會議資訊
ids=[]
for event in events.get('value', []):
    print(f"isOnlineMeeting:{event['isOnlineMeeting']}")
    print(f"event:{event['subject']}")
#     ids.append(event['id'])
#     print(f"開始時間: {event['start']['dateTime']}")
#     # print(f"結束時間: {event['end']['dateTime']}")
#     print(f"會議地點: {event['location']['displayName']}")
#     print('-' * 40)
# print(len(ids),ids)
# 列印會議資訊
for event in events.get('value', [])[:1]:
    print(f"isOnlineMeeting: {event['isOnlineMeeting']}")
    print(f"會議主題: {event['subject']}")
    # print(f"id:{event['id']}")
    # ids.append(event['id'])
    if event['isOnlineMeeting']:
        online_meeting_info = event.get('onlineMeeting')
        if online_meeting_info:
            # Join URL
            join_url = online_meeting_info.get('joinUrl')
            # 解碼 URL
            decoded_url = urllib.parse.unquote(join_url)
            print(f'joinUrl:{decoded_url}')
            # 使用正則表達式提取完整的會議 ID
            match = re.search(r'/meetup-join/([^@]+)@thread.v2', decoded_url)
            if match:
                meeting_id = match.group(1)
                encoded_meeting_id = urllib.parse.unquote(meeting_id)
                print(f"Meeting ID: {encoded_meeting_id}")
                ids.append(encoded_meeting_id)
            else:
                print("Meeting ID not found.")
        else:
            print("No online meeting details available.")

# --------------------------------------------------------------------------

# # 使用存取令牌來取得線上會議資訊
# online_meetings_url = 'https://graph.microsoft.com/v1.0/me/onlineMeetings'
# headers = {
#     'Authorization': f'Bearer {token}'
# }
# online_meetings_r = requests.get(online_meetings_url, headers=headers)
# online_meetings = online_meetings_r.json()

# print(online_meetings)
# 檢查是否成功獲取線上會議
# if 'value' not in online_meetings:
#     print("Failed to retrieve online meetings.")
# else:
#     # 迭代每個線上會議以獲取會議 ID
#     for meeting in online_meetings['value']:
#         meeting_id = meeting['id']  # 提取會議的 ID
#         print(f"會議 ID: {meeting_id}")

#         # 使用會議 ID 來獲取文字紀錄
#         transcripts_url = f'https://graph.microsoft.com/v1.0/me/onlineMeetings/{meeting_id}/transcripts'
#         transcripts_r = requests.get(transcripts_url, headers=headers)
        
#         # 檢查是否成功獲取文字紀錄
#         if transcripts_r.status_code == 200:
#             transcripts = transcripts_r.json()
#             print(f"會議 ID: {meeting_id} 的文字紀錄:")
#             for transcript in transcripts.get('value', []):
#                 print(transcript['content'])
#                 print('-' * 40)
#         else:
#             print(f"Failed to retrieve transcripts for meeting ID: {meeting_id}")


# ------------------------------------------

# # 設定時間範圍，使用時區感知的 datetime
# start_time = datetime.now(timezone.utc) - timedelta(days=30)  # 過去30天
# end_time = datetime.now(timezone.utc) + timedelta(days=30)    # 未來30天

# # 確保日期時間格式符合 API 要求
# start_time_str = start_time.isoformat(timespec='seconds').replace('+00:00', 'Z')
# end_time_str = end_time.isoformat(timespec='seconds').replace('+00:00', 'Z')

# print(start_time_str, end_time_str)  # 印出來檢查格式

# 使用存取令牌來取得線上會議資訊，並使用 $filter 來過濾
idString = ids[0]
online_meetings_url = (
    f"https://graph.microsoft.com/v1.0/me/onlineMeetings/{idString}/transcripts"
)
headers = {
    'Authorization': f'Bearer {token}'
}
online_meetings_r = requests.get(online_meetings_url, headers=headers)
online_meetings = online_meetings_r.json()
print(online_meetings)
# # 檢查是否成功獲取線上會議
# if 'value' not in online_meetings:
#     print("Failed to retrieve online meetings.")
# else:
#     print("Online Meetings:")
#     for meeting in online_meetings['value']:
#         print(meeting['id'])