import sqlite3
import requests
import difflib

DB_PATH = 'ecommerce.db'
# 🔥 請填入你們組別的 Gemini API Key
GEMINI_API_KEY = "AQ.Ab8RN6Ls5m5Xn77sS5HrI3bfA4zT_kgyJAODiIm2Ejb1O4O4Ag" 

def retrieve_knowledge(user_message):
    """【極速 RAG】利用關鍵字與模糊字串比對，快速篩選最相關的球鞋或 FAQ"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    candidates = []
    
    # A. 撈球鞋常見問題
    try:
        cursor.execute("SELECT question, answer FROM faq")
        for q, a in cursor.fetchall():
            candidates.append(f"常見問題：{q}？解答：{a}")
    except sqlite3.OperationalError:
        pass
        
    # B. 撈球鞋商品資訊
    # 💡 修正 2：對齊 server.js 的 products 欄位 (name, price, description)，移除不存在的 category
    cursor.execute("SELECT name, description, price FROM products")
    for name, desc, price in cursor.fetchall():
        candidates.append(f"鞋款名稱：{name}，描述：{desc}，價格：{price}元。")
        
    conn.close()
    
    # 模糊搜尋最相關的 3 筆資料餵給 AI 當作上下文
    best_matches = difflib.get_close_matches(user_message, candidates, n=3, cutoff=0.1)
    
    return "\n".join(best_matches) if best_matches else "暫無相關球鞋或常見問題資料。"

# 💡 修正 3：將第一個參數從 user_id 改為 username，因為 server.js 是存帳號文字
def ask_ai_custom_service(username, user_message):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    db_context = ""
    
    # 1. 精準攔截：使用者想查詢球鞋訂單進度
    if "訂單" in user_message and any(k in user_message for k in ["查", "進度", "狀態", "到哪", "號"]):
        # 💡 修正 4：對齊 server.js 的 orders 欄位 (id, total, status) 與查詢條件 (username)
        # 因為 server.js 的 orders 沒有 created_at 欄位，我們改用 id DESC 排序抓最後一筆
        try:
            cursor.execute("""
                SELECT id, total, status 
                FROM orders 
                WHERE username = ? 
                ORDER BY id DESC LIMIT 1
            """, (username,))
            order = cursor.fetchone()
            
            if order:
                db_context = f"【系統查詢到該用戶最新球鞋訂單】\n訂單編號: {order[0]}, 總金額: {order[1]}元, 當前物流狀態: {order[2]}。"
            else:
                db_context = f"【系統查詢結果】該用戶「{username}」目前在系統中沒有任何球鞋訂單紀錄。"
        except sqlite3.OperationalError as e:
            db_context = f"【系統查詢結果】訂單資料庫結構尚未建立完全。"
    else:
        # 2. 走 RAG 流程檢索球鞋與 FAQ 庫
        db_context = f"【從球鞋商店知識庫檢索到的相關資料】\n{retrieve_knowledge(user_message)}"
        
    conn.close()

    # 3. 調整為帥氣、專業的潮流鞋頭客服 Prompt
    system_prompt = (
        "你是一家高端潮流球鞋選品店『KicksTrend』的 AI 智能客服。你的說話風格非常具有潮流感、專業且客氣，"
        "回答時要展現你對球鞋文化與版型的了解。"
        "請嚴格根據主辦方提供的【商店參考資料】來回答問題。如果資料中沒有這雙鞋或答案，"
        "請委婉告訴鞋友並引導他們聯絡真人客服，千萬不要自己瞎編沒有的限量鞋款或店家規則！"
    )
    
    # 4. 呼叫 Gemini 雲端 API 進行生成
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{
            "parts": [{"text": f"{system_prompt}\n\n【商店參考資料】：\n{db_context}\n\n【顧客提問】：{user_message}"}]
        }]
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        res_json = response.json()
        ai_response = res_json['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        ai_response = f"抱歉，系統後台好像有點塞車，請稍等片刻再試！（錯誤原因: {e}）"
        
    # 5. 自動存入對話紀錄
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # 防呆：確保 chat_logs 表格存在
        cursor.execute("CREATE TABLE IF NOT EXISTS chat_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_message TEXT, ai_response TEXT)")
        cursor.execute("INSERT INTO chat_logs (user_message, ai_response) VALUES (?, ?)", (user_message, ai_response))
        conn.commit()
        conn.close()
    except Exception:
        pass
        
    return ai_response