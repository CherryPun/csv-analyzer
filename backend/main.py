import os
from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import analyzer
import pdf_report

app = FastAPI(title='CSV 数据分析平台', version='1.0.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.get('/favicon.ico')
async def favicon():
    return Response(status_code=204)

@app.get('/', response_class=HTMLResponse)
async def index():
    html_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    with open(html_path, 'r', encoding='utf-8') as f:
        return f.read()


@app.post('/api/upload')
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(400, '请上传 CSV 文件')
    
    content = await file.read()
    
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, '文件大小超过 10MB 限制')
    
    file_id = analyzer.save_csv(content, file.filename)
    overview = analyzer.get_overview(file_id)
    
    return {'file_id': file_id, 'file_name': file.filename, 'overview': overview}


@app.get('/api/overview')
async def get_overview(file_id: str = Query(...)):
    result = analyzer.get_overview(file_id)
    if result is None:
        raise HTTPException(404, '文件不存在或已过期')
    return result


@app.get('/api/analyze/numeric')
async def analyze_numeric(file_id: str = Query(...), col: str = Query(...)):
    result = analyzer.get_numeric_analysis(file_id, col)
    if result is None:
        raise HTTPException(404, '文件或列不存在')
    return result


@app.get('/api/analyze/categorical')
async def analyze_categorical(file_id: str = Query(...), col: str = Query(...), top_n: int = Query(20)):
    result = analyzer.get_categorical_analysis(file_id, col, top_n)
    if result is None:
        raise HTTPException(404, '文件或列不存在')
    return result


@app.get('/api/correlation')
async def get_correlation(file_id: str = Query(...)):
    result = analyzer.get_correlation(file_id)
    if result is None:
        raise HTTPException(404, '文件不存在')
    return result


@app.get('/api/missing')
async def get_missing(file_id: str = Query(...)):
    result = analyzer.get_missing_analysis(file_id)
    if result is None:
        raise HTTPException(404, '文件不存在')
    return result


@app.post('/api/query')
async def query_data(file_id: str = Query(...), sql: str = Query(...)):
    result = analyzer.query_data(file_id, sql)
    if result is None:
        raise HTTPException(404, '文件不存在')
    return result


@app.get('/api/scatter')
async def get_scatter(file_id: str = Query(...), col_x: str = Query(...), col_y: str = Query(...)):
    result = analyzer.get_scatter_data(file_id, col_x, col_y)
    if result is None:
        raise HTTPException(404, '文件不存在')
    return result


@app.get('/api/line')
async def get_line(file_id: str = Query(...), col_x: str = Query(...), col_y: str = Query(...)):
    result = analyzer.get_line_data(file_id, col_x, col_y)
    if result is None:
        raise HTTPException(404, '文件不存在')
    return result


@app.get('/api/export-pdf')
async def export_pdf(file_id: str = Query(...)):
    result = analyzer.get_overview(file_id)
    if result is None:
        raise HTTPException(404, '文件不存在或已过期')
    
    pdf_bytes = pdf_report.generate_report(file_id)
    if pdf_bytes is None:
        raise HTTPException(500, '生成 PDF 失败')
    
    return Response(
        content=pdf_bytes,
        media_type='application/pdf',
        headers={'Content-Disposition': 'attachment; filename="analysis_report.pdf"'}
    )


@app.post('/api/cleanup')
async def cleanup(file_id: str = Query(...)):
    analyzer.cleanup(file_id)
    return {'status': 'ok'}


if __name__ == '__main__':
    import uvicorn
    port = int(os.environ.get('PORT', 8000))
    host = os.environ.get('HOST', '127.0.0.1')
    uvicorn.run('main:app', host=host, port=port, reload=(host == '127.0.0.1'))
