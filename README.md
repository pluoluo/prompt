# Prompt Portal

AI 图像提示词管理与优化平台，基于 GPT Image 2 结构化方法论。

## 鸣谢

案例库来源：[freestylefly/awesome-gpt-image-2](https://github.com/freestylefly/awesome-gpt-image-2)

## 功能

- **模板库** — 分类筛选、关键词搜索、风格/场景标签多选
- **案例库** — 447 个 GPT Image 2 案例，中英文切换，图片懒加载
- **AI 优化生成** — MiniMax API 驱动，多轮对话，模板改写/自由生成双模式
- **提示词撰写指南** — GPT Image 2 官方指南内嵌
- **在线编辑** — 模板/案例可编辑、删除，提交新模板
- **双语切换** — 分类/风格/场景/Prompt 中英文显示

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | FastAPI + uvicorn (Python 3.11+) |
| 前端 | Vue 3 CDN 单文件 SPA |
| 数据 | JSON 文件存储 |
| 代理 | nginx |
| AI | MiniMax API (Anthropic 兼容格式) |

## 生产环境部署

### 1. 克隆仓库

```bash
git clone git@github.com:pluoluo/prompt.git
cd prompt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 API Key
```

```env
MINIMAX_API_KEY=your_api_key_here
IMAGE_API_URL=http://localhost:8766
```

### 3. 安装依赖

```bash
pip install fastapi uvicorn httpx python-dotenv
```

### 4. 同步案例库数据

首次部署需要同步案例数据和图片：

```bash
curl -X POST http://127.0.0.1:8768/api/gallery/sync
```

这会从 GitHub 拉取 cases.json 并下载所有案例图片（447 张，约 500MB）。

### 5. 启动后端 (systemd)

```bash
sudo cp prompt-portal.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable prompt-portal
sudo systemctl start prompt-portal
```

或直接运行：

```bash
./start.sh start
```

### 6. 配置 nginx

将 `nginx-portal.conf` 复制到 nginx 配置目录并加载：

```bash
# 复制配置文件
sudo cp nginx-portal.conf /etc/nginx/sites-available/prompt-portal
sudo ln -s /etc/nginx/sites-available/prompt-portal /etc/nginx/sites-enabled/

# 修改 root 路径为实际部署路径
sudo sed -i 's|/home/sahn/prompt|/your/deploy/path|g' /etc/nginx/sites-available/prompt-portal

# 测试并重载
sudo nginx -t
sudo nginx -s reload
```

### 7. 启动

```bash
./start.sh start
```

访问 `http://your-server:8769`。

### 8. 生成案例翻译（可选）

```bash
cd backend && python3 translate_prompts.py
```

## nginx 配置要点

- `proxy_read_timeout 300s` — AI 调用可能需要 60-120 秒
- `proxy_temp_path` — 指定 nginx 可写的临时目录
- `proxy_set_header Accept-Encoding ""` — 禁用 gzip 防止 Content-Length 不匹配

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/templates | 模板列表 |
| GET | /api/templates/{id} | 模板详情 |
| PUT | /api/templates/{id} | 更新模板 |
| DELETE | /api/templates/{id} | 删除模板 |
| POST | /api/templates/submit | 提交新模板 |
| GET | /api/categories | 分类列表 |
| POST | /api/match | AI 优化生成 |
| GET | /api/gallery | 案例库数据 |
| POST | /api/gallery/sync | 同步案例数据 |
| PUT | /api/gallery/cases/{id} | 更新案例 |
| DELETE | /api/gallery/cases/{id} | 删除案例 |
| POST | /api/gallery/cases | 新增案例 |
| GET | /api/gallery/translations | 案例翻译数据 |
| POST | /api/gallery/upload | 上传案例图片 |

## 环境变量

| 变量 | 说明 |
|------|------|
| MINIMAX_API_KEY | MiniMax API Key (AI 匹配必需) |
| IMAGE_API_URL | 图片生成服务地址 (可选) |

## 目录结构

```
prompt/
├── backend/
│   ├── main.py              # FastAPI 应用
│   ├── matching.py          # AI 匹配核心
│   ├── prompts_data.json    # 模板数据
│   ├── translate_prompts.py # 案例翻译脚本
│   └── data/
│       ├── gallery_data.json      # 案例元数据
│       ├── gallery_translations.json  # 案例翻译
│       └── gallery_images/        # 案例图片缓存
├── frontend/
│   └── index.html           # Vue 3 单文件 SPA
├── nginx-portal.conf        # nginx 配置
├── start.sh                 # 启动脚本
├── .env                     # 环境变量
└── README.md
```

## License

MIT
