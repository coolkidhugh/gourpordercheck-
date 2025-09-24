import pandas as pd
import streamlit as st
import re
import unicodedata

st.set_page_config(page_title="终极名单比对平台", layout="wide")

# --- Session State Initialization ---
# Initialize session state to remember values across reruns
SESSION_DEFAULTS = {
    'df1': None, 'df2': None, 'df1_name': "", 'df2_name': "",
    'ran_comparison': False, 'mismatched_df': pd.DataFrame(),
    'matched_df': pd.DataFrame(), 'in_file1_only': pd.DataFrame(),
    'in_file2_only': pd.DataFrame(), 'review_index': 0
}
for key, value in SESSION_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

# --- Helper Functions ---

def forensic_clean_text(text):
    """Applies the highest level of cleaning to any text string."""
    if not isinstance(text, str): return text
    try:
        cleaned_text = unicodedata.normalize('NFKC', text)
    except (TypeError, ValueError):
        return text
    cleaned_text = re.sub(r'[\u200B-\u200D\uFEFF\s\xa0]+', '', cleaned_text)
    return cleaned_text.strip()

def process_and_standardize(df, mapping, case_insensitive=False, room_type_equivalents=None):
    """
    Cleans and standardizes all selected columns. This is the core data processing engine.
    It handles multi-name cells, cleans text, and standardizes data types.
    """
    # Return empty if required columns are not selected
    if not all(mapping.get(key) for key in ['name', 'start_date', 'end_date']):
        return pd.DataFrame()

    # Create a new DataFrame to avoid modifying the original
    standard_df = pd.DataFrame()
    
    # Store original un-exploded name for reference in results
    standard_df['name_original'] = df[mapping['name']]
    
    # Process required and optional columns if they are mapped
    for col_key, col_name in mapping.items():
        if col_name and col_name in df.columns:
            standard_df[col_key] = df[col_name]

    # Standardize data types and clean text
    standard_df['start_date'] = pd.to_datetime(standard_df['start_date'].astype(str).str.strip(), errors='coerce').dt.strftime('%Y-%m-%d')
    standard_df['end_date'] = pd.to_datetime(standard_df['end_date'].astype(str).str.strip(), errors='coerce').dt.strftime('%Y-%m-%d')
    
    if 'room_type' in standard_df.columns:
        standard_df['room_type'] = standard_df['room_type'].astype(str).apply(forensic_clean_text)
        if room_type_equivalents:
            cleaned_equivalents = {forensic_clean_text(k): [forensic_clean_text(val) for val in v] for k, v in room_type_equivalents.items()}
            reverse_map = {val: key for key, values in cleaned_equivalents.items() for val in values}
            standard_df['room_type'] = standard_df['room_type'].replace(reverse_map)
    
    if 'price' in standard_df.columns:
        standard_df['price'] = pd.to_numeric(standard_df['price'].astype(str).str.strip(), errors='coerce')

    # BUG FIX: Handle multi-name cells robustly without causing index errors
    standard_df['name'] = standard_df['name'].astype(str).str.split(r'[、,，/]')
    standard_df = standard_df.explode('name')
    standard_df['name'] = standard_df['name'].apply(forensic_clean_text)
        
    if case_insensitive:
        standard_df['name'] = standard_df['name'].str.lower()
        
    # Final cleanup
    standard_df = standard_df[standard_df['name'] != ''].dropna(subset=['name', 'start_date', 'end_date']).reset_index(drop=True)
    return standard_df

# --- UI Layout ---

st.title("终极智能比对平台 V22.0 🏆")
st.info("集大成版：融合了交互式审核、完整报告和所有高级配置功能，稳定、全面、强大！")

