const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const jwt = require('jsonwebtoken');
const bcrypt = require('bcryptjs');
const path = require('path');

const app = express();
const PORT = 3000;
const JWT_SECRET = 'your-super-secret-key';

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));
app.use('/images', express.static(path.join(__dirname, 'public', 'images')));

// ==========================================
// 1. 資料庫初始化 (SQLite 實體檔案模式)
// ==========================================
const db = new sqlite3.Database('ecommerce.db', (err) => {
    if (err) return console.error(err.message);
    console.log('Connected to the physical SQLite database (ecommerce.db).');
});

db.serialize(() => {
    db.run(`CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, role TEXT DEFAULT 'user')`);
    db.run(`CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, price REAL, description TEXT, image TEXT)`);
    db.run(`CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, total REAL, items TEXT, status TEXT DEFAULT 'Pending')`);
    db.run(`CREATE TABLE IF NOT EXISTS faq (id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT, answer TEXT)`);

    // 預設建立一個管理者帳號 (admin / admin123)
    const hashedAdminPwd = bcrypt.hashSync('admin123', 8);
    db.run(`INSERT OR IGNORE INTO users (username, password, role) VALUES ('admin', '${hashedAdminPwd}', 'admin')`);

    // 💡 關鍵修正：移除原本會亂灌 9 雙無效規格商品的 defaultProducts 邏輯！
    // 讓系統全權交給 init_db.py 來初始化 20 雙帶有正確尺寸限制的限量球鞋。
    db.get(`SELECT COUNT(*) as count FROM products`, [], (err, row) => {
        if (row && row.count === 0) {
            console.log('⚠️ 偵測到資料庫無商品，請務必先執行一次 python init_db.py 灌入 20 雙標準潮流球鞋喔！');
        }
    });

    // 預設建立幾筆 FAQ 範例資料
    db.get(`SELECT COUNT(*) as count FROM faq`, [], (err, row) => {
        if (row && row.count === 0) {
            const stmt = db.prepare(`INSERT INTO faq (question, answer) VALUES (?, ?)`);
            stmt.run(['請問運費怎麼計算？', '全店球鞋消費滿 NT$3000 即享免運優惠，未滿則酌收 NT$80 運費。']);
            stmt.run(['商品收到後可以退換貨嗎？', '我們提供 7 天鑑賞期，若尺寸不合且鞋底無磨損，可在收到商品 7 天內申請更換尺寸一次。']);
            stmt.finalize();
        }
    });
});

// ==========================================
// 2. 認證中間件 (Middleware)
// ==========================================
const authenticateJWT = (req, res, next) => {
    const authHeader = req.headers.authorization;
    if (authHeader) {
        const token = authHeader.split(' ')[1];
        jwt.verify(token, JWT_SECRET, (err, user) => {
            if (err) return res.sendStatus(403); 
            req.user = user;
            next();
        });
    } else {
        res.sendStatus(401);
    }
};

// ==========================================
// 3. API 路由 (Routes)
// ==========================================

// 註冊與登入
app.post('/api/auth/register', (req, res) => {
    const { username, password } = req.body;
    const hashedPassword = bcrypt.hashSync(password, 8);
    db.run(`INSERT INTO users (username, password) VALUES (?, ?)`, [username, hashedPassword], function(err) {
        if (err) return res.status(400).json({ error: '帳號已被註冊' });
        res.json({ message: '註冊成功' });
    });
});

app.post('/api/auth/login', (req, res) => {
    const { username, password } = req.body;
    db.get(`SELECT * FROM users WHERE username = ?`, [username], (err, user) => {
        if (err || !user || !bcrypt.compareSync(password, user.password)) {
            return res.status(400).json({ error: '帳號或密碼錯誤' });
        }
        const token = jwt.sign({ username: user.username, role: user.role }, JWT_SECRET, { expiresIn: '24h' });
        res.json({ token, role: user.role, username: user.username });
    });
});

