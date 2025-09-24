import pandas as pd
import streamlit as st
import re
import unicodedata

st.set_page_config(page_title="多维审核比对平台", layout="wide")

# --- Session State Initialization ---
# 使用字典统一管理所有会话状态变量，确保应用重启后状态不丢失，并避免KeyError。
SESSION_DEFAULTS = {
    'df1': None, 'df2': None, 'df1_name': "", 'df2_name': "",
    'ran_comparison': False, 'common_rows': pd.DataFrame(),
    'matched_df': pd.DataFrame(), 'in_file1_only': pd.DataFrame(),
    'in_file2_only': pd.DataFrame(), 'compare_cols_keys': []
}
for key, value in SESSION_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

# --- Helper Functions ---

def forensic_clean_text(text):
    """
    对任何文本字符串进行“法证级”深度清洁。
    这是我们对抗“幽灵字符”、全/半角不统一等问题的终极武器。
    """
    if not isinstance(text, str): return text
    try:
        # NFKC范式统一化，可以将全角字符（如：Ａ，１）转换为半角（如：A, 1）。
        cleaned_text = unicodedata.normalize('NFKC', text)
    except (TypeError, ValueError):
        return text
    # 使用正则表达式移除各种不可见的控制字符，包括零宽度空格和非中断空格(\xa0)。
    cleaned_text = re.sub(r'[\u200B-\u200D\uFEFF\s\xa0]+', '', cleaned_text)
    return cleaned_text.strip()

def process_and_standardize(df, mapping, case_insensitive=False, room_type_equivalents=None):
    """
    核心数据处理引擎。
    接收原始DataFrame和用户的列映射，输出一个干净、标准化的DataFrame用于比对。
    """
    # 如果用户没有选择最关键的“姓名”列，则无法进行处理。
    if not mapping.get('name'):
        return pd.DataFrame()

    standard_df = pd.DataFrame()
    
    # 根据用户的选择，从原始DataFrame中提取需要比对的列。
    for col_key, col_name in mapping.items():
        if col_name and col_name in df.columns:
            standard_df[col_key] = df[col_name]

    # --- 智能日期统一引擎 ---
    def robust_date_parser(series):
        """
        一个更强大的日期解析器，专门处理缺少年份的日期格式 (如 '09/26' 或 '09/26 18:00')。
        """
        def process_date(date_str):
            if pd.isna(date_str): return pd.NaT # 返回pandas的“非时间”对象
            date_str = str(date_str).strip()
            # 检查是否为 '月/日' 或 '月/日 时:分' 格式
            if re.match(r'^\d{1,2}/\d{1,2}', date_str):
                # 只取日期部分（忽略时间）
                date_part = date_str.split(' ')[0]
                # 假设年份为2025年，并重新组合成标准格式
                return f"2025-{date_part.replace('/', '-')}"
            # 如果是其他格式，直接返回让pandas处理
            return date_str
        
        # 应用自定义处理函数，然后交给pandas进行最终转换
        return pd.to_datetime(series.apply(process_date), errors='coerce').dt.strftime('%Y-%m-%d')

    if 'start_date' in standard_df.columns:
        standard_df['start_date'] = robust_date_parser(standard_df['start_date'])
    if 'end_date' in standard_df.columns:
        standard_df['end_date'] = robust_date_parser(standard_df['end_date'])
    
    if 'room_type' in standard_df.columns:
        standard_df['room_type'] = standard_df['room_type'].astype(str).apply(forensic_clean_text)
        if room_type_equivalents:
            # 清洗房型映射字典，确保映射的key和value也是干净的。
            cleaned_equivalents = {forensic_clean_text(k): [forensic_clean_text(val) for val in v] for k, v in room_type_equivalents.items()}
            reverse_map = {val: key for key, values in cleaned_equivalents.items() for val in values}
            standard_df['room_type'] = standard_df['room_type'].replace(reverse_map)
    
    if 'price' in standard_df.columns:
        standard_df['price'] = pd.to_numeric(standard_df['price'].astype(str).str.strip(), errors='coerce')

    # 对姓名列进行最终的、最关键的处理：分割多人单元格（例如 "张三/李四"）。
    standard_df['name'] = standard_df['name'].astype(str).str.split(r'[、,，/]')
    standard_df = standard_df.explode('name')
    standard_df['name'] = standard_df['name'].apply(forensic_clean_text)
        
    if case_insensitive:
        standard_df['name'] = standard_df['name'].str.lower()
        
    # 移除清洗后产生的无效行（例如姓名变成空字符串）。
    standard_df = standard_df[standard_df['name'] != ''].dropna(subset=['name']).reset_index(drop=True)
    return standard_df

