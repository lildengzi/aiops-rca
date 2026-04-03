# AIOps 根因分析系统 - 快速启动

## 环境要求

- Python 3.8+
- Windows 或 Linux/Mac

## 快速启动

### Windows 用户

双击运行 `run.bat` 即可启动

或手动运行：
```bash
pip install -r requirements.txt
python demo_offline.py
```

### Linux/Mac 用户

```bash
chmod +x run.sh
./run.sh
```

## 使用说明

1. 系统启动后会显示多智能体团队信息
2. 选择故障场景进行根因分析（CPU/延迟/磁盘/网络/内存）
3. 分析完成后自动生成报告保存到 `reports/` 目录

## 故障场景

| 编号 | 类型 | 说明 |
|------|------|------|
| 1 | CPU | CPU 资源耗尽故障 |
| 2 | Delay | 服务延迟异常 |
| 3 | Disk | 磁盘 I/O 异常 |
| 4 | Loss | 网络丢包故障 |
| 5 | Memory | 内存泄漏/OOM |

## 配置说明

如需使用在线 LLM API，请编辑 `.env` 文件：

```env
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=your_base_url
LLM_MODEL=your_model
```

然后运行 `python main.py --interactive`