from flask import Flask, request, jsonify
from ai_agent import ask_ai_custom_service  # 引入你寫好的核心

app = Flask(__name__)

@app.route('/api/chat', methods=['POST'])
def chat_api():
    data = request.get_json()
    if not data:
        return jsonify({"error": "請提供聊天內容"}), 400
        
    username = data.get('username', '訪客')
    user_message = data.get('message', '')
    
    if not user_message:
        return jsonify({"error": "訊息不能為空"}), 400
        
    # 呼叫你的 Gemini RAG 核心
    ai_response = ask_ai_custom_service(username, user_message)
    
    return jsonify({"response": ai_response})

if __name__ == '__main__':
    # 本機測試時用，正式部署會被 Gunicorn 接管
    app.run(port=5000, debug=True)