import os
import tempfile
import base64
from fpdf import FPDF
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from analyzer import get_df, get_overview, get_missing_analysis, get_correlation

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

FONT_PATH = r'C:\Windows\Fonts\simhei.ttf'
FONT_NAME = 'SimHei'


class ReportPDF(FPDF):
    def __init__(self):
        super().__init__()
        if os.path.exists(FONT_PATH):
            self.add_font(FONT_NAME, '', FONT_PATH, uni=True)
            self.add_font(FONT_NAME, 'B', FONT_PATH, uni=True)
            self.add_font(FONT_NAME, 'I', FONT_PATH, uni=True)
        self._use_chinese = os.path.exists(FONT_PATH)

    def _font(self, style='', size=10):
        f = FONT_NAME if self._use_chinese else 'Helvetica'
        self.set_font(f, style, size)

    def header(self):
        self._font('B', 10)
        self.cell(0, 8, 'CSV 数据分析报告', align='C', new_x="LMARGIN", new_y="NEXT")
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', align='C')


def generate_report(file_id: str) -> bytes:
    df = get_df(file_id)
    if df is None:
        return None

    pdf = ReportPDF()
    pdf.alias_nb_pages()

    overview = get_overview(file_id)
    if overview is None:
        return None

    pdf.set_auto_page_break(auto=True, margin=20)

    _add_overview_section(pdf, overview)
    _add_columns_section(pdf, overview)
    _add_missing_section(pdf, file_id)

    numeric_cols = overview.get('numeric_cols', [])
    if len(numeric_cols) >= 2:
        _add_correlation_section(pdf, file_id)

    pdf.add_page()
    pdf._font('I', 9)
    pdf.cell(0, 10, '-- 报告结束 --', align='C')

    result = pdf.output()
    return result if isinstance(result, bytes) else bytes(result)


def _add_overview_section(pdf, overview):
    pdf.add_page()
    pdf._font('B', 14)
    pdf.cell(0, 10, '1. 数据概览', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    pdf._font('', 11)
    info = [
        f'行数: {overview["rows"]}',
        f'列数: {overview["cols"]}',
        f'缺失值: {overview["missing_cells"]} ({overview["missing_percent"]}%)',
        f'重复行: {overview["duplicated_rows"]}',
        f'内存占用: {overview["memory_usage"]}',
    ]
    for line in info:
        pdf.cell(0, 7, line, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)
    pdf._font('B', 11)
    pdf.cell(0, 8, '列列表:', new_x="LMARGIN", new_y="NEXT")
    pdf._font('', 9)

    for col in overview['columns']:
        pdf.cell(0, 6,
                 f'  {col["name"]}  |  类型: {col["type"]}  |  缺失: {col["missing"]}  |  唯一值: {col["unique"]}',
                 new_x="LMARGIN", new_y="NEXT")


def _add_columns_section(pdf, overview):
    pdf.add_page()
    pdf._font('B', 14)
    pdf.cell(0, 10, '2. 列统计', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    for col in overview['columns']:
        pdf._font('B', 11)
        pdf.cell(0, 8, f'{col["name"]} ({col["type"]})', new_x="LMARGIN", new_y="NEXT")
        pdf._font('', 9)

        stats = col.get('stats')
        if stats:
            label_map = {
                'mean': '均值', 'median': '中位数', 'std': '标准差',
                'min': '最小值', 'max': '最大值', 'q25': 'Q1', 'q75': 'Q3',
                'top': '最多', 'top_freq': '频次',
            }
            for key, val in stats.items():
                if val is not None:
                    label = label_map.get(key, key)
                    pdf.cell(0, 5, f'  {label}: {val}', new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)


def _add_missing_section(pdf, file_id):
    missing = get_missing_analysis(file_id)
    if not missing or not missing.get('missing_columns'):
        return

    pdf.add_page()
    pdf._font('B', 14)
    pdf.cell(0, 10, '3. 缺失值分析', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    pdf._font('', 11)
    pdf.cell(0, 7, f'总缺失值: {missing["total_missing"]} / {missing["total_cells"]} 个单元格',
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    pdf._font('B', 11)
    pdf.cell(0, 8, '各列缺失情况:', new_x="LMARGIN", new_y="NEXT")
    pdf._font('', 9)
    for m in missing['missing_columns']:
        pdf.cell(0, 6, f'  {m["col"]}: {m["count"]} ({m["percent"]}%)',
                 new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)
    pdf._font('B', 11)
    pdf.cell(0, 8, '处理建议:', new_x="LMARGIN", new_y="NEXT")
    pdf._font('', 9)
    for s in missing.get('suggestions', []):
        pdf.multi_cell(0, 5, f'  - {s}')
        pdf.ln(1)


def _add_correlation_section(pdf, file_id):
    corr = get_correlation(file_id)
    if not corr or 'heatmap' not in corr:
        return

    pdf.add_page()
    pdf._font('B', 14)
    pdf.cell(0, 10, '4. 相关性分析', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    img_data = base64.b64decode(corr['heatmap'])
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        f.write(img_data)
        temp_path = f.name

    try:
        pdf.image(temp_path, x=15, w=180)
    finally:
        os.unlink(temp_path)
