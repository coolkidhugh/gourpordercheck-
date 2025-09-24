import pandas as pd
import streamlit as st
import re
import unicodedata
from thefuzz import process, fuzz

st.set_page_config(page_title="智能可视化名单比对", layout="wide")

# --- Session State Initialization ---
SESSION_DEFAULTS = {
    'df1': None, 'df2': None, 'df1_name': "", 'df2_name': "",
    'ran_comparison': False, 'mismatched_df': pd.DataFrame(),
    'matched_df': pd.DataFrame(), 'in_file1_only': pd.DataFrame(),
    'in_file2_only': pd.DataFrame(), 'std_df1': pd.DataFrame(), 
    'std_df2': pd.DataFrame(), 'match_mode': '精确匹配'
}
for key, value in SESSION_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

# --- Helper Functions ---

def forensic_clean_text(text):
    """Applies the highest level of cleaning to any text string."""
    if not isinstance(text, str):
        return text
    try:
        cleaned_text = unicodedata.normalize('NFKC', text)
    except TypeError:
        return text
    cleaned_text = re.sub(r'[\u200B-\u200D\uFEFF\s\xa0]+', '', cleaned_text)
    return cleaned_text.strip()

def process_and_standardize(df, mapping, case_insensitive=False, room_type_equivalents=None):
    """Reads, cleans, and standardizes the dataframe based on user mapping."""
    if not all([mapping.get('name'), mapping.get('start_date'), mapping.get('end_date')]):
        return None
    
    standard_df = pd.DataFrame()
    standard_df['name_original'] = df[mapping['name']].astype(str)
    
    name_series = df[mapping['name']].astype(str).apply(forensic_clean_text)
    start_date_series = df[mapping['start_date']].astype(str).str.strip()
    end_date_series = df[mapping['end_date']].astype(str).str.strip()
    
    standard_df['start_date'] = pd.to_datetime(start_date_series, errors='coerce').dt.strftime('%Y-%m-%d')
    standard_df['end_date'] = pd.to_datetime(end_date_series, errors='coerce').dt.strftime('%Y-%m-%d')
    
    # Dynamically add optional columns only if they are selected
    if mapping.get('room_type') and mapping['room_type'] in df.columns:
        standard_df['room_type'] = df[mapping['room_type']].astype(str).apply(forensic_clean_text)
        if room_type_equivalents:
            reverse_map = {forensic_clean_text(v): forensic_clean_text(k) for k, values in room_type_equivalents.items() for v in values}
            standard_df['room_type'] = standard_df['room_type'].replace(reverse_map)

    if mapping.get('room_number') and mapping['room_number'] in df.columns:
        standard_df['room_number'] = df[mapping['room_number']].astype(str).apply(forensic_clean_text)
    
    name_series = name_series.str.split(r'[、,，/]')
    standard_df = standard_df.assign(name=name_series).explode('name')
    standard_df['name'] = standard_df['name'].apply(forensic_clean_text)
    
    if case_insensitive:
        standard_df['name'] = standard_df['name'].str.lower()
    
    standard_df.dropna(subset=['name', 'start_date', 'end_date'], inplace=True)
    standard_df = standard_df[standard_df['name'] != ''].reset_index(drop=True)
    
    return standard_df

def style_diffs(df, compare_cols):
    """Applies color highlighting to differing cells based on dynamic columns."""
    style_df = pd.DataFrame('', index=df.index, columns=df.columns)
    highlight_color = 'background-color: #FFC7CE'
    for col_base in compare_cols:
        col1, col2 = f'{col_base}_1', f'{col_base}_2'
        if col1 in df.columns and col2 in df.columns:
            notna1 = df[col1].notna()
            notna2 = df[col2].notna()
            is_diff = (df[col1] != df[col2]) & notna1 & notna2
            is_diff |= (notna1 ^ notna2)
            style_df.loc[is_diff, col1] = highlight_color
            style_df.loc[is_diff, col2] = highlight_color
    return df.style.apply(lambda s: style_df, axis=None)

# --- UI Layout ---

st.title("智能可视化名单比对工具 V17.0 🚀")
st.info("全新升级：实现动态按需比对！程序现在只对比您选择了的列，未选择的列将被自动忽略。")

st.header("第 1 步: 上传文件")
if st.button("🔄 清空并重置"):
    st.session_state.clear()
    st.rerun()

