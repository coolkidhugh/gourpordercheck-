import pandas as pd
import streamlit as st
import re
import unicodedata

st.set_page_config(page_title="精准可视化名单比对", layout="wide")

# --- Session State Initialization ---
if 'df1' not in st.session_state: st.session_state.df1 = None
if 'df2' not in st.session_state: st.session_state.df2 = None
if 'df1_name' not in st.session_state: st.session_state.df1_name = ""
if 'df2_name' not in st.session_state: st.session_state.df2_name = ""

# --- Helper Functions ---

def forensic_clean_name(name, case_insensitive=False):
    """Cleans and standardizes name strings."""
    if not isinstance(name, str): return ''
    try:
        name = unicodedata.normalize('NFKC', name)
    except:
        pass
    name = re.sub(r'[\u200B-\u200D\uFEFF\s]+', '', name).strip()
    return name.lower() if case_insensitive else name

def process_and_standardize(df, mapping, case_insensitive=False, room_type_equivalents=None):
    """Reads, cleans, and standardizes the dataframe based on user mapping."""
    if not all([mapping['name'], mapping['start_date'], mapping['end_date']]):
        return None

    standard_df = pd.DataFrame()
    standard_df['name'] = df[mapping['name']].astype(str)
    
    # --- MAJOR FIX for Date Comparison ---
    # Convert to datetime, then immediately to a standardized YYYY-MM-DD string.
    # This eliminates any underlying format/type differences (e.g., Date vs. Timestamp).
    standard_df['start_date'] = pd.to_datetime(df[mapping['start_date']], errors='coerce').dt.strftime('%Y-%m-%d')
    standard_df['end_date'] = pd.to_datetime(df[mapping['end_date']], errors='coerce').dt.strftime('%Y-%m-%d')
    
    if mapping['room_type']:
        standard_df['room_type'] = df[mapping['room_type']].astype(str).str.strip()
        if room_type_equivalents:
            reverse_map = {v: k for k, values in room_type_equivalents.items() for v in values}
            standard_df['room_type'] = standard_df['room_type'].replace(reverse_map)
    if mapping['price']:
        standard_df['price'] = pd.to_numeric(df[mapping['price']], errors='coerce')
    if mapping['room_number']:
        standard_df['room_number'] = df[mapping['room_number']].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)

    standard_df['name'] = standard_df['name'].str.replace('、', ',', regex=False).str.split(',')
    standard_df = standard_df.explode('name')
    standard_df['name'] = standard_df['name'].apply(forensic_clean_name, case_insensitive=case_insensitive)
    
    # Drop rows if the string conversion of dates resulted in NaT -> NaN
    standard_df.dropna(subset=['name', 'start_date', 'end_date'], inplace=True)
    standard_df = standard_df[standard_df['name'] != '']
    
    return standard_df

def style_diffs(df):
    """Applies color highlighting to differing cells."""
    style_df = pd.DataFrame('', index=df.index, columns=df.columns)
    highlight_color = 'background-color: #FFC7CE'
    compare_cols = ['start_date', 'end_date', 'room_type', 'room_number', 'price']

    for col_base in compare_cols:
        col1, col2 = f'{col_base}_1', f'{col_base}_2'
        if col1 in df.columns and col2 in df.columns:
            # NaNs were handled by strftime, so a direct comparison is now safe.
            is_diff = df[col1] != df[col2]
            is_diff &= ~(df[col1].isna() & df[col2].isna())
            style_df.loc[is_diff, col1] = highlight_color
            style_df.loc[is_diff, col2] = highlight_color
            
    return df.style.apply(lambda s: style_df, axis=None)

# --- UI Layout ---

st.title("精准可视化名单比对工具 V13.1 🎯")
st.info("精准模式：彻底解决日期格式问题，新增“差异摘要”列并置顶，比对更准、查看更易！")

