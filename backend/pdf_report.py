import os
import tempfile
import base64
import io
from fpdf import FPDF
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from analyzer import get_df, get_overview, get_missing_analysis, get_correlation

plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

_FONT_CANDIDATES = [
    '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf',
    r'C:\Windows\Fonts\simhei.ttf',
    r'C:\Windows\Fonts\msyh.ttc',
]
FONT_PATH = next((f for f in _FONT_CANDIDATES if os.path.exists(f)), None)
FONT_NAME = os.path.splitext(os.path.basename(FONT_PATH))[0] if FONT_PATH else None


class ReportPDF(FPDF):
    def __init__(self):
        super().__init__('P', 'mm', 'A4')
        if FONT_PATH:
            self.add_font(FONT_NAME, '', FONT_PATH, uni=True)
            self.add_font(FONT_NAME, 'B', FONT_PATH, uni=True)
            self.add_font(FONT_NAME, 'I', FONT_PATH, uni=True)
        self._use_chinese = FONT_PATH is not None

    def _f(self, style='', size=10):
        f = FONT_NAME if self._use_chinese else 'Helvetica'
        self.set_font(f, style, size)

    def header(self):
        self._f('B', 12)
        self.cell(0, 8, 'CSV 数据分析报告', align='C', new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(100, 100, 100)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'第 {self.page_no()} 页 / 共 {{nb}} 页', align='C')

    def section_title(self, num, title):
        self.ln(4)
        self._f('B', 13)
        self.set_text_color(50, 50, 50)
        self.cell(0, 8, f'{num}. {title}', new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def kv_table(self, data, col_widths=None, header=True):
        if not data:
            return
        if col_widths is None:
            col_widths = [60, 60]
        with self.table(col_widths=col_widths, first_row_as_header=header) as table:
            for row in data:
                r = table.row()
                for cell in row:
                    r.cell(str(cell))

    def section_text(self, text):
        self._f('', 10)
        self.multi_cell(0, 6, text)
        self.ln(1)


def _fig_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=120, bbox_inches='tight', facecolor='white', edgecolor='none')
    buf.seek(0)
    img = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return img


def _safe(val, decimals=4):
    if val is None or (isinstance(val, float) and (val != val)):
        return '-'
    if isinstance(val, float):
        return round(val, decimals)
    return str(val)


def generate_report(file_id: str, include_correlation=True,
                    include_numeric_charts=True, include_categorical_charts=True) -> bytes:
    df = get_df(file_id)
    if df is None:
        return None

    pdf = ReportPDF()
    pdf.alias_nb_pages()
    overview = get_overview(file_id)
    if overview is None:
        return None

    pdf.set_auto_page_break(auto=True, margin=20)

    _render_overview(pdf, overview)
    _render_column_stats(pdf, overview)

    missing = get_missing_analysis(file_id)
    if missing and missing.get('missing_columns'):
        _render_missing(pdf, missing)

    if include_correlation:
        _render_correlation(pdf, file_id, overview)

    if include_numeric_charts:
        _render_numeric_charts(pdf, file_id, overview)

    if include_categorical_charts:
        _render_categorical_charts(pdf, file_id, overview)

    pdf.add_page()
    pdf._f('I', 9)
    pdf.cell(0, 10, '-- 报告结束 --', align='C')

    result = pdf.output()
    return result if isinstance(result, bytes) else bytes(result)


def _render_overview(pdf, overview):
    pdf.add_page()
    pdf.section_title('1', '数据概览')

    rows = [
        ['行数', str(overview['rows'])],
        ['列数', str(overview['cols'])],
        ['缺失值', f'{overview["missing_cells"]} ({overview["missing_percent"]}%)'],
        ['重复行', str(overview['duplicated_rows'])],
        ['内存占用', str(overview['memory_usage'])],
    ]
    pdf.kv_table(rows)

    pdf.ln(4)
    pdf._f('B', 10)
    pdf.cell(0, 7, '列清单', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)

    cols_data = [['列名', '类型', '缺失', '唯一值']]
    for col in overview['columns']:
        cols_data.append([col['name'], col['type'], str(col['missing']), str(col['unique'])])
    pdf.kv_table(cols_data, col_widths=[60, 30, 25, 25], header=True)


