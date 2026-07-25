import os
import io
import base64
import uuid
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import duckdb
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.facecolor'] = '#161b22'
plt.rcParams['axes.facecolor'] = '#161b22'
plt.rcParams['axes.edgecolor'] = '#30363d'
plt.rcParams['axes.labelcolor'] = '#c9d1d9'
plt.rcParams['xtick.color'] = '#8b949e'
plt.rcParams['ytick.color'] = '#8b949e'
plt.rcParams['text.color'] = '#c9d1d9'
plt.rcParams['legend.facecolor'] = '#1c2128'
plt.rcParams['legend.edgecolor'] = '#30363d'

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

dataframes = {}


def _fig_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    img = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return img


def save_csv(file_content: bytes, file_name: str) -> str:
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file_name)[1] or '.csv'
    save_path = os.path.join(UPLOAD_DIR, f'{file_id}{ext}')
    with open(save_path, 'wb') as f:
        f.write(file_content)
    
    encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin-1']
    df = None
    for enc in encodings:
        try:
            df = pd.read_csv(save_path, encoding=enc)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    if df is None:
        df = pd.read_csv(save_path, encoding='latin-1')
    
    dataframes[file_id] = df
    return file_id


def get_df(file_id: str) -> pd.DataFrame:
    return dataframes.get(file_id)


def get_overview(file_id: str) -> dict:
    df = get_df(file_id)
    if df is None:
        return None
    
    overview = {
        'rows': len(df),
        'cols': len(df.columns),
        'columns': [],
        'missing_cells': int(df.isnull().sum().sum()),
        'missing_percent': round(float(df.isnull().sum().sum() / (len(df) * len(df.columns)) * 100), 2),
        'duplicated_rows': int(df.duplicated().sum()),
        'memory_usage': f'{df.memory_usage(deep=True).sum() / 1024:.1f} KB',
    }
    
    for col in df.columns:
        col_info = {
            'name': col,
            'dtype': str(df[col].dtype),
            'missing': int(df[col].isnull().sum()),
            'missing_pct': round(float(df[col].isnull().sum() / len(df) * 100), 2),
            'unique': int(df[col].nunique()),
        }
        
        safe_round = lambda v: None if (v is None or (isinstance(v, float) and v != v)) else round(float(v), 4)
        if pd.api.types.is_numeric_dtype(df[col]):
            col_info['type'] = '数值'
            col_info['stats'] = {
                'mean': safe_round(df[col].mean()),
                'median': safe_round(df[col].median()),
                'std': safe_round(df[col].std()),
                'min': safe_round(df[col].min()),
                'max': safe_round(df[col].max()),
                'q25': safe_round(df[col].quantile(0.25)),
                'q75': safe_round(df[col].quantile(0.75)),
            }
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            col_info['type'] = '日期'
            col_info['stats'] = {
                'min': str(df[col].min()) if not df[col].isnull().all() else None,
                'max': str(df[col].max()) if not df[col].isnull().all() else None,
            }
        else:
            col_info['type'] = '类别'
            top_value = df[col].mode().iloc[0] if not df[col].isnull().all() else None
            col_info['stats'] = {
                'top': str(top_value) if top_value is not None else None,
                'top_freq': int(df[col].value_counts().iloc[0]) if not df[col].isnull().all() else 0,
            }
        
        overview['columns'].append(col_info)
    
    numeric_cols = [c['name'] for c in overview['columns'] if c['type'] == '数值']
    overview['numeric_cols'] = numeric_cols
    categorical_cols = [c['name'] for c in overview['columns'] if c['type'] == '类别']
    overview['categorical_cols'] = categorical_cols
    
    return overview


