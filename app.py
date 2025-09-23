import pandas as pd
import streamlit as st
import re
import unicodedata

st.set_page_config(page_title="可视化智能名单比对平台", layout="wide")

# --- Initialize Session State ---
if 'df1' not in st.session_state: st.session_state.df1 = None
if 'df2' not in st.session_state: st.session_state.df2 = None
if 'df1_name' not in st.session_state: st.session_state.df1_name = ""
if 'df2_name' not in st.session_state: st.session_state.df2_name = ""

def forensic_clean_name(name):
    """【鉴证级清洁】只保留中文字符和英文字母，清除一切幽灵字符。"""
    if not isinstance(name, str):
        return ''
    # 使用正则表达式移除所有非中文、非字母的字符
    cleaned_name = re.sub(r'[^\u4e00-\u9fa5a-zA-Z]', '', name)
    return cleaned_name

def process_and_standardize(df, mapping, room_type_equivalents=None):
    """根据用户映射来处理和标准化DataFrame"""
    if not all([mapping['name'], mapping['start_date'], mapping['end_date']]):
        return None

    standard_df = pd.DataFrame()
    standard_df['name'] = df[mapping['name']].astype(str)
    standard_df['start_date'] = pd.to_datetime(df[mapping['start_date']], errors='coerce').dt.date
    standard_df['end_date'] = pd.to_datetime(df[mapping['end_date']], errors='coerce').dt.date
    
    # Optional columns
    if mapping['room_type']:
        standard_df['room_type'] = df[mapping['room_type']].astype(str).str.strip()
        if room_type_equivalents:
            reverse_map = {value: key for key, values in room_type_equivalents.items() for value in values}
            standard_df['room_type'] = standard_df['room_type'].replace(reverse_map)
    if mapping['price']:
        standard_df['price'] = pd.to_numeric(df[mapping['price']], errors='coerce')
    if mapping['room_number']:
        standard_df['room_number'] = df[mapping['room_number']].astype(str).str.strip().str.replace(r'\.0$', '', regex=True) # 清理类似 '101.0' 的情况

    # --- 拆分和终极清洁姓名 ---
    standard_df['name'] = standard_df['name'].str.replace('、', ',', regex=False).str.split(',')
    standard_df = standard_df.explode('name')
    standard_df['name'] = standard_df['name'].apply(forensic_clean_name) # 应用鉴证级清洁
    
    standard_df.dropna(subset=['name', 'start_date', 'end_date'], inplace=True)
    standard_df = standard_df[standard_df['name'] != '']
    
    return standard_df

# --- UI Section ---
st.title("可视化智能名单比对平台 V10.0 Forensic Edition 🏆")
st.info("终极版：具备【鉴证级数据清洁】功能，新增【房号】比对，颜色高亮已彻底修复！")