col1, col2 = st.columns(2)
# File uploaders
with col1:
    uploaded_file1 = st.file_uploader("上传名单文件 1", type=['csv', 'xlsx'])
    if uploaded_file1:
        st.session_state.df1_name = uploaded_file1.name
        try:
            st.session_state.df1 = pd.read_excel(uploaded_file1) if uploaded_file1.name.endswith('xlsx') else pd.read_csv(uploaded_file1)
        except Exception as e:
            st.error(f"读取文件1失败: {e}")
with col2:
    uploaded_file2 = st.file_uploader("上传名单文件 2", type=['csv', 'xlsx'])
    if uploaded_file2:
        st.session_state.df2_name = uploaded_file2.name
        try:
            st.session_state.df2 = pd.read_excel(uploaded_file2) if uploaded_file2.name.endswith('xlsx') else pd.read_csv(uploaded_file2)
        except Exception as e:
            st.error(f"读取文件2失败: {e}")

if st.session_state.df1 is not None and st.session_state.df2 is not None:
    st.success("文件上传成功！请继续下一步。")

    st.header("第 2 步: 选择用于比对的列")
    mapping = {'file1': {}, 'file2': {}}
    cols1, cols2 = st.columns(2)
    # Column mapping UI...
    
    st.header("第 3 步: 配置与执行")
    room_type_equivalents = {}
    # Use .get() for safety in case a mapping is None
    if mapping['file1'].get('room_type') and mapping['file2'].get('room_type'):
        with st.expander("⭐ 功能：统一不同名称的房型（例如：让'大床房'='King Room'）"):
            # Room type mapping logic...
            pass # The logic remains the same

    match_mode = st.radio("姓名匹配模式", ["精确匹配", "模糊匹配 (识别相似姓名)"], horizontal=True)
    similarity_threshold = 90
    if match_mode == "模糊匹配 (识别相似姓名)":
        similarity_threshold = st.slider("相似度阈值 (%)", 50, 100, 90)

    case_insensitive = st.checkbox("比对英文名时忽略大小写", True)
    
    if st.button("🚀 开始比对", type="primary"):
        if not all([mapping['file1'].get('name'), mapping['file1'].get('start_date'), mapping['file1'].get('end_date'),
                    mapping['file2'].get('name'), mapping['file2'].get('start_date'), mapping['file2'].get('end_date')]):
            st.error("请确保两边文件的“姓名”、“入住日期”、“离开日期”都已正确选择。")
        else:
            with st.spinner('正在执行动态比对...'):
                st.session_state.ran_comparison = True
                
                std_df1 = process_and_standardize(st.session_state.df1, mapping['file1'], case_insensitive, room_type_equivalents)
                st.session_state.std_df1 = std_df1
                std_df2 = process_and_standardize(st.session_state.df2, mapping['file2'], case_insensitive, room_type_equivalents)
                st.session_state.std_df2 = std_df2
                
                # --- NEW: Dynamically determine which columns to compare ---
                st.session_state.compare_cols = ['start_date', 'end_date']
                if mapping['file1'].get('room_type') and mapping['file2'].get('room_type'):
                    st.session_state.compare_cols.append('room_type')
                if mapping['file1'].get('room_number') and mapping['file2'].get('room_number'):
                    st.session_state.compare_cols.append('room_number')

                # Matching logic...
                
                def get_diff_details(row, compare_cols):
                    diffs = []
                    col_map = {"start_date": "入住日期", "end_date": "离开日期", "room_type": "房型", "room_number": "房号"}
                    for col in compare_cols:
                        is_diff = row.get(f'{col}_1') != row.get(f'{col}_2') and not (pd.isna(row.get(f'{col}_1')) and pd.isna(row.get(f'{col}_2')))
                        if is_diff:
                            diffs.append(col_map.get(col, col))
                    return ', '.join(diffs)
                
                # After merge, calculate differences
                # common_rows['差异摘要'] = common_rows.apply(get_diff_details, axis=1, compare_cols=st.session_state.compare_cols)
                # ...store results in session_state...

    if st.session_state.ran_comparison:
        st.header("比对结果")
        # Results display...
        
        # In the mismatched display part:
        # st.dataframe(style_diffs(display_row, st.session_state.compare_cols))

    st.divider()
    st.header("原始上传文件预览")
    # Data preview UI...
