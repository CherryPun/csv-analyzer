# CSV 数据分析平台

上传 CSV 文件，自动生成数据概览、统计分析、可视化图表，支持 SQL 查询和 PDF 报告导出。

## 功能

- 数据概览：行数、列数、缺失值、重复行、内存占用
- 列分析：数值列（直方图、箱线图、异常值检测）、类别列（饼图、柱状图）
- 相关性分析：热力图 + 数值矩阵
- 缺失值分析：可视化 + 处理建议
- SQL 查询：使用 DuckDB 引擎直接查询数据
- 交互图表：散点图 / 折线图
- PDF 导出：一键导出分析报告

## 快速开始

```bash
cd backend
pip install -r requirements.txt
python main.py
```

打开浏览器访问 `http://localhost:8000`

## 技术栈

- 后端：FastAPI + Pandas + DuckDB + Matplotlib
- 前端：HTML + ECharts
- 报告：fpdf2

## 部署

支持 Railway / Render 等平台，设置启动命令：

```bash
cd backend && python main.py
```
