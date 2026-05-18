# Prompt Portal

AI 图像提示词门户网站 | 基于 awesome-gpt-image-2 体系

## 功能特性

- **模板库首页** - 分类导航 + 卡片列表，支持筛选
- **模板编辑页** - 大文本编辑 + 一键复制
- **AI 智能匹配** - 输入需求，AI 自动匹配优化 Prompt
- **模板提交** - 提交新模板到审核队列

## 技术栈

- **后端**: FastAPI (Python) + uvicorn
- **前端**: Vue3 + CDN (单文件 SPA)
- **数据**: JSON 文件存储

## 快速启动

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 MINIMAX_API_KEY 和 IMAGE_API_URL
```

`.env` 内容示例：
```env
MINIMAX_API_KEY=your_api_key_here
IMAGE_API_URL=http://localhost:8766
```

### 2. 启动后端

```bash
# 方式一：启动脚本（推荐）
./start.sh start

# 方式二：直接运行
python3 -m backend.main

# 方式三：systemd 守护（需安装）
sudo cp prompt-portal.service /etc/systemd/system/
sudo systemctl enable prompt-portal
sudo systemctl start prompt-portal
```

其他命令：
```bash
./start.sh stop     # 停止
./start.sh restart  # 重启
./start.sh status   # 查看状态
```

### 3. 启动前端

直接用浏览器打开 `frontend/index.html`

或使用 nginx 托管：

```nginx
server {
    listen 80;
    root /path/to/prompt/frontend;
    index index.html;
    location /api/ {
        proxy_pass http://127.0.0.1:8768/api/;
    }
}
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/templates | 获取所有模板 |
| GET | /api/templates/{id} | 获取单个模板 |
| GET | /api/categories | 获取所有分类 |
| POST | /api/match | AI 智能匹配 |
| POST | /api/templates/submit | 提交新模板 |

## 页面路由

- `#home` - 模板库首页
- `#edit/{id}` - 模板编辑页
- `#match` - AI 匹配页
- `#submit` - 提交模板页

## 数据结构

```json
{
  "id": 1,
  "title": "模板标题",
  "prompt": "英文 Prompt 内容",
  "category": "分类名称",
  "styles": ["风格1", "风格2"],
  "scenes": ["场景1", "场景2"],
  "description": "中文说明"
}
```

## 分类

- Photography & Realism
- UI & Interfaces
- Posters & Typography
- Illustration & Art
- Architecture & Spaces
- Characters & People
- Products & E-commerce
- Infographics
- Other

## 环境变量

- `MINIMAX_API_KEY` - MiniMax API Key (用于 AI 匹配功能)

## License

MIT
