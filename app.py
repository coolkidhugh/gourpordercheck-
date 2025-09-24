import pandas as pd
import streamlit as st
import re
import unicodedata

st.set_page_config(page_title="交互式比对审核工具", layout="wide")

# --- Session State Initialization ---
SESSION_DEFAULTS = {
    'df1': None, 'df2': None,
    'ran_comparison': False, 
    'mismatched_df': pd.DataFrame(),
    'review_index': 0  # Index for the interactive review
}
for key, value in SESSION_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

# --- Helper Functions ---

def forensic_clean_text(text):
    if not isinstance(text, str): return text
    try:
        cleaned_text = unicodedata.normalize('NFKC', text)
    except (TypeError, ValueError):
        return text
    cleaned_text = re.sub(r'[\u200B-\u200D\uFEFF\s\xa0]+', '', cleaned_text)
    return cleaned_text.strip()

def process_and_standardize(df, mapping, case_insensitive=False):
    if not all(mapping.get(key) for key in ['name', 'start_date', 'end_date']):
        return pd.DataFrame(columns=['name', 'start_date', 'end_date'])

    standard_df = pd.DataFrame()
    
    # Process required columns and create a clean base
    for col_key, col_name in mapping.items():
        if col_name and col_name in df.columns:
            standard_df[col_key] = df[col_name].astype(str)

    # Clean and standardize data types
    standard_df['name'] = standard_df['name'].str.split(r'[、,，/]').explode().apply(forensic_clean_text)
    standard_df['start_date'] = pd.to_datetime(standard_df['start_date'].str.strip(), errors='coerce').dt.strftime('%Y-%m-%d')
    standard_df['end_date'] = pd.to_datetime(standard_df['end_date'].str.strip(), errors='coerce').dt.strftime('%Y-%m-%d')
    
    if 'room_type' in standard_df.columns:
        standard_df['room_type'] = standard_df['room_type'].apply(forensic_clean_text)
        
    if case_insensitive:
        standard_df['name'] = standard_df['name'].str.lower()
        
    standard_df = standard_df[standard_df['name'] != ''].dropna(subset=['name', 'start_date', 'end_date']).reset_index(drop=True)
    return standard_df

# --- UI Layout ---

st.title("交互式比对审核平台 V20.0 🏆 (最终版)")
st.info("终极形态：下方新增“逐条审核平台”，可对不一致项进行交互式、并排、高亮审核！")

st.header("第 1 步: 上传文件")
if 'df1' not in st.session_state: st.session_state.df1 = None
if 'df2' not in st.session_state: st.session_state.df2 = None
if 'df1_name' not in st.session_state: st.session_state.df1_name = ""
if 'df2_name' not in st.session_state: st.session_state.df2_name = ""

col1, col2 = st.columns(2)
with col1:
    uploaded_file1 = st.file_uploader("上传名单文件 1", type=['csv', 'xlsx'])
    if uploaded_file1:
        st.session_state.df1 = pd.read_excel(uploaded_file1) if uploaded_file1.name.endswith('xlsx') else pd.read_csv(uploaded_file1)
        st.session_state.df1_name = uploaded_file1.name
with col2:
    uploaded_file2 = st.file_uploader("上传名单文件 2", type=['csv', 'xlsx'])
    if uploaded_file2:
        st.session_state.df2 = pd.read_excel(uploaded_file2) if uploaded_file2.name.endswith('xlsx') else pd.read_csv(uploaded_file2)
        st.session_state.df2_name = uploaded_file2.name

