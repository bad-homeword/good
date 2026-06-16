from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import requests
import difflib
import re

app = Flask(__name__)
CORS(app)

# 統一使用電商網站生成的資料庫檔案
DB_PATH = 'ecommerce.db'
GEMINI_API_KEY = "AQ.Ab8RN6Ls5m5Xn77sS5HrI3bfA4zT_kgyJAODiIm2Ejb1O4O4Ag"

# 🧠 全局對話記憶引擎：動態記住每個用戶（username）最後提及的球鞋物件
USER_CONTEXT = {}

def retrieve_knowledge(user_message, username):
    """【雙引擎意圖分流 RAG】同時檢索球鞋與 FAQ，互不衝突，完美支援連續追問"""
    global USER_CONTEXT
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # A. 安全撈取商品資訊
    products = []
    try:
        cursor.execute("SELECT name, description, price FROM products")
        products = cursor.fetchall()
    except Exception:
        pass
        
    # B. 安全撈取常見問題
    faqs = []
    try:
        cursor.execute("SELECT question, answer FROM faq")
        faqs = cursor.fetchall()
    except Exception:
        pass
    conn.close()
    
    user_msg_clean = user_message.lower()
    contexts = []
    
    # ----------------------------------------------------
    # 策略 1：球鞋品牌型號檢索與 Session 狀態機鎖定
    # ----------------------------------------------------
    matched_product = None
    for name, desc, price in products:
        clean_name = name.lower()
        # 提取核心型號關鍵字 (例如 993, Mostro, AJ4, 1906L)
        keywords = [kw for kw in re.findall(r'[a-zA-Z0-9]+', clean_name) if len(kw) > 1 and kw not in ['new', 'balance', 'nike', 'adidas', 'puma', 'asics', 'x']]
        if clean_name in user_msg_clean or any(kw in user_msg_clean for kw in keywords if kw):
            matched_product = (name, desc, price)
            USER_CONTEXT[username] = matched_product  # 寫入該用戶的專屬對話記憶
            break
            
    # 判斷使用者是不是在進行「省略主詞的連續追問」（如：尺寸呢、多少錢、那版型呢）
    is_follow_up = any(kw in user_message for kw in ["尺寸", "價錢", "價格", "多少", "幾元", "錢", "呢", "版型", "大小", "那雙", "尺碼"])
    
    # 如果當下沒提到鞋子，但屬於連續追問，且記憶體有資料，自動激活上一雙鞋
    if not matched_product and is_follow_up and username in USER_CONTEXT:
        matched_product = USER_CONTEXT[username]
        print(f"[記憶體引擎] 偵測到用戶 {username} 追問，自動帶入上一雙鞋：{matched_product[0]}")

    # 如果有鎖定特定球鞋，將商品細節裝載進 Context
    if matched_product:
        p_name, p_desc, p_price = matched_product
        contexts.append(f"【當前詢問球鞋資訊】\n鞋款名稱：{p_name}\n商品描述與尺寸規格：{p_desc}\n價格：{p_price}元。")

    # ----------------------------------------------------
    # 策略 2：店務與常見問題 FAQ 檢索機制 (並行裝載，絕不阻斷)
    # ----------------------------------------------------
    faq_keywords = {
        "配送": ["配送", "運費", "宅配", "超商", "免運", "寄送", "發貨", "黑貓", "出貨", "運送", "怎麼寄", "寄到"],
        "正品": ["正品", "真假", "假貨", "公司貨", "正貨", "保證"],
        "尺寸": ["尺寸", "版型", "大小", "幾號", "挑選", "尺碼", "正常"],
        "退換": ["退換", "換貨", "退貨", "尺寸不合", "七天", "鑑賞期"]
    }
    
    faq_found = False
    for q, a in faqs:
        for category, keywords in faq_keywords.items():
            if category in q and any(kw in user_msg_clean for kw in keywords):
                contexts.append(f"【商店店務常見問題】\n問題：{q}？\n解答：{a}")
                faq_found = True
                break
        if faq_found:
            break

    # ----------------------------------------------------
    # 策略 3：若前兩者皆空，啟動傳統模糊比對兜底
    # ----------------------------------------------------
    if not contexts:
        candidates = []
        for q, a in faqs: candidates.append(f"常見問題：{q}？解答：{a}")
        for name, desc, price in products: candidates.append(f"鞋款名稱：{name}，描述：{desc}，價格：{price}元。")
        best_matches = difflib.get_close_matches(user_message, candidates, n=2, cutoff=0.02)
        if best_matches:
            contexts.append("【模糊檢索參考資料】\n" + "\n".join(best_matches))
            
    return "\n\n".join(contexts) if contexts else "暫無相關球鞋或常見問題資料。"


