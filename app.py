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
        return text # Return original if not a string
    # Remove a wide range of invisible characters and control characters, including non-breaking spaces.
    cleaned_text = re.sub(r'[\u200B-\u200D\uFEFF\s\xa0]+', '', cleaned_text)
    return cleaned_text.strip()

def process_and_standardize(df, mapping, case_insensitive=False):
    """Reads, cleans, and standardizes the dataframe with aggressive cleaning."""
    if not all([mapping['name'], mapping['start_date'], mapping['end_date']]):
        return None
    
    standard_df = pd.DataFrame()
    standard_df['name_original'] = df[mapping['name']].astype(str)
    
    name_series = df[mapping['name']].astype(str).apply(forensic_clean_text)
    start_date_series = df[mapping['start_date']].astype(str).str.strip()
    end_date_series = df[mapping['end_date']].astype(str).str.strip()
    
    standard_df['start_date'] = pd.to_datetime(start_date_series, errors='coerce').dt.strftime('%Y-%m-%d')
    standard_df['end_date'] = pd.to_datetime(end_date_series, errors='coerce').dt.strftime('%Y-%m-%d')
    
    if mapping.get('room_type') and mapping['room_type'] in df.columns:
        standard_df['room_type'] = df[mapping['room_type']].astype(str).apply(forensic_clean_text)
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

def diagnose_difference(val1, val2):
    """Generates a detailed diagnostic report for two values."""
    def get_details(val):
        val_str = str(val)
        val_len = len(val_str)
        val_bytes = val_str.encode('utf-8', 'surrogatepass')
        return f"**文本内容**: `{val_str}`\n\n**字符长度**: `{val_len}`\n\n**字节构成**: `{val_bytes}`"

    report = f"--- **文件1中的值** ---\n\n{get_details(val1)}\n\n--- **文件2中的值** ---\n\n{get_details(val2)}\n"
    return report

def style_diffs(df):
    """Applies color highlighting to differing cells."""
    style_df = pd.DataFrame('', index=df.index, columns=df.columns)
    highlight_color = 'background-color: #FFC7CE'
    compare_cols = ['start_date', 'end_date', 'room_type', 'room_number']
    for col_base in compare_cols:
        col1, col2 = f'{col_base}_1', f'{col_base}_2'
        if col1 in df.columns and col2 in df.columns:
            # Create boolean Series for non-NA values
            notna1 = df[col1].notna()
            notna2 = df[col2].notna()
            # Compare where both are not NA
            is_diff = (df[col1] != df[col2]) & notna1 & notna2
            # Also consider one is NA and the other is not as a difference
            is_diff |= (notna1 ^ notna2)
            style_df.loc[is_diff, col1] = highlight_color
            style_df.loc[is_diff, col2] = highlight_color
    return df.style.apply(lambda s: style_df, axis=None)

# --- UI Layout ---

st.title("智能可视化名单比对工具 V16.0 🕵️")
st.info("终极武器：新增“深度诊断报告”！对于不一致项，可展开查看法证级分析，揭示所有隐藏差异。")

st.header("第 1 步: 上传文件")
if st.button("🔄 清空并重置"):
    st.session_state.clear()
    st.rerun()

