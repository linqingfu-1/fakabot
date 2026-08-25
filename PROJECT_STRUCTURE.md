# 📁 项目结构说明

## 核心文件

### 主程序
- `bot.py` (37KB) - 主程序入口，Flask服务器，支付回调处理
- `user_flow.py` (58KB) - 用户交互流程，订单创建，支付处理
- `admin_panel.py` (103KB) - 管理员面板，商品管理，订单管理

### 支付模块
- `payments.py` (6.7KB) - 支付统一接口
- `payments_lemzf_official.py` (11KB) - 柠檬支付官方对接

### 缓存和限流
- `redis_cache.py` (7.6KB) - Redis缓存模块
- `rate_limiter.py` (6.3KB) - 频率限制模块

### 工具模块
- `utils.py` (15KB) - 工具函数，数据库操作
- `screenshot_utils.py` (12KB) - 支付页面截图

### 配置文件
- `config.json` (1.8KB) - 主配置文件（需自行配置）
- `requirements.txt` (176B) - Python依赖
- `Dockerfile` (832B) - Docker镜像构建
- `docker-compose.yml` (735B) - Docker编排配置

### 文档
- `README.md` - 项目说明
- `CHANGELOG.md` - 更新日志
- `deploy/MULTI_BOT_USDT_DEPLOYMENT.md` - 多机器人 USDT 扫链部署文档（含 Nginx/HTTPS）
- `deploy/deploy_multi_bot.sh` - 多机器人一键部署脚本
- `.gitignore` - Git忽略文件

---

## 目录结构

```
fakabot/
├── 📄 核心代码
│   ├── bot.py                          # 主程序（Flask + Telegram Bot）
│   ├── user_flow.py                    # 用户流程处理
│   ├── admin_panel.py                  # 管理员面板
│   ├── payments.py                     # 支付处理
│   ├── payments_lemzf_official.py      # 柠檬支付
│   ├── redis_cache.py                  # Redis缓存
│   ├── rate_limiter.py                 # 频率限制
│   ├── utils.py                        # 工具函数
│   └── screenshot_utils.py             # 截图工具
│
├── ⚙️ 配置文件
│   ├── config.json                     # 主配置（需配置）
│   ├── requirements.txt                # Python依赖
│   ├── Dockerfile                      # Docker镜像
│   └── docker-compose.yml              # Docker编排
│
├── 📚 文档
│   ├── README.md                       # 项目说明
│   ├── CHANGELOG.md                    # 更新日志
│   ├── deploy/                         # 部署文档与脚本
│   │   ├── MULTI_BOT_USDT_DEPLOYMENT.md # 多机器人部署文档
│   │   ├── REWRITE_DOCKER_COMPOSE.md    # compose 修复文档
│   │   └── deploy_multi_bot.sh          # 一键部署脚本
│   ├── PROJECT_STRUCTURE.md            # 项目结构（本文件）
│   └── .gitignore                      # Git忽略
│
└── 💾 数据目录（运行时生成）
    └── data/
        └── fakabot.db                  # SQLite数据库
```

---

## 代码模块说明

### bot.py - 主程序
**功能**：
- Flask Web服务器
- Telegram Bot初始化
- 支付回调处理（柠檬支付/TOKEN188）
- 订单超时管理
- 健康检查接口

**关键函数**：
- `pay_callback()` - 支付回调处理
- `handle_token188_callback()` - TOKEN188回调
- `job_cancel_expired()` - 订单超时取消
- `_mark_paid_and_deliver()` - 标记已支付并发货

---

### user_flow.py - 用户流程
**功能**：
- 用户命令处理（/start, /shop等）
- 商品列表展示
- 支付方式选择
- 订单创建和预加载
- 支付链接生成
- 订单查询

**关键函数**：
- `cb_pay()` - 支付方式选择
- `_create_payment_order()` - 创建支付订单
- `cb_order_list()` - 订单列表

---

### admin_panel.py - 管理员面板
**功能**：
- 商品管理（增删改查）
- 订单管理
- 用户管理
- 统计数据
- 系统设置

