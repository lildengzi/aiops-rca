# 部署脚本说明

## 目录结构

```
bin/
├── run.bat              # 一键启动 Web 界面（Windows）
├── run_demo.bat         # 离线演示模式（无需 API Key）
├── Dockerfile           # Docker 镜像构建文件
├── docker-compose.yml   # Docker Compose 编排文件
└── README.md            # 本说明文件
```

## 使用方法

### 1. 快速启动（推荐）
双击运行 `run.bat` 或在命令行执行：
```batch
bin\run.bat
```

功能：
- 自动检查 Python 环境
- 自动安装缺失依赖
- 首次运行自动构建 RAG 知识库
- 自动启动 Streamlit Web 界面
- 浏览器自动打开 http://localhost:8501

### 2. 离线演示（无需 API Key）
双击运行 `run_demo.bat` 或执行：
```batch
bin\run_demo.bat
```

- 无需配置 LLM API Key
- 使用预加载的数据集运行完整分析流程
- 适合快速体验系统功能

### 3. Docker 部署

#### 方式一：Docker Compose（推荐）
```bash
cd bin
docker-compose up -d
```

访问: http://localhost:8501

#### 方式二：直接构建镜像
```bash
docker build -f bin/Dockerfile -t aiops-rca .
docker run -p 8501:8501 aiops-rca
```

## 环境变量配置

在项目根目录创建 `.env` 文件配置：

```env
# LLM 配置
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus
LLM_TEMPERATURE=0.1

# 系统配置
MAX_ITERATIONS=5
CONVERGENCE_THRESHOLD=0.8
```

## 性能优化

Docker 部署默认资源限制：
- CPU: 2核 (上限) / 0.5核 (预留)
- 内存: 4GB (上限) / 1GB (预留)

可根据实际服务器配置修改 `docker-compose.yml` 中的资源限制。
