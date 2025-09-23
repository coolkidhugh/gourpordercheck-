import pandas as pd
import streamlit as st

st.set_page_config(page_title="可视化智能名单比对平台", layout="wide")

# --- 初始化 Session State ---
if 'df1' not in st.session_state:
    st.session_state.df1 = None
if 'df2' not in st.session_state:
    st.session_state.df2 = None
if 'df1_name' not in st.session_state:
    st.session_state.df1_name = ""
if 'df2_name' not in st.session_state:
    st.session_state.df2_name = ""

def process_and_standardize(df, mapping, room_type_equivalents=None):
    """根据用户映射来处理和标准化DataFrame"""
    if not all([mapping['name'], mapping['start_date'], mapping['end_date']]):
        return None

    standard_df = pd.DataFrame()
    standard_df['name'] = df[mapping['name']].astype(str)
    standard_df['start_date'] = pd.to_datetime(df[mapping['start_date']], errors='coerce').dt.date
    standard_df['end_date'] = pd.to_datetime(df[mapping['end_date']], errors='coerce').dt.date
    
    if mapping['room_type']:
        standard_df['room_type'] = df[mapping['room_type']].astype(str).str.strip()
        if room_type_equivalents:
            reverse_map = {value: key for key, values in room_type_equivalents.items() for value in values}
            standard_df['room_type'] = standard_df['room_type'].replace(reverse_map)

    if mapping['price']:
        standard_df['price'] = pd.to_numeric(df[mapping['price']], errors='coerce')
        
    standard_df['name'] = standard_df['name'].str.replace('、', ',', regex=False).str.split(',')
    standard_df = standard_df.explode('name')
    standard_df['name'] = standard_df['name'].str.strip()
    
    standard_df.dropna(subset=['name', 'start_date', 'end_date'], inplace=True)
    standard_df = standard_df[standard_df['name'] != '']
    
    return standard_df

# --- 界面 ---
st.title("可视化智能名单比对平台 V9.0 Ultimate ✨")
st.info("终极版功能：上传文件 -> 映射列 -> 匹配房型 -> 查看带【颜色高亮】和【差异说明】的比对结果！")

# (文件上传和映射部分的UI代码与V8版本相同，此处保持不变)
# --- 步骤 1: 文件上传 ---
st.header("第 1 步: 上传文件")
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

    # --- 步骤 2: 映射比较列 ---
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
        mapping['file1']['price'] = st.selectbox("房价 (可选)", df1_cols, key='f1_price')

    with cols2:
        st.subheader(f"文件 2: {st.session_state.df2_name}")
        df2_cols = [None] + list(st.session_state.df2.columns)
        mapping['file2']['name'] = st.selectbox("姓名 (必选)", df2_cols, key='f2_name')
        mapping['file2']['start_date'] = st.selectbox("入住日期 (必选)", df2_cols, key='f2_start')
        mapping['file2']['end_date'] = st.selectbox("离开日期 (必选)", df2_cols, key='f2_end')
        mapping['file2']['room_type'] = st.selectbox("房型 (可选)", df2_cols, key='f2_room')
        mapping['file2']['price'] = st.selectbox("房价 (可选)", df2_cols, key='f2_price')

    # --- 步骤 3: 匹配房型 ---
    room_type_equivalents = {}
    if mapping['file1']['room_type'] and mapping['file2']['room_type']:
        st.header("第 3 步: 匹配房型 (可选)")
        with st.expander("如果两份名单中的房型名称不一致，请在此建立对应关系"):
            unique_rooms1 = st.session_state.df1[mapping['file1']['room_type']].dropna().astype(str).unique()
            unique_rooms2 = list(st.session_state.df2[mapping['file2']['room_type']].dropna().astype(str).unique())
            for room1 in unique_rooms1:
                room_type_equivalents[room1] = st.multiselect(f"文件1的“{room1}”等同于文件2的:", unique_rooms2, key=f"map_{room1}")
    
    # --- 执行比较 ---
    if st.button("🚀 开始比对", type="primary"):
        if not all([mapping['file1']['name'], mapping['file1']['start_date'], mapping['file1']['end_date'],
                    mapping['file2']['name'], mapping['file2']['start_date'], mapping['file2']['end_date']]):
            st.error("请确保两边文件的“姓名”、“入住日期”、“离开日期”都已正确选择。")
        else:
            std_df1 = process_and_standardize(st.session_state.df1, mapping['file1'])
            std_df2 = process_and_standardize(st.session_state.df2, mapping['file2'], room_type_equivalents)
            
            merged_df = pd.merge(std_df1, std_df2, on='name', how='outer', suffixes=('_1', '_2'))
            
            # --- 【核心升级】定义颜色高亮和差异说明的逻辑 ---
            def highlight_and_describe_diffs(row):
                styles = [''] * len(row)
                diffs = []
                highlight_color = 'background-color: #FFC7CE' # 淡红色

                # 比较函数
                def compare_and_style(col1, col2, name):
                    val1, val2 = row.get(col1), row.get(col2)
                    if val1 != val2:
                        diffs.append(f"{name}: {val1} != {val2}")
                        if col1 in row.index: styles[row.index.get_loc(col1)] = highlight_color
                        if col2 in row.index: styles[row.index.get_loc(col2)] = highlight_color
                
                compare_and_style('start_date_1', 'start_date_2', '入住日期')
                compare_and_style('end_date_1', 'end_date_2', '离开日期')
                compare_and_style('room_type_1', 'room_type_2', '房型')
                compare_and_style('price_1', 'price_2', '房价')
                
                row['差异详情'] = ', '.join(diffs)
                return styles, row

            both_present_filter = merged_df['start_date_1'].notna() & merged_df['start_date_2'].notna()
            temp_df = merged_df[both_present_filter].copy()
            
            # 应用差异分析
            analysis_results = [highlight_and_describe_diffs(row) for index, row in temp_df.iterrows()]
            styles_list = [res[0] for res in analysis_results]
            updated_rows = [res[1] for res in analysis_results]
            
            if updated_rows:
                temp_df = pd.DataFrame(updated_rows, index=temp_df.index)
                styler = temp_df.style.apply(lambda s, styles: styles.pop(0), styles=styles_list, axis=None)
            else:
                styler = temp_df.style # 如果没有不匹配项，则使用默认样式
            
            mismatched_df = temp_df[temp_df['差异详情'] != '']
            matched_df = temp_df[temp_df['差异详情'] == '']
            in_file1_only = merged_df[merged_df['start_date_2'].isna()]
            in_file2_only = merged_df[merged_df['start_date_1'].isna()]

            # --- 展示结果 ---
            st.header("比对结果")
            st.subheader("1. 信息不一致的名单 (差异项已高亮)")
            if not mismatched_df.empty:
                display_cols = ['name', '差异详情'] + [col for col in mismatched_df.columns if col not in ['name', '差异详情']]
                # 应用样式并展示
                st.dataframe(mismatched_df[display_cols].style.apply(highlight_and_describe_diffs, axis=1)[0])
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