**关键功能**：
- 商品上下架
- 订单状态修改
- 数据统计
- 配置管理

---

### payments.py - 支付处理
**功能**：
- 支付统一接口
- 支付网关对接
- 签名生成和验证

---

### redis_cache.py - Redis缓存
**功能**：
- Redis连接管理
- 缓存读写
- 自动过期
- 降级处理

**缓存类型**：
- 商品信息（5分钟）
- 配置信息（10分钟）
- 用户会话（1小时）

---

### rate_limiter.py - 频率限制
**功能**：
- 用户操作限流
- IP限流
- 自动重置
- 降级处理

**限制规则**：
- 用户命令：20次/分钟
- 创建订单：5次/5分钟
- 查询订单：10次/分钟
- IP回调：100次/分钟

---

### utils.py - 工具函数
**功能**：
- 数据库操作
- 消息发送
- 键盘生成
- 设置管理

---

### screenshot_utils.py - 截图工具
**功能**：
- 支付页面截图
- 二维码生成
- Selenium自动化

---

## 数据库表结构

### products - 商品表
- id, name, price, cover_url, full_description, status

### orders - 订单表
- id, user_id, product_id, amount, payment_method, status, out_trade_no, create_time

### card_keys - 卡密表
- id, product_id, card_key, status

### settings - 设置表
- key, value

### last_msgs - 最后消息表
- chat_id, message_id

### usdt_transactions - USDT交易表
- id, out_trade_no, transaction_id, from_address, amount, create_time

---

## 配置说明

### config.json
```json
{
  "BOT_TOKEN": "Telegram Bot Token",
  "ADMIN_ID": 管理员用户ID,
  "DOMAIN": "域名",
  "USE_WEBHOOK": true/false,
  "WEBHOOK_PATH": "/tg/webhook",
  "ORDER_TIMEOUT_SECONDS": 3600,
  "SHOW_QR": false,
  "STRICT_CALLBACK_SIGN_VERIFY": true,
  "ENABLE_PAYMENT_SCREENSHOT": true,
  "PAYMENTS": {
    "alipay": {...},
    "wxpay": {...},
    "usdt_lemon": {...},
    "usdt_token188": {...}
  }
}
```

---

## 环境变量

### Docker环境变量
- `TZ` - 时区（Asia/Shanghai）
- `REDIS_HOST` - Redis主机（redis）
- `REDIS_PORT` - Redis端口（6379）
- `DATA_DIR` - 数据目录（/app/data）

---

## 端口说明

- `58001` - Flask Web服务器（支付回调）
- `58002` - 备用端口
- `6379` - Redis（容器内部）

---

## 文件大小统计

| 文件 | 大小 | 说明 |
|------|------|------|
| admin_panel.py | 103KB | 管理员面板 |
| bot.py | 37KB | 主程序 |
| user_flow.py | 58KB | 用户流程 |
| utils.py | 15KB | 工具函数 |
| screenshot_utils.py | 12KB | 截图工具 |
| payments_lemzf_official.py | 11KB | 柠檬支付 |
| redis_cache.py | 7.6KB | Redis缓存 |
| rate_limiter.py | 6.3KB | 频率限制 |
| payments.py | 6.7KB | 支付处理 |

**总代码量**: ~256KB

---

## 依赖说明

### Python依赖
- python-telegram-bot[job-queue,webhooks]==20.6
- Flask==3.0.3
- requests==2.31.0
- qrcode==7.4.2
- Pillow==10.2.0
- waitress==2.1.2
- selenium==4.15.0
- webdriver-manager==4.0.1
- redis==5.0.1

### 系统依赖
- Python 3.11
- Redis 7
- Chromium（用于截图）

---

## 开发建议

### 代码规范
- 使用Python 3.11+
- 遵循PEP 8规范
- 添加类型注解
- 编写文档字符串

### 测试
- 单元测试
- 集成测试
- 支付回调测试

### 部署
- 使用Docker部署
- 配置反向代理（Nginx）
- 启用HTTPS
- 定期备份数据库

---

**项目整理完成！** ✨