def _render_column_stats(pdf, overview):
    pdf.add_page()
    pdf.section_title('2', '列统计')

    for col in overview['columns']:
        pdf._f('B', 10)
        pdf.cell(0, 7, f'{col["name"]} ({col["type"]})', new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

        stats = col.get('stats')
        if stats:
            label_map = {
                'mean': '均值', 'median': '中位数', 'std': '标准差',
                'min': '最小值', 'max': '最大值', 'q25': 'Q1', 'q75': 'Q3',
                'top': '最多', 'top_freq': '频次',
            }
            data = []
            for key, val in stats.items():
                if val is not None:
                    label = label_map.get(key, key)
                    data.append([label, str(_safe(val))])
            if data:
                pdf.kv_table(data, col_widths=[40, 100])
        pdf.ln(2)


def _render_missing(pdf, missing):
    pdf.add_page()
    pdf.section_title('3', '缺失值分析')

    pdf.section_text(f'总缺失值: {missing["total_missing"]} / {missing["total_cells"]} 个单元格')
    pdf.ln(2)

    data = [['列名', '缺失数量', '缺失率']]
    for m in missing['missing_columns']:
        data.append([m['col'], str(m['count']), f'{m["percent"]}%'])
    pdf.kv_table(data, col_widths=[60, 40, 40], header=True)

    pdf.ln(4)
    pdf._f('B', 10)
    pdf.cell(0, 7, '处理建议:', new_x="LMARGIN", new_y="NEXT")
    pdf._f('', 9)
    for s in missing.get('suggestions', []):
        pdf.multi_cell(0, 5, f'  - {s}')
        pdf.ln(1)


def _render_correlation(pdf, file_id, overview):
    corr = get_correlation(file_id)
    if not corr or 'heatmap' not in corr:
        return

    pdf.add_page()
    pdf.section_title('4', '相关性分析')

    img_data = base64.b64decode(corr['heatmap'])
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        f.write(img_data)
        temp_path = f.name
    try:
        pdf.image(temp_path, x=15, w=180)
    finally:
        os.unlink(temp_path)

    if corr.get('matrix'):
        pdf.ln(4)
        matrix = corr['matrix']
        cols = corr['columns']
        header = [''] + [c[:8] for c in cols]
        data = [header]
        for i, row in enumerate(matrix):
            data.append([cols[i][:8]] + [str(_safe(v, 3)) for v in row])
        pdf.kv_table(data, header=True)


def _render_numeric_charts(pdf, file_id, overview):
    numeric_cols = overview.get('numeric_cols', [])
    if not numeric_cols:
        return

    from analyzer import get_numeric_analysis

    pdf.add_page()
    pdf.section_title('5', '数值列分布图')

    for col in numeric_cols[:6]:
        analysis = get_numeric_analysis(file_id, col)
        if not analysis or 'histogram' not in analysis:
            continue

        s = analysis['stats']
        pdf._f('B', 10)
        pdf.cell(0, 7, f'{col} (均值={_safe(s["mean"], 2)}, 中位数={_safe(s["median"], 2)})',
                 new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 3))
        fig.patch.set_facecolor('white')

        hist = analysis['histogram']
        centers = [(hist['bins'][i] + hist['bins'][i + 1]) / 2 for i in range(len(hist['bins']) - 1)]
        ax1.bar([f'{hist['bins'][i]:.1f}-{hist['bins'][i+1]:.1f}' for i in range(len(hist['bins'])-1)],
                hist['counts'], color='#58a6ff', edgecolor='white', width=0.9)
        ax1.set_title('直方图', fontsize=10)
        ax1.tick_params(axis='x', rotation=45, labelsize=6)
        ax1.set_ylabel('频数', fontsize=8)
        ax1.yaxis.set_major_locator(plt.MaxNLocator(integer=True))

        outliers = analysis.get('outliers', {})
        st = analysis['stats']
        ax2.barh(['最小值', 'Q1', '中位数', '均值', 'Q3', '最大值'],
                 [st['min'], st['q25'], st['median'], st['mean'], st['q75'], st['max']],
                 color=['#f85149', '#d29922', '#58a6ff', '#3fb950', '#d29922', '#f85149'])
        ax2.set_title(f'关键统计 (异常值: {outliers.get("count", 0)})', fontsize=10)
        ax2.tick_params(labelsize=7)

        fig.tight_layout()
        img = _fig_to_base64(fig)
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            f.write(base64.b64decode(img))
            temp_path = f.name
        try:
            pdf.image(temp_path, x=15, w=180)
        finally:
            os.unlink(temp_path)
        pdf.ln(2)


def _render_categorical_charts(pdf, file_id, overview):
    cat_cols = overview.get('categorical_cols', [])
    if not cat_cols:
        return

    from analyzer import get_categorical_analysis

    pdf.add_page()
    pdf.section_title('6', '类别列分布图')

    for col in cat_cols[:4]:
        analysis = get_categorical_analysis(file_id, col, top_n=10)
        if not analysis:
            continue

        pdf._f('B', 10)
        pdf.cell(0, 7, f'{col} (共 {analysis["unique_count"]} 个类别)', new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

        fig, ax = plt.subplots(figsize=(8, 3.5))
        fig.patch.set_facecolor('white')

        items = analysis['freq'][:10]
        labels = [d['label'][:12] + '...' if len(d['label']) > 12 else d['label'] for d in items]
        values = [d['count'] for d in items]
        colors = plt.cm.Set2(np.linspace(0, 1, len(items)))
        bars = ax.barh(range(len(items)), values, color=colors, edgecolor='white')
        ax.set_yticks(range(len(items)))
        ax.set_yticklabels(labels, fontsize=7)
        ax.set_xlabel('频数', fontsize=8)
        ax.set_title(f'{col} Top 10', fontsize=10)
        for bar, val in zip(bars, values):
            ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                    str(val), va='center', fontsize=7)
        ax.margins(x=0.15)
        fig.tight_layout()

        img = _fig_to_base64(fig)
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            f.write(base64.b64decode(img))
            temp_path = f.name
        try:
            pdf.image(temp_path, x=15, w=180)
        finally:
            os.unlink(temp_path)
        pdf.ln(2)