st.header("第 1 步: 上传文件")
if st.button("🔄 清空并重置"):
    st.session_state.clear()
    st.rerun()

col1, col2 = st.columns(2)
# ... (File uploaders remain the same)
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


if 'df1' in st.session_state and st.session_state.df1 is not None and \
   'df2' in st.session_state and st.session_state.df2 is not None:
    
    st.success("文件上传成功！请继续下一步。")

    st.header("第 2 步: 选择用于比对的列")
    mapping = {'file1': {}, 'file2': {}}
    # ... (Column mapping UI remains the same)
    cols1, cols2 = st.columns(2)
    with cols1:
        st.subheader(f"文件 1: {st.session_state.df1_name}")
        df1_cols = [None] + list(st.session_state.df1.columns)
        mapping['file1']['name'] = st.selectbox("姓名 (必选)", df1_cols, key='f1_name')
        mapping['file1']['start_date'] = st.selectbox("入住日期 (必选)", df1_cols, key='f1_start')
        mapping['file1']['end_date'] = st.selectbox("离开日期 (必选)", df1_cols, key='f1_end')
        mapping['file1']['room_type'] = st.selectbox("房型 (可选)", df1_cols, key='f1_room')
        mapping['file1']['room_number'] = st.selectbox("房号 (可选)", df1_cols, key='f1_room_num')
        mapping['file1']['price'] = st.selectbox("房价 (可选)", df1_cols, key='f1_price')
    with cols2:
        st.subheader(f"文件 2: {st.session_state.df2_name}")
        df2_cols = [None] + list(st.session_state.df2.columns)
        mapping['file2']['name'] = st.selectbox("姓名 (必选)", df2_cols, key='f2_name')
        mapping['file2']['start_date'] = st.selectbox("入住日期 (必选)", df2_cols, key='f2_start')
        mapping['file2']['end_date'] = st.selectbox("离开日期 (必选)", df2_cols, key='f2_end')
        mapping['file2']['room_type'] = st.selectbox("房型 (可选)", df2_cols, key='f2_room')
        mapping['file2']['room_number'] = st.selectbox("房号 (可选)", df2_cols, key='f2_room_num')
        mapping['file2']['price'] = st.selectbox("房价 (可选)", df2_cols, key='f2_price')


    st.header("第 3 步: 配置与执行")
    # ... (Room type mapping and checkbox UI remains the same)
    room_type_equivalents = {}
    if mapping['file1']['room_type'] and mapping['file2']['room_type']:
        with st.expander("如果两份名单中的房型名称不一致，请在此建立对应关系"):
            unique_rooms1 = st.session_state.df1[mapping['file1']['room_type']].dropna().astype(str).unique()
            unique_rooms2 = list(st.session_state.df2[mapping['file2']['room_type']].dropna().astype(str).unique())
            for room1 in unique_rooms1:
                room_type_equivalents[room1] = st.multiselect(f"文件1的“{room1}”等同于文件2的:", unique_rooms2, key=f"map_{room1}")
    
    case_insensitive = st.checkbox("比对英文名时忽略大小写 (e.g., 'John' = 'john')")
    
    if st.button("🚀 开始比对", type="primary"):
        if not all([mapping['file1']['name'], mapping['file1']['start_date'], mapping['file1']['end_date'],
                    mapping['file2']['name'], mapping['file2']['start_date'], mapping['file2']['end_date']]):
            st.error("请确保两边文件的“姓名”、“入住日期”、“离开日期”都已正确选择。")
        else:
            with st.spinner('正在执行精准比对...'):
                st.session_state.df1.sort_values(by=mapping['file1']['name'], inplace=True, ignore_index=True)
                st.session_state.df2.sort_values(by=mapping['file2']['name'], inplace=True, ignore_index=True)

                std_df1 = process_and_standardize(st.session_state.df1, mapping['file1'], case_insensitive, room_type_equivalents)
                std_df2 = process_and_standardize(st.session_state.df2, mapping['file2'], case_insensitive, room_type_equivalents)
                
                merged_df = pd.merge(std_df1, std_df2, on='name', how='outer', suffixes=('_1', '_2'))
                
                def get_diff_details(row):
                    diffs = []
                    is_diff = lambda v1, v2: v1 != v2 and not (pd.isna(v1) and pd.isna(v2))
                    if is_diff(row.get('start_date_1'), row.get('start_date_2')): diffs.append("入住日期")
                    if is_diff(row.get('end_date_1'), row.get('end_date_2')): diffs.append("离开日期")
                    if is_diff(row.get('room_type_1'), row.get('room_type_2')): diffs.append("房型")
                    if is_diff(row.get('room_number_1'), row.get('room_number_2')): diffs.append("房号")
                    if is_diff(row.get('price_1'), row.get('price_2')): diffs.append("房价")
                    return ', '.join(diffs)

                both_present = merged_df['start_date_1'].notna() & merged_df['start_date_2'].notna()
                temp_df = merged_df[both_present].copy()
                if not temp_df.empty:
                    temp_df['差异摘要'] = temp_df.apply(get_diff_details, axis=1)
                else:
                    temp_df['差异摘要'] = ''
                
                mismatched_df = temp_df[temp_df['差异摘要'] != ''].copy()
                matched_df = temp_df[temp_df['差异摘要'] == ''].copy()
                in_file1_only = merged_df[merged_df['start_date_2'].isna()].copy()
                in_file2_only = merged_df[merged_df['start_date_1'].isna()].copy()

                st.header("比对结果")
                st.subheader("📊 结果摘要统计")
                # ... (Summary stats UI remains the same)
                stat_cols = st.columns(5)
                stat_cols[0].metric("名单1 总人数", len(std_df1))
                stat_cols[1].metric("名单2 总人数", len(std_df2))
                stat_cols[2].metric("✅ 信息完全一致", len(matched_df))
                stat_cols[3].metric("⚠️ 信息不一致", len(mismatched_df), delta_color="inverse")
                stat_cols[4].metric("❓ 单边存在人数", len(in_file1_only) + len(in_file2_only))
                
                st.subheader("1. 信息不一致的名单 (先看“差异摘要”，再看高亮项)")
                if not mismatched_df.empty:
                    # --- MAJOR FIX for column order ---
                    # Move the summary column to the front for clarity.
                    cols_order = ['差异摘要', 'name'] + [c for c in mismatched_df.columns if c not in ['差异摘要', 'name']]
                    mismatched_df = mismatched_df[cols_order]
                    st.dataframe(style_diffs(mismatched_df))
                else:
                    st.info("✅ 两份名单中共同存在的人员，信息均一致。")

                st.subheader(f"2. 仅存在于名单 1 ({st.session_state.df1_name}) 的人员")
                # ... (Display for in_file1_only remains the same)
                if not in_file1_only.empty:
                    st.warning(f"共发现 {len(in_file1_only)} 人")
                    st.dataframe(in_file1_only.dropna(axis=1, how='all'))
                else:
                    st.info(f"✅ 名单1中的所有人员都在名单2中。")

                st.subheader(f"3. 仅存在于名单 2 ({st.session_state.df2_name}) 的人员")
                # ... (Display for in_file2_only remains the same)
                if not in_file2_only.empty:
                    st.info(f"共发现 {len(in_file2_only)} 人")
                    st.dataframe(in_file2_only.dropna(axis=1, how='all'))
                else:
                    st.info(f"✅ 名单2中的所有人员都在名单1中。")
                
                st.subheader("4. 信息完全一致的名单")
                # ... (Display for matched_df remains the same)
                if not matched_df.empty:
                    with st.expander(f"共 {len(matched_df)} 人信息完全一致，点击查看"):
                        st.dataframe(matched_df.drop(columns=['差异摘要']))
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
