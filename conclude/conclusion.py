from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import json
import requests

# 從檔案中讀取存取令牌
with open('../token.json', 'r') as token_file:
    token_data = json.load(token_file)
    token = token_data.get('access_token')

app = Flask(__name__)
CORS(app)  # 啟用CORS

@app.route('/conclusion', methods=['POST'])
def conclusion():
    data = request.json
    meeting_id = data.get('meeting_id')

    if not meeting_id:
        return jsonify({"error": "Meeting ID is required."}), 400

    # 設置標頭
    headers = {
        'Authorization': f'Bearer {token}'
    }
    transcripts_url = f"https://graph.microsoft.com/v1.0/me/onlineMeetings/{meeting_id}/transcripts"
    transcripts_response = requests.get(transcripts_url, headers=headers)
    transcripts_data = transcripts_response.json()
    
    transcript_content_url = transcripts_data['value'][0]['transcriptContentUrl']
    if transcript_content_url:
        # 發送 GET 請求來讀取內容
        response = requests.get(f"{transcript_content_url}?$format=text/vtt", headers=headers)

        # 檢查響應狀態碼
        if response.status_code == 200:
            transcript_content = response.text
            print("Transcript content retrieved successfully.")
            
            # 回傳文字紀錄給 DaVinci LLM
            return Response(transcript_content, mimetype='text/vtt')
        else:
            error_message = f"Failed to retrieve content. Status code: {response.status_code}"
            print(error_message)
            return jsonify({"error": error_message}), response.status_code
    else:
        return jsonify({"error": "No transcript content URL available."}), 404


# 定義一個 API 端點來提供 OpenAPI 規範文件
@app.route("/openapi.yaml", methods=["GET"])
def openapi_spec():
    try:
        # 使用 UTF-8 編碼讀取檔案
        with open("openapi.yaml", "r", encoding="utf-8") as f:
            text = f.read()
            return Response(text, mimetype="text/yaml")
    except FileNotFoundError:
        return jsonify({"error": "OpenAPI specification file not found."}), 404   

def main():
    app.run(debug=True, host="127.0.0.1", port=5011)

if __name__ == "__main__":
    main()