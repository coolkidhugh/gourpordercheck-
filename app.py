import pandas as pd
import streamlit as st

st.set_page_config(page_title="交互式名单比对平台", layout="wide")

# --- 初始化 Session State ---
# 使用Session State来存储上传的文件和用户的选择，避免每次操作都重置
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
    # 筛选出用户选择的列
    
    # 检查必需的列是否已映射
    if not all([mapping['name'], mapping['start_date'], mapping['end_date']]):
        return None # 如果核心列没有映射，则不处理

    # 从原始df中根据映射关系，提取并重命名列，构建新的df
    standard_df = pd.DataFrame()
    standard_df['name'] = df[mapping['name']].astype(str)
    standard_df['start_date'] = pd.to_datetime(df[mapping['start_date']], errors='coerce').dt.date
    standard_df['end_date'] = pd.to_datetime(df[mapping['end_date']], errors='coerce').dt.date
    
    # 可选列
    if mapping['room_type']:
        standard_df['room_type'] = df[mapping['room_type']].astype(str)
        # 如果有房型映射关系，则进行转换
        if room_type_equivalents:
            # 创建一个反向映射，方便替换
            reverse_map = {}
            for key, values in room_type_equivalents.items():
                for value in values:
                    reverse_map[value] = key
            standard_df['room_type'] = standard_df['room_type'].replace(reverse_map)

    if mapping['price']:
        standard_df['price'] = pd.to_numeric(df[mapping['price']], errors='coerce')
        
    # 清理姓名列（拆分同住人）
    standard_df['name'] = standard_df['name'].str.replace('、', ',', regex=False).str.split(',')
    standard_df = standard_df.explode('name')
    standard_df['name'] = standard_df['name'].str.strip()
    
    # 删除无效行
    standard_df.dropna(subset=['name', 'start_date', 'end_date'], inplace=True)
    standard_df = standard_df[standard_df['name'] != '']
    
    return standard_df


# --- 界面 ---
st.title("交互式名单比对平台 V7.0 Pro 🚀")
st.info("请上传两个Excel或CSV文件，然后按照引导完成列的映射和房型的匹配。")

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

# 当两个文件都上传成功后，显示后续步骤
if st.session_state.df1 is not None and st.session_state.df2 is not None:
    
    st.success("文件上传成功！请继续下一步。")

    # --- 步骤 2: 映射比较列 ---
    st.header("第 2 步: 选择用于比对的列")
    
    mapping = {
        'file1': {'name': None, 'start_date': None, 'end_date': None, 'room_type': None, 'price': None},
        'file2': {'name': None, 'start_date': None, 'end_date': None, 'room_type': None, 'price': None}
    }
    
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
        st.info("如果两份名单中的房型名称不一致，您可以在此建立对应关系。")
        
        unique_rooms1 = st.session_state.df1[mapping['file1']['room_type']].dropna().unique()
        unique_rooms2 = list(st.session_state.df2[mapping['file2']['room_type']].dropna().unique())
        
        # 使用expander避免界面过长
        with st.expander("点击展开房型匹配设置"):
            for room1 in unique_rooms1:
                # 让用户为文件1的每个房型，在文件2的房型列表中选择一个或多个等价的房型
                room_type_equivalents[room1] = st.multiselect(
                    f"文件1中的“{room1}”等同于文件2中的:",
                    unique_rooms2,
                    key=f"map_{room1}"
                )
    
    # --- 执行比较 ---
    if st.button("🚀 开始比对", type="primary"):
        # 检查核心列是否都已选择
        if not all([mapping['file1']['name'], mapping['file1']['start_date'], mapping['file1']['end_date'],
                    mapping['file2']['name'], mapping['file2']['start_date'], mapping['file2']['end_date']]):
            st.error("请确保两边文件的“姓名”、“入住日期”、“离开日期”都已正确选择。")
        else:
            # 根据用户的映射关系，处理和标准化两个DataFrame
            # 注意：我们将文件2的房型标准化到文件1的房型体系中
            std_df1 = process_and_standardize(st.session_state.df1, mapping['file1'])
            std_df2 = process_and_standardize(st.session_state.df2, mapping['file2'], room_type_equivalents)
            
            # 合并处理后的数据
            merged_df = pd.merge(
                std_df1, 
                std_df2, 
                on='name', 
                how='outer', 
                suffixes=(f'_{st.session_state.df1_name}', f'_{st.session_state.df2_name}')
            )
            
            # --- 分析和展示结果 ---
            st.header("比对结果")

            # 找出存在于两边但信息不一致的数据
            # fillna(0)是为了处理空值，避免比较时出错
            mismatch_filter = (merged_df[f'start_date_{st.session_state.df1_name}'].notna()) & \
                              (merged_df[f'start_date_{st.session_state.df2_name}'].notna()) & \
                              ((merged_df[f'start_date_{st.session_state.df1_name}'] != merged_df[f'start_date_{st.session_state.df2_name}']) |
                               (merged_df[f'end_date_{st.session_state.df1_name}'] != merged_df[f'end_date_{st.session_state.df2_name}']) |
                               (merged_df.get(f"room_type_{st.session_state.df1_name}", pd.Series(dtype='object')).fillna(0) != merged_df.get(f"room_type_{st.session_state.df2_name}", pd.Series(dtype='object')).fillna(0)) |
                               (merged_df.get(f"price_{st.session_state.df1_name}", pd.Series(dtype='object')).fillna(0) != merged_df.get(f"price_{st.session_state.df2_name}", pd.Series(dtype='object')).fillna(0))
                               )
            mismatched_df = merged_df[mismatch_filter]

            in_file1_only = merged_df[merged_df[f'start_date_{st.session_state.df2_name}'].isna()]
            in_file2_only = merged_df[merged_df[f'start_date_{st.session_state.df1_name}'].isna()]
            
            # 完全匹配的数据
            matched_df = merged_df.dropna().drop(mismatched_df.index, errors='ignore')

            st.subheader("1. 信息不一致的名单")
            if not mismatched_df.empty:
                st.dataframe(mismatched_df)
            else:
                st.info("✅ 两份名单中共同存在的人员，信息均一致。")

            st.subheader(f"2. 仅存在于名单 1 ({st.session_state.df1_name}) 的人员")
            if not in_file1_only.empty:
                st.warning(f"共发现 {len(in_file1_only)} 人，请关注！")
                st.dataframe(in_file1_only.dropna(axis=1, how='all'))
            else:
                st.info(f"✅ 名单1中的所有人员都在名单2中。")

            st.subheader(f"3. 仅存在于名单 2 ({st.session_state.df2_name}) 的人员")
            if not in_file2_only.empty:
                st.info(f"共发现 {len(in_file2_only)} 人，请确认。")
                st.dataframe(in_file2_only.dropna(axis=1, how='all'))
            else:
                st.info(f"✅ 名单2中的所有人员都在名单1中。")
            
            st.subheader("4. 信息完全一致的名单")
            if not matched_df.empty:
                st.dataframe(matched_df)
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