st.header("第 1 步: 上传文件")
# (File upload UI remains the same)
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

    st.header("第 3 步: 匹配房型 (可选)")
    room_type_equivalents = {}
    if mapping['file1']['room_type'] and mapping['file2']['room_type']:
        with st.expander("如果两份名单中的房型名称不一致，请在此建立对应关系"):
            unique_rooms1 = st.session_state.df1[mapping['file1']['room_type']].dropna().astype(str).unique()
            unique_rooms2 = list(st.session_state.df2[mapping['file2']['room_type']].dropna().astype(str).unique())
            for room1 in unique_rooms1:
                room_type_equivalents[room1] = st.multiselect(f"文件1的“{room1}”等同于文件2的:", unique_rooms2, key=f"map_{room1}")
    
    if st.button("🚀 开始比对", type="primary"):
        if not all([mapping['file1']['name'], mapping['file1']['start_date'], mapping['file1']['end_date'],
                    mapping['file2']['name'], mapping['file2']['start_date'], mapping['file2']['end_date']]):
            st.error("请确保两边文件的“姓名”、“入住日期”、“离开日期”都已正确选择。")
        else:
            std_df1 = process_and_standardize(st.session_state.df1, mapping['file1'])
            std_df2 = process_and_standardize(st.session_state.df2, mapping['file2'], room_type_equivalents)
            
            merged_df = pd.merge(std_df1, std_df2, on='name', how='outer', suffixes=('_1', '_2'))
            
            def get_diff_details(row):
                diffs = []
                def is_different(val1, val2): return val1 != val2 and not (pd.isna(val1) and pd.isna(val2))
                if is_different(row.get('start_date_1'), row.get('start_date_2')): diffs.append(f"入住日期")
                if is_different(row.get('end_date_1'), row.get('end_date_2')): diffs.append(f"离开日期")
                if is_different(row.get('room_type_1'), row.get('room_type_2')): diffs.append(f"房型")
                if is_different(row.get('room_number_1'), row.get('room_number_2')): diffs.append(f"房号")
                if is_different(row.get('price_1'), row.get('price_2')): diffs.append(f"房价")
                return ', '.join(diffs)

            # --- 【彻底修复】重写颜色高亮逻辑 ---
            def style_diffs(df_to_style):
                style_df = pd.DataFrame('', index=df_to_style.index, columns=df_to_style.columns)
                highlight_color = 'background-color: #FFC7CE'
                for col_name in ['start_date', 'end_date', 'room_type', 'room_number', 'price']:
                    col1, col2 = f'{col_name}_1', f'{col_name}_2'
                    if col1 in df_to_style.columns and col2 in df_to_style.columns:
                        mask = (df_to_style[col1] != df_to_style[col2]) & ~(df_to_style[col1].isna() & df_to_style[col2].isna())
                        style_df.loc[mask, col1] = highlight_color
                        style_df.loc[mask, col2] = highlight_color
                return style_df

            both_present_filter = merged_df['start_date_1'].notna() & merged_df['start_date_2'].notna()
            temp_df = merged_df[both_present_filter].copy()
            if not temp_df.empty:
                temp_df['差异详情'] = temp_df.apply(get_diff_details, axis=1)
            else:
                temp_df['差异详情'] = ''
            
            mismatched_df = temp_df[temp_df['差异详情'] != '']
            matched_df = temp_df[temp_df['差异详情'] == '']
            in_file1_only = merged_df[merged_df['start_date_2'].isna()]
            in_file2_only = merged_df[merged_df['start_date_1'].isna()]

            st.header("比对结果")
            st.subheader("1. 信息不一致的名单 (差异项已高亮)")
            if not mismatched_df.empty:
                display_cols = ['name', '差异详情'] + [col for col in mismatched_df.columns if col not in ['name', '差异详情']]
                st.dataframe(mismatched_df[display_cols].style.apply(style_diffs, axis=None))
            else:
                st.info("✅ 两份名单中共同存在的人员，信息均一致。")
            st.subheader(f"2. 仅存在于名单 1 ({st.session_state.df1_name}) 的人员")
            if not in_file1_only.empty:
                st.warning(f"共发现 {len(in_file1_only)} 人")
                st.dataframe(in_file1_only.dropna(axis=1, how='all'))
            else:
                st.info(f"✅ 名单1中的所有人员都在名单2中。")
            st.subheader(f"3. 仅存在于名单 2 ({st.session_state.df2_name}) 的人员")
            if not in_file2_only.empty:
                st.info(f"共发现 {len(in_file2_only)} 人")
                st.dataframe(in_file2_only.dropna(axis=1, how='all'))
            else:
                st.info(f"✅ 名单2中的所有人员都在名单1中。")
            st.subheader("4. 信息完全一致的名单")
            if not matched_df.empty:
                 with st.expander(f"共 {len(matched_df)} 人信息完全一致，点击查看"):
                    st.dataframe(matched_df.drop(columns=['差异详情']))
            else:
                st.info("没有找到信息完全一致的人员。")

    st.header("数据预览")
    c1, c2 = st.columns(2)
    with c1:
        st.caption(f"文件 1: {st.session_state.df1_name}")
        st.dataframe(st.session_state.df1)
    with c2:
        st.caption(f"文件 2: {st.session_state.df2_name}")
        st.dataframe(st.session_state.df2)