// 前台：商品列表
app.get('/api/products', (req, res) => {
    db.all(`SELECT * FROM products`, [], (err, rows) => {
        if (err) return res.status(500).json({ error: err.message });

        // 物理修正：遍歷所有商品，確保 image 欄位開頭一定有 images/ 資料夾路徑
        const fixedRows = rows.map(p => {
            let imgName = p.image || 'shoes01.jpg';
            imgName = imgName.replace('images/', ''); 
            return {
                ...p,
                image: `images/${imgName}` 
            };
        });
        res.json(fixedRows);
    });
});

// 前台：單一商品詳情（💡 修正：強制轉換 ID 型態為 Number，防止字串與整數查無資料）
app.get('/api/products/:id', (req, res) => {
    const productId = Number(req.params.id);
    db.get(`SELECT * FROM products WHERE id = ?`, [productId], (err, row) => {
        if (err) return res.status(500).json({ error: err.message });
        if (!row) return res.status(404).json({ error: "商品未找到" });
        
        let imgName = row.image || 'shoes01.jpg';
        imgName = imgName.replace('images/', ''); 
        
        res.json({
            ...row,
            image: `images/${imgName}`
        });
    });
});

// 前台：送出訂單
app.post('/api/orders', (req, res) => {
    const { username, total, items } = req.body;
    db.run(`INSERT INTO orders (username, total, items) VALUES (?, ?, ?)`, [username || '訪客', total, JSON.stringify(items)], function(err) {
        if (err) return res.status(500).json({ error: err.message });
        res.json({ message: '訂單建立成功', orderId: this.lastID });
    });
});

// 後台：商品 CRUD
app.post('/api/admin/products', authenticateJWT, (req, res) => {
    if (req.user.role !== 'admin') return res.sendStatus(403);
    const { name, price, description, image } = req.body;
    db.run(`INSERT INTO products (name, price, description, image) VALUES (?, ?, ?, ?)`, [name, price, description, image], function(err) {
        res.json({ message: '新增成功', id: this.lastID });
    });
});

app.put('/api/admin/products/:id', authenticateJWT, (req, res) => {
    if (req.user.role !== 'admin') return res.sendStatus(403);
    const { name, price, description, image } = req.body;
    db.run(`UPDATE products SET name=?, price=?, description=?, image=? WHERE id=?`, [name, price, description, image, req.params.id], function(err) {
        res.json({ message: '更新成功' });
    });
});

app.delete('/api/admin/products/:id', authenticateJWT, (req, res) => {
    if (req.user.role !== 'admin') return res.sendStatus(403);
    db.run(`DELETE FROM products WHERE id=?`, [req.params.id], function(err) {
        res.json({ message: '刪除成功' });
    });
});

// 後台：查看所有訂單
app.get('/api/admin/orders', authenticateJWT, (req, res) => {
    if (req.user.role !== 'admin') return res.sendStatus(403);
    db.all(`SELECT * FROM orders ORDER BY id DESC`, [], (err, rows) => res.json(rows));
});

// 後台：修改訂單狀態 API
app.put('/api/admin/orders/:id', authenticateJWT, (req, res) => {
    if (req.user.role !== 'admin') return res.sendStatus(403);
    const { status } = req.body; 
    db.run(`UPDATE orders SET status = ? WHERE id = ?`, [status, req.params.id], function(err) {
        if (err) return res.status(500).json({ error: err.message });
        res.json({ message: '訂單狀態更新成功' });
    });
});

app.listen(PORT, () => console.log(`MVP Server running on http://localhost:${PORT}`));
// 智慧轉運站：讓 ngrok 外網請求也能完美接通本地的 Python AI 客服
app.post('/api/chat', (req, res) => {
    fetch('http://localhost:5000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req.body)
    })
    .then(response => response.json())
    .then(data => res.json(data))
    .catch(err => res.status(500).json({ error: "AI 轉運失敗" }));
});