col1, col2 = st.columns(2)
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
    with cols1:
        st.subheader(f"文件 1: {st.session_state.df1_name}")
        df1_cols = [None] + list(st.session_state.df1.columns)
        mapping['file1']['name'] = st.selectbox("姓名 (必选)", df1_cols, key='f1_name')
        mapping['file1']['start_date'] = st.selectbox("入住日期 (必选)", df1_cols, key='f1_start')
        mapping['file1']['end_date'] = st.selectbox("离开日期 (必选)", df1_cols, key='f1_end')
        mapping['file1']['room_type'] = st.selectbox("房型 (可选)", df1_cols, key='f1_room')
        mapping['file1']['room_number'] = st.selectbox("房号 (可选)", df1_cols, key='f1_room_num')
    with cols2:
        st.subheader(f"文件 2: {st.session_state.df2_name}")
        df2_cols = [None] + list(st.session_state.df2.columns)
        mapping['file2']['name'] = st.selectbox("姓名 (必选)", df2_cols, key='f2_name')
        mapping['file2']['start_date'] = st.selectbox("入住日期 (必选)", df2_cols, key='f2_start')
        mapping['file2']['end_date'] = st.selectbox("离开日期 (必选)", df2_cols, key='f2_end')
        mapping['file2']['room_type'] = st.selectbox("房型 (可选)", df2_cols, key='f2_room')
        mapping['file2']['room_number'] = st.selectbox("房号 (可选)", df2_cols, key='f2_room_num')

    st.header("第 3 步: 配置与执行")
    
    st.session_state.match_mode = st.radio("姓名匹配模式", ["精确匹配", "模糊匹配 (识别相似姓名)"], horizontal=True)
    similarity_threshold = 90
    if st.session_state.match_mode == "模糊匹配 (识别相似姓名)":
        similarity_threshold = st.slider("相似度阈值 (%)", 50, 100, 90)

    case_insensitive = st.checkbox("比对英文名时忽略大小写", True)
    
    if st.button("🚀 开始比对", type="primary"):
        if not all([mapping['file1']['name'], mapping['file1']['start_date'], mapping['file1']['end_date'],
                    mapping['file2']['name'], mapping['file2']['start_date'], mapping['file2']['end_date']]):
            st.error("请确保两边文件的“姓名”、“入住日期”、“离开日期”都已正确选择。")
        else:
            with st.spinner('正在执行深度比对...'):
                st.session_state.ran_comparison = True
                st.session_state.df1.sort_values(by=mapping['file1']['name'], inplace=True, ignore_index=True)
                st.session_state.df2.sort_values(by=mapping['file2']['name'], inplace=True, ignore_index=True)

                st.session_state.std_df1 = process_and_standardize(st.session_state.df1, mapping['file1'], case_insensitive)
                st.session_state.std_df2 = process_and_standardize(st.session_state.df2, mapping['file2'], case_insensitive)
                
                std_df1, std_df2 = st.session_state.std_df1, st.session_state.std_df2
                merged_df = pd.DataFrame()
                
                if st.session_state.match_mode == "精确匹配":
                    merged_df = pd.merge(std_df1, std_df2, on='name', how='outer', suffixes=('_1', '_2'))
                else: # Fuzzy Match Logic
                    names1 = std_df1['name'].unique().tolist()
                    names2 = std_df2['name'].unique().tolist()
                    matches, matched_names1, matched_names2 = [], [], []
                    
                    if len(names1) <= len(names2):
                        for name1 in names1:
                            result = process.extractOne(name1, names2, scorer=fuzz.ratio, score_cutoff=similarity_threshold)
                            if result:
                                name2, score = result
                                matches.append((name1, name2)); matched_names1.append(name1); matched_names2.append(name2)
                                names2.remove(name2)
                    else:
                        for name2 in names2:
                            result = process.extractOne(name2, names1, scorer=fuzz.ratio, score_cutoff=similarity_threshold)
                            if result:
                                name1, score = result
                                matches.append((name1, name2)); matched_names1.append(name1); matched_names2.append(name2)
                                names1.remove(name1)
                    
                    if matches:
                        df1_matches = std_df1[std_df1['name'].isin(matched_names1)].add_suffix('_1')
                        df2_matches = std_df2[std_df2['name'].isin(matched_names2)].add_suffix('_2')
                        
                        match_map = pd.DataFrame(matches, columns=['name_1', 'name_2'])
                        
                        merged_df = pd.merge(df1_matches, match_map, on='name_1', how='left')
                        merged_df = pd.merge(merged_df, df2_matches, on='name_2', how='left')
                        merged_df.rename(columns={'name_1': 'name'}, inplace=True)

                def get_diff_details(row):
                    diffs = []
                    is_diff = lambda v1, v2: v1 != v2 and not (pd.isna(v1) and pd.isna(v2))
                    if is_diff(row.get('start_date_1'), row.get('start_date_2')): diffs.append("入住日期")
                    if is_diff(row.get('end_date_1'), row.get('end_date_2')): diffs.append("离开日期")
                    if is_diff(row.get('room_type_1'), row.get('room_type_2')): diffs.append("房型")
                    if is_diff(row.get('room_number_1'), row.get('room_number_2')): diffs.append("房号")
                    return ', '.join(diffs)

                if 'name' in merged_df.columns:
                    common_rows = merged_df.dropna(subset=[c for c in merged_df.columns if '_1' in c or '_2' in c]).copy()
                    common_rows['差异摘要'] = common_rows.apply(get_diff_details, axis=1)
                    st.session_state.mismatched_df = common_rows[common_rows['差异摘要'] != '']
                    st.session_state.matched_df = common_rows[common_rows['差异摘要'] == '']
                else:
                    st.session_state.mismatched_df = pd.DataFrame()
                    st.session_state.matched_df = pd.DataFrame()

                if st.session_state.match_mode == "精确匹配":
                    unmatched_1_mask = merged_df[std_df2.columns.drop('name').add_suffix('_2')].isna().all(axis=1)
                    st.session_state.in_file1_only = merged_df[unmatched_1_mask][std_df1.columns].copy()
                    unmatched_2_mask = merged_df[std_df1.columns.drop('name').add_suffix('_1')].isna().all(axis=1)
                    st.session_state.in_file2_only = merged_df[unmatched_2_mask][std_df2.columns].copy()
                else:
                    st.session_state.in_file1_only = std_df1[~std_df1['name'].isin([m[0] for m in matches])].copy()
                    st.session_state.in_file2_only = std_df2[~std_df2['name'].isin([m[1] for m in matches])].copy()

    if st.session_state.ran_comparison:
        st.header("比对结果")
        st.subheader("📊 结果摘要统计")
        stat_cols = st.columns(5)
        stat_cols[0].metric("名单1 总人数", st.session_state.std_df1['name'].nunique())
        stat_cols[1].metric("名单2 总人数", st.session_state.std_df2['name'].nunique())
        stat_cols[2].metric("✅ 信息完全一致", len(st.session_state.matched_df))
        stat_cols[3].metric("⚠️ 信息不一致", len(st.session_state.mismatched_df), delta_color="inverse")
        stat_cols[4].metric("❓ 单边存在人数", len(st.session_state.in_file1_only) + len(st.session_state.in_file2_only))

        st.subheader("1. 信息不一致的名单")
        if not st.session_state.mismatched_df.empty:
            mismatched_df_display = st.session_state.mismatched_df.copy()
            display_cols = ['差异摘要']
            if st.session_state.match_mode == "模糊匹配 (识别相似姓名)":
                mismatched_df_display['姓名 (文件1)'] = mismatched_df_display['name_original_1']
                mismatched_df_display['姓名 (文件2)'] = mismatched_df_display['name_original_2']
                display_cols.extend(['姓名 (文件1)', '姓名 (文件2)'])
            else:
                display_cols.append('name')
            
            other_cols = [c for c in mismatched_df_display.columns if c not in display_cols and '_original' not in c and c not in ['name', 'name_2']]
            display_cols.extend(other_cols)
            
            st.markdown("下方将逐条展示不一致的项目，并提供诊断报告。")
            for index, row in st.session_state.mismatched_df.iterrows():
                row_df = pd.DataFrame(row).transpose()
                display_row = row_df[display_cols] if 'name' in display_cols else row_df[[c for c in display_cols if c in row_df.columns]]
                st.dataframe(style_diffs(display_row))
                with st.expander("🔍 点击查看深度诊断报告"):
                    diff_summary = row['差异摘要']
                    diff_cols = diff_summary.replace(' ', '').split(',')
                    col_map = {"入住日期": "start_date", "离开日期": "end_date", "房型": "room_type", "房号": "room_number"}
                    for col_name_zh in diff_cols:
                        col_base = col_map.get(col_name_zh)
                        if col_base:
                            st.markdown(f"--- \n### 对比字段: **{col_name_zh}**")
                            st.markdown(diagnose_difference(row.get(f'{col_base}_1'), row.get(f'{col_base}_2')), unsafe_allow_html=True)
        else:
            st.info("✅ 两份名单中共同存在的人员，信息均一致。")

        st.subheader(f"2. 仅存在于名单 1 ({st.session_state.df1_name}) 的人员")
        if not st.session_state.in_file1_only.empty:
            st.warning(f"共发现 {len(st.session_state.in_file1_only)} 人")
            st.dataframe(st.session_state.in_file1_only.drop(columns=['name_original'], errors='ignore'))
        else:
            st.info(f"✅ 名单1中的所有人员都在名单2中。")

        st.subheader(f"3. 仅存在于名单 2 ({st.session_state.df2_name}) 的人员")
        if not st.session_state.in_file2_only.empty:
            st.info(f"共发现 {len(st.session_state.in_file2_only)} 人")
            st.dataframe(st.session_state.in_file2_only.drop(columns=['name_original'], errors='ignore'))
        else:
            st.info(f"✅ 名单2中的所有人员都在名单1中。")
        
        st.subheader("4. 信息完全一致的名单")
        if not st.session_state.matched_df.empty:
            with st.expander(f"共 {len(st.session_state.matched_df)} 人信息完全一致，点击查看"):
                st.dataframe(st.session_state.matched_df.drop(columns=['差异摘要', 'name_original_1', 'name_original_2', 'name_2'], errors='ignore'))
        else:
            st.info("没有找到信息完全一致的人员。")

    st.divider()
    st.header("原始上传文件预览 (点击比对后会按姓名排序)")
    c1, c2 = st.columns(2)
    with c1:
        st.caption(f"文件 1: {st.session_state.df1_name}")
        st.dataframe(st.session_state.df1)
    with c2:
        st.caption(f"文件 2: {st.session_state.df2_name}")
        st.dataframe(st.session_state.df2)