@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message', '')
    username = data.get('username', '訪客')
    
    # 強制去除前後空格，防止因為空白字元導致字串比對失敗
    if isinstance(username, str):
        username = username.strip()
    
    # 🔍 終端機日誌：第一時間抓出前端傳了什麼鬼名字
    print("\n" + "="*50)
    print(f"[收到訊息] 誰在說話: '{username}' | 訊息內容: {user_message}")
    print("="*50)
    
    db_context = ""
    
    # 偵測是否在詢問運送、配送相關問題，用來與訂單精準分流
    is_asking_shipping = any(kw in user_message for kw in ["運送", "配送方式", "怎麼寄", "運費", "免運"])
    
    # 1. 訂單查詢精準攔截
    if "訂單" in user_message and any(k in user_message for k in ["查", "進度", "狀態", "到哪"]) and not is_asking_shipping:
        
        # 💡 安全防禦第一關：不管是查編號還是盲查，只要名字是訪客或空的，一律直接在後端封殺！
        if username in ["訪客", "", None, "guest", "訪客 "]:
            print(f"🛑 [攔截攔阻] 用戶名為 '{username}'，屬於未登入或訪客狀態，拒絕查詢訂單。")
            return jsonify({
              "reply": "查不到您的訂單資料，請確認您是否已經成功登入正確帳號喔！"
            })
            
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        order = None
        
        # A. 檢查對話中是否包含特定的訂單編號數字 (例：查訂單 3)
        order_id_match = re.search(r'\d+', user_message)
        if order_id_match:
            order_id = order_id_match.group()
            
            # 🔍 [核心除錯追蹤] 幫你抓出到底是誰亂寫資料庫
            try:
                cursor.execute("SELECT id, username FROM orders WHERE id = ?", (order_id,))
                raw_check = cursor.fetchone()
                if raw_check:
                    print(f"🚨 [資料庫監測] 顧客想查的訂單 ID: {order_id}")
                    print(f"🚨 [資料庫監測] 當前對話框使用者名字: '{username}'")
                    print(f"🚨 [資料庫監測] 資料庫裡這筆訂單實際擁有人名字: '{raw_check[1]}'")
                else:
                    print(f"🔍 [資料庫監測] 資料庫中根本找不到編號為 {order_id} 的訂單。")
            except Exception as db_err:
                print(f"❌ 查詢訂單擁有者時出錯，可能 orders 資料表裡沒有 username 欄位: {db_err}")

            # 💡 安全防禦第二關：SQL 加上雙重枷鎖，就算有人在訊息打數字，名字對不上就是撈不到
            cursor.execute("SELECT id, total, status FROM orders WHERE id = ? AND username = ?", (order_id, username))
            order = cursor.fetchone()
        else:
            # B. 沒指定編號，盲查該註冊用戶自己最新的一筆訂單
            print(f"🔍 [盲查模式] 正在幫用戶 '{username}' 搜尋他自己最新的一筆訂單...")
            cursor.execute("""
                SELECT id, total, status FROM orders
                WHERE username = ? ORDER BY id DESC LIMIT 1
            """, (username,))
            order = cursor.fetchone()
        
        if order:
            total_str = str(order[1])
            if total_str.endswith('.0'):
                total_str = total_str[:-2]
            db_context = f"【系統查詢到該用戶最新球鞋訂單】\n訂單編號: {order[0]}, 總金額: {total_str}元, 當前物流狀態: {order[2]}。"
            print(f"✅ [成功防禦] 成功查到屬於 {username} 的安全訂單：#{order[0]}")
            conn.close()
        else:
            print(f"🛑 [安全阻斷] 查無此人與此編號的配對訂單，直接拒絕回應，不對外洩漏任何資訊！")
            conn.close()
            return jsonify({
              "reply": f"嗨，鞋友！查不到用戶「{username}」相對應的訂單資料喔。請確認編號是否正確，或者是否登入錯帳號了呢？🤙"
            })
            
    else:
        # 2. 執行雙引擎 RAG 檢索
        db_context = retrieve_knowledge(user_message, username)
        
    # 3. 潮流客服 System Prompt
    system_prompt = (
        "你是一家高端潮流球鞋選品店『KicksTrend』的 AI 智能客服。你的說話風格非常具有潮流感、專業且客氣，"
        "回答時要充分利用【商店參考資料】。結尾偶爾可以帶個帥氣的『🤙』。"
        "如果參考資料中同時包含【當前詢問球鞋資訊】與【商店店務常見問題】，請智慧地進行整合回答。"
        "例如：顧客問特定鞋子尺寸，請先報出該鞋款描述裡的具體尺寸區間，再補上店家的通用版型建議。"
        "如果資料中真的找不到答案，請引導他們聯絡真人客服，千萬不要自己瞎編！"
    )
    
    # 4. 呼叫 Gemini 雲端 API
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": f"{system_prompt}\n\n【商店參考資料】：\n{db_context}\n\n【顧客提問】：{user_message}"}]}]
    }
    
    ai_response = ""
    try:
        # 🚀 真正向雲端發送請求
        response = requests.post(url, json=payload, timeout=10)
        res_json = response.json()
        
        if 'candidates' in res_json and len(res_json['candidates']) > 0:
            ai_response = res_json['candidates'][0]['content']['parts'][0]['text'].strip()
        else:
            raise Exception("Gemini 未正常回傳資料，轉由本地防護網應答")
            
    except Exception as e:
        print(f"[本地防護網防禦啟動] 原因: {e}")
        # === 🛠️ 專題高防護本地應答邏輯 ===
        if "【系統查詢到該用戶最新球鞋訂單】" in db_context:
            order_id = re.search(r"訂單編號: (\d+)", db_context).group(1) if re.search(r"訂單編號: (\d+)", db_context) else "1"
            total_match = re.search(r"總金額: ([0-9.]+)元", db_context)
            if total_match:
                total = total_match.group(1)
                if total.endswith('.0'):
                    total = total[:-2]
            else:
                total = "3200"
            status = re.search(r"當前物流狀態: ([^。]+)", db_context).group(1) if re.search(r"當前物流狀態: ([^。]+)", db_context) else "Pending"
            ai_response = f"哈囉！幫你查到囉！你最新的潮流球鞋訂單編號是 #{order_id}，總金額共 {total} 元。目前的物流進度是：【{status}】。我們已經安排最快的黑貓宅急便準備發貨了啦！🤙"
        
        elif "【當前詢問球鞋資訊】" in db_context:
            name_match = re.search(r"鞋款名稱：([^\n]+)", db_context)
            desc_match = re.search(r"商品描述與尺寸規格：([^\n]+)", db_context)
            price_match = re.search(r"價格：([^\n]+)", db_context)
            
            p_name = name_match.group(1) if name_match else "這雙球鞋"
            p_desc = desc_match.group(1) if desc_match else ""
            p_price = price_match.group(1) if price_match else ""
            
            if "尺寸" in user_message or "版型" in user_message or "呢" in user_message:
                size_info = re.search(r'(尺寸\s*：\s*[^。]+)', p_desc)
                size_str = size_info.group(1) if size_info else "規格請參考官網描述"
                ai_response = f"這雙 {p_name} 目前官方說明的{size_str}。我們店內保證 100% 正品公司貨，版型通常正常，喜歡可以直接下單喔！🤙"
            elif any(kw in user_message for kw in ["價格", "多少", "錢"]):
                ai_response = f"鞋友！這雙 {p_name} 的價格是 {p_price} 喔！手刀快搶！🤙"
            else:
                ai_response = f"幫你確認好囉！{p_name} 的資訊為：{p_desc}，店內售價為 {p_price}。需要幫你留貨嗎？🤙"
                
        elif "【商店店務常見問題】" in db_context:
            ans_match = re.search(r"解答：([^\n]+)", db_context)
            faq_ans = ans_match.group(1) if ans_match else "目前全館滿 3000 免運，商品皆為 100% 公司貨正品。"
            ai_response = f"嗨，鞋友！關於你問的店務細節：{faq_ans} 🤙"
        else:
            ai_response = "哈囉！歡迎來到 KicksTrend 潮流選品店！今晚想找哪雙限量波鞋，還是想了解哪款球鞋的配送或尺寸呢？輸入「查訂單」我也能幫你搞定喔！🤙"
            
    # 5. 自動存入對話紀錄
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS chat_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_message TEXT, ai_response TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)")
        cursor.execute("INSERT INTO chat_logs (user_message, ai_response) VALUES (?, ?)", (user_message, ai_response))
        conn.commit()
        conn.close()
    except Exception:
        pass
        
    return jsonify({"reply": ai_response})

if __name__ == '__main__':
    app.run(port=5000, debug=True)