st.header("第 1 步: 上传文件")
if st.button("🔄 清空并重置"):
    st.session_state.clear()
    st.rerun()

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
    cols_to_map = ['name', 'start_date', 'end_date', 'room_type', 'price']
    col_names_zh = ['姓名', '入住日期', '离开日期', '房型', '房价']

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

    st.header("第 3 步: 配置与执行")
    room_type_equivalents = {}
    if mapping['file1'].get('room_type') and mapping['file2'].get('room_type'):
        with st.expander("⭐ 功能：统一不同名称的房型 (例如：让'大床房'='King Room')"):
            unique_rooms1 = st.session_state.df1[mapping['file1']['room_type']].dropna().astype(str).unique()
            unique_rooms2 = list(st.session_state.df2[mapping['file2']['room_type']].dropna().astype(str).unique())
            for room1 in unique_rooms1:
                room_type_equivalents[room1] = st.multiselect(f"文件1的“{room1}”等同于:", unique_rooms2, key=f"map_{room1}")

    case_insensitive = st.checkbox("比对姓名时忽略大小写/全半角", True)
    
    if st.button("🚀 开始比对", type="primary"):
        if not all(mapping['file1'].get(key) for key in ['name', 'start_date', 'end_date']) or \
           not all(mapping['file2'].get(key) for key in ['name', 'start_date', 'end_date']):
            st.error("请确保两边文件的“姓名”、“入住日期”、“离开日期”都已正确选择。")
        else:
            with st.spinner('正在执行终极比对...'):
                st.session_state.ran_comparison = True
                st.session_state.review_index = 0
                
                st.session_state.df1.sort_values(by=mapping['file1']['name'], inplace=True, ignore_index=True)
                st.session_state.df2.sort_values(by=mapping['file2']['name'], inplace=True, ignore_index=True)

                std_df1 = process_and_standardize(st.session_state.df1, mapping['file1'], case_insensitive, room_type_equivalents)
                std_df2 = process_and_standardize(st.session_state.df2, mapping['file2'], case_insensitive)
                
                merged_df = pd.merge(std_df1, std_df2, on='name', how='outer', suffixes=('_1', '_2'))
                
                compare_cols_keys = [key for key in ['start_date', 'end_date', 'room_type', 'price'] if mapping['file1'].get(key) and mapping['file2'].get(key)]
                
                def get_diff_summary(row):
                    diffs = []
                    for key in compare_cols_keys:
                        col1, col2 = f'{key}_1', f'{key}_2'
                        if row.get(col1) != row.get(col2) and not (pd.isna(row.get(col1)) and pd.isna(row.get(col2))):
                            diffs.append(col_names_zh[cols_to_map.index(key)])
                    return ', '.join(diffs) if diffs else "一致"
                
                # Identify rows present in both files
                both_exist_mask = merged_df['start_date_1'].notna() & merged_df['start_date_2'].notna()
                common_rows = merged_df[both_exist_mask].copy()
                if not common_rows.empty:
                    common_rows['比对摘要'] = common_rows.apply(get_diff_summary, axis=1)
                    st.session_state.mismatched_df = common_rows[common_rows['比对摘要'] != "一致"].reset_index(drop=True)
                    st.session_state.matched_df = common_rows[common_rows['比对摘要'] == "一致"].reset_index(drop=True)
                else:
                    st.session_state.mismatched_df = pd.DataFrame()
                    st.session_state.matched_df = pd.DataFrame()

                # Identify rows only in one file
                only_in_1_mask = merged_df['start_date_1'].notna() & merged_df['start_date_2'].isna()
                st.session_state.in_file1_only = merged_df[only_in_1_mask].reset_index(drop=True)
                only_in_2_mask = merged_df['start_date_1'].isna() & merged_df['start_date_2'].notna()
                st.session_state.in_file2_only = merged_df[only_in_2_mask].reset_index(drop=True)

    if st.session_state.ran_comparison:
        mismatched_count = len(st.session_state.mismatched_df)
        matched_count = len(st.session_state.matched_df)
        only_1_count = len(st.session_state.in_file1_only)
        only_2_count = len(st.session_state.in_file2_only)

        st.header("比对结果摘要")
        stat_cols = st.columns(4)
        stat_cols[0].metric("⚠️ 信息不一致", mismatched_count)
        stat_cols[1].metric("✅ 信息完全一致", matched_count)
        stat_cols[2].metric(f"❓ 仅文件1有", only_1_count)
        stat_cols[3].metric(f"❓ 仅文件2有", only_2_count)

        if mismatched_count > 0:
            st.markdown("---")
            st.header("第 4 步: 逐条审核不一致项")

            idx = st.session_state.review_index
            current_item = st.session_state.mismatched_df.iloc[idx]
            
            st.subheader(f"正在审核第 {idx + 1} / {mismatched_count} 条")
            
            nav_cols = st.columns([1, 1, 5])
            if nav_cols[0].button('<< 上一条') and idx > 0:
                st.session_state.review_index -= 1
                st.rerun()
            if nav_cols[1].button('下一条 >>') and idx < mismatched_count - 1:
                st.session_state.review_index += 1
                st.rerun()

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"#### 文件 1: {st.session_state.df1_name}")
                st.markdown(f"**姓名:** {current_item.get('name_original_1', current_item.get('name'))}")
                for key in ['start_date', 'end_date', 'room_type', 'price']:
                    if mapping['file1'].get(key):
                        col_name_zh = col_names_zh[cols_to_map.index(key)]
                        val = current_item.get(f'{key}_1', 'N/A')
                        is_diff = col_name_zh in current_item['比对摘要']
                        st.markdown(f"<div style='padding: 5px; border-radius: 5px; background-color: {'#FFC7CE' if is_diff else '#F0F2F6'}; margin-bottom: 5px;'><strong>{col_name_zh}:</strong> {val}</div>", unsafe_allow_html=True)
            with col2:
                st.markdown(f"#### 文件 2: {st.session_state.df2_name}")
                st.markdown(f"**姓名:** {current_item.get('name_original_2', current_item.get('name'))}")
                for key in ['start_date', 'end_date', 'room_type', 'price']:
                    if mapping['file2'].get(key):
                        col_name_zh = col_names_zh[cols_to_map.index(key)]
                        val = current_item.get(f'{key}_2', 'N/A')
                        is_diff = col_name_zh in current_item['比对摘要']
                        st.markdown(f"<div style='padding: 5px; border-radius: 5px; background-color: {'#FFC7CE' if is_diff else '#F0F2F6'}; margin-bottom: 5px;'><strong>{col_name_zh}:</strong> {val}</div>", unsafe_allow_html=True)
        
        with st.expander(f"✅ 查看 {matched_count} 条信息完全一致的名单"):
            st.dataframe(st.session_state.matched_df[['name']].rename(columns={'name': '姓名'}))
        with st.expander(f"❓ 查看 {only_1_count} 条仅存在于文件1的名单"):
            st.dataframe(st.session_state.in_file1_only[['name']].rename(columns={'name': '姓名'}))
        with st.expander(f"❓ 查看 {only_2_count} 条仅存在于文件2的名单"):
            st.dataframe(st.session_state.in_file2_only[['name']].rename(columns={'name': '姓名'}))

    st.divider()
    st.header("原始数据预览 (点击比对后会按姓名排序)")
    c1, c2 = st.columns(2)
    with c1:
        st.caption(f"文件 1: {st.session_state.df1_name}")
        st.dataframe(st.session_state.df1)
    with c2:
        st.caption(f"文件 2: {st.session_state.df2_name}")
        st.dataframe(st.session_state.df2)