def get_numeric_analysis(file_id: str, col: str) -> dict:
    df = get_df(file_id)
    if df is None or col not in df.columns:
        return None
    
    series = df[col].dropna()
    if len(series) == 0:
        return {'error': '此列无有效数据'}
    
    safe = lambda v: None if (v is None or (isinstance(v, float) and v != v)) else round(float(v), 4)
    result = {
        'col': col,
        'histogram': _get_histogram(series),
        'boxplot': _get_boxplot_base64(series, col),
        'stats': {
            'count': int(len(series)),
            'mean': safe(series.mean()),
            'median': safe(series.median()),
            'std': safe(series.std()),
            'min': safe(series.min()),
            'max': safe(series.max()),
            'q25': safe(series.quantile(0.25)),
            'q75': safe(series.quantile(0.75)),
            'skew': safe(series.skew()),
            'kurtosis': safe(series.kurtosis()),
        },
        'outliers': _get_outlier_info(series, safe),
    }
    return result


def _get_histogram(series):
    counts, edges = np.histogram(series, bins='auto')
    return {
        'bins': edges.tolist(),
        'counts': counts.tolist(),
    }


def _get_boxplot_base64(series, col):
    fig, ax = plt.subplots(figsize=(6, 3))
    bp = ax.boxplot(series, vert=False, patch_artist=True,
                    boxprops=dict(facecolor='#58a6ff', alpha=0.5),
                    whiskerprops=dict(color='#8b949e'),
                    capprops=dict(color='#8b949e'),
                    medianprops=dict(color='#f0883e', linewidth=2),
                    flierprops=dict(marker='o', markerfacecolor='#f85149', markersize=6, markeredgecolor='#f85149'))
    ax.set_title(f'{col} - 箱线图', color='#c9d1d9')
    ax.set_xlabel(col, color='#c9d1d9')
    ax.tick_params(colors='#8b949e')
    for spine in ax.spines.values():
        spine.set_color('#30363d')
    fig.tight_layout()
    return _fig_to_base64(fig)


def _get_outlier_info(series, safe=None):
    if safe is None:
        safe = lambda v: None if (v is None or (isinstance(v, float) and v != v)) else round(float(v), 4)
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    outliers = series[(series < lower) | (series > upper)]
    return {
        'count': int(len(outliers)),
        'percent': round(float(len(outliers) / len(series) * 100), 2) if len(series) > 0 else 0,
        'lower_bound': safe(lower),
        'upper_bound': safe(upper),
    }


def get_categorical_analysis(file_id: str, col: str, top_n: int = 20) -> dict:
    df = get_df(file_id)
    if df is None or col not in df.columns:
        return None
    
    series = df[col].dropna()
    vc = series.value_counts()
    
    if len(vc) > top_n:
        top = vc.head(top_n)
        other_count = vc.iloc[top_n:].sum()
        labels = top.index.tolist() + ['其他']
        values = top.values.tolist() + [int(other_count)]
    else:
        labels = vc.index.tolist()
        values = vc.values.tolist()
    
    labels_str = [str(x) for x in labels]
    
    return {
        'col': col,
        'freq': [{'label': labels_str[i], 'count': values[i]} for i in range(len(labels_str))],
        'unique_count': int(series.nunique()),
        'total': int(len(series)),
    }


def get_correlation(file_id: str) -> dict:
    df = get_df(file_id)
    if df is None:
        return None
    
    numeric_df = df.select_dtypes(include=[np.number])
    if numeric_df.shape[1] < 2:
        return {'error': '至少需要2个数值列才能计算相关性'}
    
    corr = numeric_df.corr()
    corr_img = _get_corr_heatmap_base64(corr)
    
    matrix = []
    for row in corr.values:
        matrix.append([None if (v is None or (isinstance(v, float) and (v != v))) else round(float(v), 4) for v in row])
    
    return {
        'columns': corr.columns.tolist(),
        'matrix': matrix,
        'heatmap': corr_img,
    }