if st.session_state.df1 is not None and st.session_state.df2 is not None:
    st.header("第 2 步: 选择要比对的列 (姓名/日期为必选)")
    mapping = {'file1': {}, 'file2': {}}
    cols_to_map = ['name', 'start_date', 'end_date', 'room_type']
    col_names_zh = ['姓名', '入住日期', '离开日期', '房型']

    cols1, cols2 = st.columns(2)
    with cols1:
        st.subheader(f"文件 1: {st.session_state.df1_name}")
        df1_cols = [None] + list(st.session_state.df1.columns)
        for key, name_zh in zip(cols_to_map, col_names_zh):
            mapping['file1'][key] = st.selectbox(f"{name_zh}", df1_cols, key=f'f1_{key}')
    with cols2:
        st.subheader(f"文件 2: {st.session_state.df2_name}")
        df2_cols = [None] + list(st.session_state.df2.columns)
        for key, name_zh in zip(cols_to_map, col_names_zh):
            mapping['file2'][key] = st.selectbox(f"{name_zh}", df2_cols, key=f'f2_{key}')
    
    if st.button("🚀 开始比对", type="primary"):
        if not all(mapping['file1'].get(key) for key in ['name', 'start_date', 'end_date']) or \
           not all(mapping['file2'].get(key) for key in ['name', 'start_date', 'end_date']):
            st.error("请确保两边文件的“姓名”、“入住日期”、“离开日期”都已正确选择。")
        else:
            with st.spinner('正在执行比对...'):
                st.session_state.ran_comparison = True
                st.session_state.review_index = 0

                std_df1 = process_and_standardize(st.session_state.df1, mapping['file1'], True)
                std_df2 = process_and_standardize(st.session_state.df2, mapping['file2'], True)
                
                merged_df = pd.merge(std_df1, std_df2, on='name', how='outer', suffixes=('_1', '_2'))
                
                compare_cols_keys = [key for key in ['start_date', 'end_date', 'room_type'] if mapping['file1'].get(key) and mapping['file2'].get(key)]
                
                def get_diff_summary(row):
                    diffs = []
                    for key in compare_cols_keys:
                        if row[f'{key}_1'] != row[f'{key}_2'] and not (pd.isna(row[f'{key}_1']) and pd.isna(row[f'{key}_2'])):
                            diffs.append(col_names_zh[cols_to_map.index(key)])
                    return ', '.join(diffs) if diffs else "一致"

                merged_df['比对摘要'] = merged_df.apply(get_diff_summary, axis=1)
                st.session_state.mismatched_df = merged_df[merged_df['比对摘要'] != "一致"].dropna(subset=[f'{c}_1' for c in compare_cols_keys] + [f'{c}_2' for c in compare_cols_keys], how='all').reset_index(drop=True)

    if st.session_state.ran_comparison:
        mismatched_count = len(st.session_state.mismatched_df)
        st.header("比对结果摘要")
        st.metric("发现不一致项数量", mismatched_count)

        if mismatched_count > 0:
            st.markdown("---")
            st.header("第 4 步: 逐条审核不一致项")

            # --- Interactive Review UI ---
            idx = st.session_state.review_index
            current_item = st.session_state.mismatched_df.iloc[idx]
            
            # Navigation controls
            st.subheader(f"正在审核第 {idx + 1} / {mismatched_count} 条")
            
            nav_cols = st.columns([1, 1, 5])
            if nav_cols[0].button('<< 上一条') and idx > 0:
                st.session_state.review_index -= 1
                st.rerun()
            if nav_cols[1].button('下一条 >>') and idx < mismatched_count - 1:
                st.session_state.review_index += 1
                st.rerun()

            # Side-by-side display
            display_cols = ['name'] + compare_cols_keys
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"#### 文件 1: {st.session_state.df1_name}")
                for key in display_cols:
                    col_name_zh = col_names_zh[cols_to_map.index(key)]
                    val = current_item.get(f'{key}_1', 'N/A')
                    is_diff = col_name_zh in current_item['比对摘要']
                    st.markdown(f"<div style='padding: 5px; border-radius: 5px; background-color: {'#FFC7CE' if is_diff else '#F0F2F6'}; margin-bottom: 5px;'>"
                                f"<strong>{col_name_zh}:</strong> {val}"
                                f"</div>", unsafe_allow_html=True)
            with col2:
                st.markdown(f"#### 文件 2: {st.session_state.df2_name}")
                for key in display_cols:
                    col_name_zh = col_names_zh[cols_to_map.index(key)]
                    val = current_item.get(f'{key}_2', 'N/A')
                    is_diff = col_name_zh in current_item['比对摘要']
                    st.markdown(f"<div style='padding: 5px; border-radius: 5px; background-color: {'#FFC7CE' if is_diff else '#F0F2F6'}; margin-bottom: 5px;'>"
                                f"<strong>{col_name_zh}:</strong> {val}"
                                f"</div>", unsafe_allow_html=True)
