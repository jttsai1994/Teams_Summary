import json
from datetime import datetime
from openai import OpenAI


    
def load_prompt():
    """從文件中讀取 prompt"""
    with open('../params/prompt.txt', 'r', encoding='utf-8') as file:
        prompt = file.read()
    return prompt

def generate_summary(transcript_content, api_key, assistant_id):
    """使用助理 API 生成會議總結"""
    ASSISTANT_API = 'https://prod-davinci.one-fit.com/api/assts/v1'
    
    # 初始化 OpenAI 客戶端
    client = OpenAI(
        base_url=ASSISTANT_API,
        api_key=api_key,
    )
    
    # 讀取 prompt
    prompt = load_prompt()
    
    # 定義訊息
    messages = [
        {"type": "text", "text": f"{prompt} {transcript_content}"}
    ]

    # 建立 thread
    thread = client.beta.threads.create(messages=[])

    # 連續發送訊息
    for message in messages:
        client.beta.threads.messages.create(thread_id=thread.id, role='user', content=[message])

    # 執行 assistant
    run = client.beta.threads.runs.create_and_poll(thread_id=thread.id, assistant_id=assistant_id, additional_instructions=f"\nThe current time is: {datetime.now()}", timeout=2.0)

    while run.status == 'requires_action' and run.required_action:
        outputs = []
        for call in run.required_action.submit_tool_outputs.tool_calls:
            resp = client._client.post(ASSISTANT_API + '/pluginapi', params={"tid": thread.id, "aid": assistant_id, "pid": call.function.name}, headers={"Authorization": "Bearer " + api_key}, json=json.loads(call.function.arguments))
            # 檢查插件 API 返回值
            print("插件返回值：", resp.text)

            # 確保將插件的響應正確傳遞給助手
            outputs.append({"tool_call_id": call.id, "output": resp.text})
        run = client.beta.threads.runs.submit_tool_outputs_and_poll(run_id=run.id, thread_id=thread.id, tool_outputs=outputs, timeout=2.0)

    if run.status == 'failed' and run.last_error:
        print(run.last_error.model_dump_json())

    # 獲取生成的總結
    msgs = client.beta.threads.messages.list(thread_id=thread.id, order='desc')
    client.beta.threads.delete(thread_id=thread.id)
    summary = msgs.data[0].content[0].text.value
    return summary