def _get_corr_heatmap_base64(corr_matrix):
    fig, ax = plt.subplots(figsize=(max(6, len(corr_matrix.columns) * 0.6),
                                    max(5, len(corr_matrix.columns) * 0.5)))
    im = ax.imshow(corr_matrix.values, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')
    
    ax.set_xticks(range(len(corr_matrix.columns)))
    ax.set_yticks(range(len(corr_matrix.columns)))
    ax.set_xticklabels(corr_matrix.columns, rotation=45, ha='right', fontsize=9, color='#c9d1d9')
    ax.set_yticklabels(corr_matrix.columns, fontsize=9, color='#c9d1d9')
    ax.tick_params(colors='#8b949e')
    for spine in ax.spines.values():
        spine.set_color('#30363d')
    
    for i in range(len(corr_matrix.columns)):
        for j in range(len(corr_matrix.columns)):
            val = corr_matrix.values[i, j]
            color = 'white' if abs(val) > 0.5 else '#c9d1d9'
            ax.text(j, i, f'{val:.2f}', ha='center', va='center', fontsize=8, color=color)
    
    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.ax.yaxis.set_tick_params(color='#8b949e')
    plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color='#8b949e')
    fig.tight_layout()
    return _fig_to_base64(fig)


def get_missing_analysis(file_id: str) -> dict:
    df = get_df(file_id)
    if df is None:
        return None
    
    missing = []
    for col in df.columns:
        count = int(df[col].isnull().sum())
        if count > 0:
            missing.append({
                'col': col,
                'count': count,
                'percent': round(count / len(df) * 100, 2),
            })
    
    missing.sort(key=lambda x: x['count'], reverse=True)
    
    suggestions = []
    for m in missing:
        if m['percent'] > 50:
            suggestions.append(f"{m['col']}：缺失 {m['percent']}% > 50%，建议删除此列")
        elif m['percent'] > 0:
            col_type = '数值' if pd.api.types.is_numeric_dtype(df[m['col']]) else '类别'
            if col_type == '数值':
                suggestions.append(f"{m['col']}：缺失 {m['percent']}%，建议填充均值/中位数")
            else:
                suggestions.append(f"{m['col']}：缺失 {m['percent']}%，建议填充众数或标记为'未知'")
    
    return {
        'total_missing': int(df.isnull().sum().sum()),
        'total_cells': int(len(df) * len(df.columns)),
        'missing_columns': missing,
        'suggestions': suggestions,
    }


def query_data(file_id: str, sql: str) -> dict:
    df = get_df(file_id)
    if df is None:
        return None
    
    try:
        rel = duckdb.sql(sql)
        result = rel.fetchdf()
        return {
            'success': True,
            'columns': result.columns.tolist(),
            'rows': result.values.tolist(),
            'total_rows': len(result),
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
        }


def _to_numeric(series):
    return pd.to_numeric(series, errors='coerce')


def get_scatter_data(file_id: str, col_x: str, col_y: str) -> dict:
    df = get_df(file_id)
    if df is None:
        return None
    
    if col_x not in df.columns or col_y not in df.columns:
        return {'error': '列名不存在'}
    
    sub = df[[col_x, col_y]].copy()
    sub[col_x] = _to_numeric(sub[col_x])
    sub[col_y] = _to_numeric(sub[col_y])
    sub = sub.dropna()
    
    if len(sub) == 0:
        return {'error': '两列数据无法转换为数值，无法生成图表'}
    
    return {
        'col_x': col_x,
        'col_y': col_y,
        'data': [{'x': round(float(r[0]), 6), 'y': round(float(r[1]), 6)} for r in sub.values],
        'count': len(sub),
    }


def get_line_data(file_id: str, col_x: str, col_y: str) -> dict:
    df = get_df(file_id)
    if df is None:
        return None
    
    if col_x not in df.columns or col_y not in df.columns:
        return {'error': '列名不存在'}
    
    sub = df[[col_x, col_y]].copy()
    sub[col_y] = _to_numeric(sub[col_y])
    sub = sub.dropna(subset=[col_y]).sort_values(col_x)
    
    if len(sub) == 0:
        return {'error': 'Y 列数据无法转换为数值，无法生成图表'}
    
    return {
        'col_x': col_x,
        'col_y': col_y,
        'data': [{'x': str(r[0]), 'y': round(float(r[1]), 6)} for r in sub.values],
        'count': len(sub),
    }


def cleanup(file_id: str):
    if file_id in dataframes:
        del dataframes[file_id]
    for f in os.listdir(UPLOAD_DIR):
        if f.startswith(file_id):
            os.remove(os.path.join(UPLOAD_DIR, f))