def highlight_diff(row, col1, col2):
    """一个用于DataFrame样式化的函数，如果两个指定列的值不同，则高亮整行。"""
    style = 'background-color: #FFC7CE' # 浅红色
    # 增加对NaN（空值）的判断，避免将两个空值也判定为“不同”。
    if row.get(col1) != row.get(col2) and not (pd.isna(row.get(col1)) and pd.isna(row.get(col2))):
        return [style] * len(row)
    return [''] * len(row)

# --- UI Layout ---

st.title("多维审核比对平台 V23.2 🏆 (终极智能日期版)")
st.info("全新模式：结果以独立的标签页展示，并内置智能日期统一引擎，比对更精准！")

st.header("第 1 步: 上传文件")
if st.button("🔄 清空并重置"):
    st.session_state.clear()
    st.rerun()

col1, col2 = st.columns(2)
# 文件上传控件
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

# 只有当两个文件都成功上传后，才显示后续的主应用界面。
if st.session_state.df1 is not None and st.session_state.df2 is not None:
    st.header("第 2 步: 选择要比对的列 (姓名必选)")
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
    # 只有当用户为两个文件都选择了“房型”列时，才显示此高级功能。
    if mapping['file1'].get('room_type') and mapping['file2'].get('room_type'):
        with st.expander("⭐ 高级功能：统一不同名称的房型 (例如：让'大床房'='King Room')"):
            unique_rooms1 = st.session_state.df1[mapping['file1']['room_type']].dropna().astype(str).unique()
            unique_rooms2 = list(st.session_state.df2[mapping['file2']['room_type']].dropna().astype(str).unique())
            for room1 in unique_rooms1:
                room_type_equivalents[room1] = st.multiselect(f"文件1的“{room1}”等同于:", unique_rooms2, key=f"map_{room1}")

    case_insensitive = st.checkbox("比对姓名时忽略大小写/全半角", True)
    
    if st.button("🚀 开始比对", type="primary"):
        # 对用户的选择进行最终校验。
        if not mapping['file1'].get('name') or not mapping['file2'].get('name'):
            st.error("请确保两边文件的“姓名”都已正确选择。")
        else:
            with st.spinner('正在执行终极比对...'):
                st.session_state.ran_comparison = True
                
                # 为数据源预览区进行A-Z排序
                st.session_state.df1.sort_values(by=mapping['file1']['name'], inplace=True, ignore_index=True)
                st.session_state.df2.sort_values(by=mapping['file2']['name'], inplace=True, ignore_index=True)

                # 调用核心引擎处理数据
                std_df1 = process_and_standardize(st.session_state.df1, mapping['file1'], case_insensitive, room_type_equivalents)
                std_df2 = process_and_standardize(st.session_state.df2, mapping['file2'], case_insensitive)
                
                # 使用外连接（outer merge）合并两个表，找出所有关系。
                merged_df = pd.merge(std_df1, std_df2, on='name', how='outer', suffixes=('_1', '_2'))
                
                # 找出两个文件中都存在的人员
                cols1_for_check = [f"{c}_1" for c in std_df1.columns if c != 'name']
                cols2_for_check = [f"{c}_2" for c in std_df2.columns if c != 'name']
                both_exist_mask = merged_df[cols1_for_check].notna().any(axis=1) & merged_df[cols2_for_check].notna().any(axis=1)
                st.session_state.common_rows = merged_df[both_exist_mask].copy().reset_index(drop=True)

                # 找出仅单边存在的人员
                only_in_1_mask = merged_df[cols1_for_check].notna().any(axis=1) & merged_df[cols2_for_check].isna().all(axis=1)
                st.session_state.in_file1_only = merged_df[only_in_1_mask].reset_index(drop=True)
                
                only_in_2_mask = merged_df[cols1_for_check].isna().all(axis=1) & merged_df[cols2_for_check].notna().any(axis=1)
                st.session_state.in_file2_only = merged_df[only_in_2_mask].reset_index(drop=True)
                
                # 动态决定需要比对哪些细节列
                st.session_state.compare_cols_keys = [key for key in ['start_date', 'end_date', 'room_type', 'price'] if mapping['file1'].get(key) and mapping['file2'].get(key)]
                
                # 找出信息完全一致的人员
                if not st.session_state.common_rows.empty and st.session_state.compare_cols_keys:
                    condition = pd.Series(True, index=st.session_state.common_rows.index)
                    for key in st.session_state.compare_cols_keys:
                        # 两个列的值相等，或者两个列都为空值，都算作“一致”。
                        condition &= (st.session_state.common_rows[f'{key}_1'] == st.session_state.common_rows[f'{key}_2']) | \
                                     (st.session_state.common_rows[f'{key}_1'].isna() & st.session_state.common_rows[f'{key}_2'].isna())
                    st.session_state.matched_df = st.session_state.common_rows[condition]
                else:
                    # 如果没有选择任何细节列进行比对，那么所有共同存在的人都算作“信息一致”。
                    st.session_state.matched_df = st.session_state.common_rows

    # --- Results Display Section ---
    # 只有当用户点击过“开始比对”后，才显示此结果区域。
    if st.session_state.ran_comparison:
        st.header("第 4 步: 查看比对结果")

        tab_list = ["📊 结果总览"]
        tab_name_map = {'start_date': "🕵️ 入住日期", 'end_date': "🕵️ 离开日期", 'room_type': "🕵️ 房型", 'price': "🕵️ 房价"}
        
        # 动态生成标签页的标题列表
        for key in st.session_state.compare_cols_keys:
            tab_list.append(tab_name_map[key])
        
        tabs = st.tabs(tab_list)

        with tabs[0]: # 总览标签页
            st.subheader("宏观统计")
            stat_cols = st.columns(3)
            matched_count = len(st.session_state.matched_df)
            only_1_count = len(st.session_state.in_file1_only)
            only_2_count = len(st.session_state.in_file2_only)
            stat_cols[0].metric("✅ 信息完全一致", matched_count)
            stat_cols[1].metric(f"❓ 仅 '{st.session_state.df1_name}' 有", only_1_count)
            stat_cols[2].metric(f"❓ 仅 '{st.session_state.df2_name}' 有", only_2_count)

            st.subheader("人员名单详情")
            with st.expander(f"✅ 查看 {matched_count} 条信息完全一致的名单"):
                if not st.session_state.matched_df.empty:
                    st.dataframe(st.session_state.matched_df[['name']].rename(columns={'name': '姓名'}))
                else:
                    st.write("没有信息完全一致的人员。")

            with st.expander(f"❓ 查看 {only_1_count} 条仅存在于 '{st.session_state.df1_name}' 的名单"):
                if not st.session_state.in_file1_only.empty:
                    # 升级：显示单边人员的完整信息，而不仅仅是姓名。
                    display_cols_1 = [c for c in cols_to_map if f"{c}_1" in st.session_state.in_file1_only.columns]
                    display_df_1 = st.session_state.in_file1_only[[f"{c}_1" for c in display_cols_1]]
                    display_df_1.columns = [col_names_zh[cols_to_map.index(c)] for c in display_cols_1]
                    st.dataframe(display_df_1)
                else:
                    st.write("没有人员。")

            with st.expander(f"❓ 查看 {only_2_count} 条仅存在于 '{st.session_state.df2_name}' 的名单"):
                if not st.session_state.in_file2_only.empty:
                    # 升级：显示单边人员的完整信息。
                    display_cols_2 = [c for c in cols_to_map if f"{c}_2" in st.session_state.in_file2_only.columns]
                    display_df_2 = st.session_state.in_file2_only[[f"{c}_2" for c in display_cols_2]]
                    display_df_2.columns = [col_names_zh[cols_to_map.index(c)] for c in display_cols_2]
                    st.dataframe(display_df_2)
                else:
                    st.write("没有人员。")

        # 动态为每个选择的比对维度创建一个专属的标签页。
        for i, key in enumerate(st.session_state.compare_cols_keys):
            with tabs[i+1]:
                col1_name, col2_name = f'{key}_1', f'{key}_2'
                display_name = col_names_zh[cols_to_map.index(key)]
                
                st.subheader(f"【{display_name}】比对详情")
                
                if not st.session_state.common_rows.empty:
                    # 准备用于当前标签页展示的数据。
                    compare_df = st.session_state.common_rows[['name', col1_name, col2_name]].copy()
                    compare_df.rename(columns={'name': '姓名', col1_name: f'文件1 - {display_name}', col2_name: f'文件2 - {display_name}'}, inplace=True)
                    
                    # 对存在差异的行进行整行高亮。
                    styled_df = compare_df.style.apply(highlight_diff, col1=f'文件1 - {display_name}', col2=f'文件2 - {display_name}', axis=1)
                    st.dataframe(styled_df)
                else:
                    st.info("两个文件中没有共同的人员可供进行细节比对。")

    # --- Data Preview Section ---
    st.divider()
    st.header("原始数据预览 (点击比对后会按姓名排序)")
    c1, c2 = st.columns(2)
    with c1:
        st.caption(f"文件 1: {st.session_state.df1_name}")
        st.dataframe(st.session_state.df1)
    with c2:
        st.caption(f"文件 2: {st.session_state.df2_name}")
        st.dataframe(st.session_state.df2)

