# WHOOP Health Dashboard

React + TypeScript 前端、FastAPI 后端和 SQLite 存储组成的个人 WHOOP 健康分析看板。

提供恢复与睡眠趋势、运动活动日历、跨指标长期对照、训练计划核对、心率区间比例、体重记录、事件标注和报表导出。

## 仓库范围

本仓库仅包含前后端源码、依赖清单和通用前端构建文件。不包含真实健康数据、数据库、报表、WHOOP 授权令牌、环境变量文件、服务器部署配置、SSH 密钥、镜像或本机路径。

`whoop.py`、`weekly.py`、`report.py` 是后端使用的同步、归档与报表模块，保留在根目录。

## 本地开发

使用 Python 3.12 和 Node.js 22。

在根目录安装后端依赖并启动：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

在另一个终端启动前端：

```bash
cd frontend
npm ci
npm run dev
```

前端开发服务器将 `/api` 和 `/callback` 转发到本机后端。也可以在 `frontend` 中执行 `npm run build`，随后从后端的 `http://127.0.0.1:8000` 查看构建后的页面。

初次启动没有个人数据，这是预期行为。WHOOP 同步需要在本机自行设置 `WHOOP_CLIENT_ID`、`WHOOP_CLIENT_SECRET` 和 `WHOOP_REDIRECT_URI`，通过环境变量或不纳入版本管理的 `.env` 提供。密钥、授权令牌、数据库和运行结果都不能提交到仓库。

## 安全说明

默认开发模式仅用于本机回环地址。不要直接将无认证开发服务暴露到公网。

后端保留服务器认证与 Tailscale 专用访问模式的实现，但实际网络绑定、凭据及访问策略应在部署环境单独管理，本仓库不提供个人服务器配置。

健康分析用于个人趋势观察，不构成医疗诊断；指标间的相关性不代表因果。
