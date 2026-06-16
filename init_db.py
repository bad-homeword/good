import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'ecommerce.db')

def init_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("正在建立所有必要的資料表...")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT DEFAULT 'user'
    );""")
    
    # 🔥 關鍵修正：欄位完全對齊 server.js 的 5 個欄位，型態也完全一致！
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price REAL,
        description TEXT,
        image TEXT
    );""")
    
    # 🔥 關鍵修正：欄位完全對齊 server.js 的 5 個欄位 (id, username, total, items, status)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        total REAL,
        items TEXT,
        status TEXT DEFAULT 'Pending'
    );""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS faq (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT,
        answer TEXT
    );""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_message TEXT,
        ai_response TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );""")
    
    print("資料表結構確認成功！正在清理舊資料並寫入球鞋測試資料...")
    
    tables = ['users', 'products', 'orders', 'faq', 'chat_logs']
    for table in tables:
        cursor.execute(f"DELETE FROM {table}")
    
    # 1. 建立測試用戶（密碼對齊，並塞入管理員帳號）
    cursor.execute("INSERT INTO users (id, username, password, role) VALUES (1, 'ellen', 'password123', 'user')")
    
    # 2. 塞入 20 筆熱門球鞋商品 (滿足題目 20 項商品門檻)
    # 欄位對應順序：(id, name, price, description, image)
    products_data = [
        (1, 'Nigel Sylvester X Air Jordan 4', 5500, '與極限單車（BMX）運動員 Nigel Sylvester 合作的全新低筒變體版 AJ4 RM。將傳統 AJ4 大幅改裝，包覆感更好且更耐磨。尺寸：US 7.5 - US 11。風格：美式街頭。', 'images/shoes01.jpg'),
        (2, 'A$AP Rocky X Puma Mostro 3D Mule', 9500, '由潮流 Icon A$AP Rocky 親自操刀，將 Puma 世紀初的經典怪鞋 Mostro 以全 3D 列印技術重新建模，演變成充滿尖刺、極具未來侵略性的黑紅/藍色穆勒半拖鞋。尺寸：US 7.5 - US 11。風格：前衛。', 'images/shoes02.jpg'),
        (3, 'nonnative X asics Gel Terrain Gore-Tex', 9000, '日本頂級城市機能品牌 nonnative 與 Asics 的聯名，以大地色系貫穿，並注入 Gore-Tex 防水科技，將戶外越野鞋轉化為極具質感的都市機能單品。尺寸：US 7.5 - US 11。風格：機能。', 'images/shoes03.jpg'),
        (4, 'jjjjound X new balance 993', 16000, '蒙特婁設計工作室 JJJJound 帶來的 MiUSA 993 聯名。採用標誌性的「Mushroom 蕈菇褐」與「Military Grey 軍事灰」麂皮，延續極致的無商標低調美學。尺寸：US 7.5 - US 11。風格：極簡百搭。', 'images/shoes04.jpg'),
        (5, 'new balance 1906L', 5500, 'NB 的破格之作，將大熱的 1906R 科技跑鞋底，與經典「樂福鞋（Loafers）」的皮革鞋面融合。成功將皮鞋的優雅與跑鞋的舒適結合。尺寸：US 7.5 - US 11。風格：千禧復古。', 'images/shoes05.jpg'),
        (6, 'CLOT x adidas originals Superstar', 5500, '將傳統貝殼頭重新改造，邊緣融入鋸齒狀的紳士皮鞋沿條（Welt），部分版本更採用網眼布或草編感，重新定義街頭經典。尺寸：US 7.5 - US 11。風格：新中式。', 'images/shoes06.jpg'),
        (7, 'Adidas Wonder Runner Turbo', 5000, 'Adidas 內部高級支線衍生出的概念鞋款，鞋底採用誇張的機械結構感與 Turbo 緩震線條，充滿強烈的千禧年未來速度感。尺寸：US 7.5 - US 11。風格：未來感。', 'images/shoes07.jpg'),
        (8, 'New Balance Terrace Mule', 3200, '以室內網球或復古德訓鞋底為靈感，延伸出來的極簡復古皮質穆勒鞋。一體成型的低調輪廓，主打隨穿隨走的鬆弛感。尺寸：US 7.5 - US 11。風格：日系休閒。', 'images/shoes08.jpg'),
        (9, 'Post Archive Faction (PAF) x On 2.0', 8500, '韓國先鋒機能時裝品牌 PAF 與瑞士跑鞋新貴 On 的第二代聯名。將 PAF 標誌性的不對稱流線剪裁與結構線條，完美融入 On 的立體緩震科技中。尺寸：US 7.5 - US 11。風格：先鋒機能。', 'images/shoes09.jpg'),
        (10, 'Liberaiders × Puma suede', 4800, '由梅詠主導的日本街頭工裝品牌 Liberaiders 與 Puma 傳奇鞋款 Suede 的聯名。運用高級長毛麂皮與標誌性的「軍事藍/紙鶴反光細節」，展現日式街頭反叛與 Old School 的融合。尺寸：US 7 - US 12。風格：美式復古。', 'images/shoes10.jpg'),
        (11, 'UNDEFEATED × Dodgers × Converse Chuck 70', 3600, '洛杉磯潮流元老 UNDEFEATED 攜手在地傳奇球隊「道奇隊（Dodgers）」與 Converse 的三方聯名，以道奇藍與標誌性刺繡字體呈現，充滿西海岸棒球情懷。尺寸：US 3 - US 13。風格：經典復古。', 'images/shoes11.jpg'),
        (12, 'Mizuno Racer Trail SE', 4280, 'Mizuno 將其引以為傲的復古專業跑鞋基因，與越野山系大底結合的特殊版本。鞋面結構繁複，充滿千禧年科技感。尺寸：US 7 - US 12。風格：戶外機能。', 'images/shoes12.jpg'),
        (13, 'Kith X New Balance 990v4', 14000, 'Ronnie Fieg 掌舵的 Kith 與 NB 的定番聯名。通常採用極致高級的調色盤，搭配頂級皮質，質感甚至超越常規美製。尺寸：US 5 - US 12。風格：Clean-fit。', 'images/shoes13.jpg'),
        (14, 'Dr.Martens beams', 7800, '馬汀大夫與日本選品巨頭 BEAMS 的長期聯名。常常將經典 1461 三孔鞋或穆勒鞋款改為「無鞋帶/隱藏式鬆緊帶」或加上「白縫線」，帶有濃厚的日式叛逆紳裝感。尺寸：US 3 - US 12。風格：英倫龐克風。', 'images/shoes14.jpg'),
        (15, 'Union LA X Fragment Design X Air Jordan 1 High OG', 40000, '結合了 Union 的解構拼接邊緣、做舊美學，以及Fragment Design最具號召力的閃電標誌與經典藍黑白配色。尺寸：US 7 - US 15。風格：收藏。', 'images/shoes15.jpg'),
        (16, 'Adidas Climacool Laced', 4200, '經典 360 度全方位透氣科技 Climacool 的摩登進化版。全鞋面佈滿透氣網眼，搭配立體切割的 TPU 支撐條，主打極致的夏季透氣度。尺寸：US 4 - US 13。風格：日常通勤、實用性。', 'images/shoes16.jpg'),
        (17, 'Clot X adidas originals superstar', 7500, '陳冠希設計的另一款全黑或經典黑白配色的鋸齒沿條 Superstar。將傳統的運動休閒鞋用高級黑色皮革重新包裹，打造宛如正裝皮鞋的質感。尺寸：US 4 - US 13。風格：clean-fit。', 'images/shoes17.jpg'),
        (18, 'Kith × Danielle Cathari X NB 991v2', 15000, 'Kith 聯手阿姆斯特丹新銳女裝設計師 Danielle Cathari 與 NB 推出的三方聯名。在英製 991v2 的優雅鞋型上，注入了極具女性張力卻不失高級感的調色。尺寸：US 5 - US 12。風格：摩登知性。', 'images/shoes18.jpg'),
        (19, 'ALD × New Balance 993', 14500, '由紐約復古美學品牌 ALD 與 NB 的經典聯名 993，將美式紐約復古輕奢（Aimé Aesthetics）發揮到極致。尺寸：US 5 - US 12。風格：美式復古。', 'images/shoes19.jpg'),
        (20, 'Mizuno WAVE RIDER 10 SBTG', 6500, 'Mizuno 與新加坡 SBTG 的聯名。以 Wave Rider 10 為藍本，注入 SBTG 最核心的「軍事手繪迷彩、重工業軍綠、以及標誌性的字體印記」。尺寸：US 7 - US 12。風格：重工業街頭。', 'images/shoes20.jpg')
    ]
    
    # 🔥 關鍵修正：executemany 欄位數量跟上面完全對齊，絕不產生卡死或錯位
    cursor.executemany(
        "INSERT INTO products (id, name, price, description, image) VALUES (?, ?, ?, ?, ?)", 
        products_data
    )
    
    # 3. 建立一筆預設測試訂單，買了第一雙 AJ4 
    cursor.execute("""
        INSERT INTO orders (id, username, total, items, status) VALUES 
        (1, 'ellen', 5500, '[{"id":1,"name":"Nigel Sylvester X Air Jordan 4","price":5500,"quantity":1,"size":"US 9.0"}]', '備貨中')
    """)
    
    # 4. 塞入球鞋店專屬 RAG FAQ 問答資料庫
    cursor.execute("""
        INSERT INTO faq (question, answer) VALUES 
        ('球鞋尺寸怎麼選', '我們的球鞋多數為正常版型。若您的腳板偏寬，建議選購大半號（0.5cm）穿起來會比較舒適喔！'),
        ('請問保證正品嗎', '本店所有球鞋皆由國內外正規經銷商管道購入，保證 100% 正品公司貨，附原廠鞋盒，請放心選購。'),
        ('配送方式與運費', '目前提供四大超商取貨與黑貓宅配。全館球鞋單筆滿 3000 元即享免運費優惠。'),
        ('收到鞋子尺寸不合可以退換嗎', '收到商品 7 天內，在「鞋底無磨損、鞋盒配件完整、吊牌未拆」的前提下，皆可聯繫客服辦理尺寸更換。')
    """)
    
    conn.commit()
    conn.close()
    print("KicksTrend 潮流選品店 20項商品與測試資料全面對齊填入完成！")

if __name__ == "__main__":
    init_database()