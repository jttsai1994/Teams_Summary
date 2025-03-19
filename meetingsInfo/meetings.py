import requests
import json
import urllib.parse
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # 啟用CORS

def load_access_token():
    """從檔案中讀取存取令牌"""
    with open('token.json', 'r') as token_file:
        token_data = json.load(token_file)
        return token_data.get('access_token')

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
    """使用存取令牌來取得過往會議資訊"""
    events_url = 'https://graph.microsoft.com/v1.0/me/events'
    headers = {'Authorization': f'Bearer {token}'}
    events_r = requests.get(events_url, headers=headers)
    events = events_r.json()

    meetings = []
    for event in events.get('value', []):
        if event['isOnlineMeeting']:
            online_meeting_info = event.get('onlineMeeting')
            if online_meeting_info:
                meeting = {}
                meeting['subject'] = event['subject']
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
                    meeting['Meeting ID'] = meeting_id
                    transcripts_url = f"https://graph.microsoft.com/v1.0/me/onlineMeetings/{meeting_id}/transcripts"
                    transcripts_response = requests.get(transcripts_url, headers=headers)
                    transcripts_data = transcripts_response.json()
                    
                    if 'value' in transcripts_data and len(transcripts_data['value']) > 0:
                        transcript_content_url = transcripts_data['value'][0].get('transcriptContentUrl')
                        if transcript_content_url:
                            meeting['transcript_content_url'] = transcript_content_url
                            print(f"Transcript Content URL: {transcript_content_url}")
                        else:
                            print("No transcript content URL available.")
                            meeting['transcript_content_url'] = False
                    else:
                        print("No transcripts available for this meeting.")
                else:
                    print("Meeting not found or no valid meeting ID returned.")
                
                meetings.append(meeting)
            else:
                print("No online meeting details available.")
    return meetings

@app.route('/getMeetings', methods=['GET'])
def meetings_list():
    """返回所有會議資訊"""
    token = load_access_token()
    user_id = get_user_info(token)
    if user_id:
        meetings = get_meetings(token, user_id)
        return jsonify({'meetings': meetings})
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