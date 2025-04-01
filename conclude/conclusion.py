from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import json
from pymongo import MongoClient

app = Flask(__name__)
CORS(app)  # 啟用CORS

# 連接到 MongoDB
client = MongoClient('localhost', 27017)
db = client.summary
collection = db.meetings

@app.route('/conclusion', methods=['POST'])
def conclusion():
    data = request.json
    subject = data.get('subject')

    if not subject:
        return jsonify({"error": "Meeting subject is required."}), 400

    # 從 MongoDB 中查找對應的會議記錄
    meeting_record = collection.find_one({'subject': subject})

    if not meeting_record:
        return jsonify({"error": "Meeting not found in database. Please input the identical Meeting Subject again."}), 404

    # 提取 subject, date, 和 summary
    meeting_info = {
        "subject": meeting_record.get('subject'),
        "date": meeting_record.get('date'),
        "summary": meeting_record.get('summary')
    }

    return jsonify(meeting_info)

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