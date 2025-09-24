import pandas as pd
import streamlit as st
import re
import unicodedata

st.set_page_config(page_title="深度比对总览工具", layout="wide")

# --- Helper Functions ---

def forensic_clean_text(text):
    """Applies the highest level of cleaning to any text string."""
    if not isinstance(text, str):
        return text
    try:
        cleaned_text = unicodedata.normalize('NFKC', text)
    except (TypeError, ValueError):
        return text
    cleaned_text = re.sub(r'[\u200B-\u200D\uFEFF\s\xa0]+', '', cleaned_text)
    return cleaned_text.strip()

def process_and_standardize(df, mapping, case_insensitive=False, room_type_equivalents=None):
    """Cleans and standardizes all selected columns from the user."""
    # Return an empty DataFrame if required columns are not selected
    if not all(mapping.get(key) for key in ['name', 'start_date', 'end_date']):
        return pd.DataFrame(columns=['name', 'start_date', 'end_date', 'name_original'])

    standard_df = pd.DataFrame()
    
    # Keep original un-exploded name for reference
    standard_df['original_name_group'] = df[mapping['name']].astype(str)
    
    # Process required columns
    name_series = df[mapping['name']].astype(str)
    standard_df['start_date'] = pd.to_datetime(df[mapping['start_date']].astype(str).str.strip(), errors='coerce').dt.strftime('%Y-%m-%d')
    standard_df['end_date'] = pd.to_datetime(df[mapping['end_date']].astype(str).str.strip(), errors='coerce').dt.strftime('%Y-%m-%d')

    # Process optional columns only if they are selected
    if mapping.get('room_type') and mapping['room_type'] in df.columns:
        standard_df['room_type'] = df[mapping['room_type']].astype(str).apply(forensic_clean_text)
        if room_type_equivalents:
            cleaned_equivalents = {forensic_clean_text(k): [forensic_clean_text(val) for val in v] for k, v in room_type_equivalents.items()}
            reverse_map = {val: key for key, values in cleaned_equivalents.items() for val in values}
            standard_df['room_type'] = standard_df['room_type'].replace(reverse_map)

    if mapping.get('price') and mapping['price'] in df.columns:
        standard_df['price'] = pd.to_numeric(df[mapping['price']].astype(str).str.strip(), errors='coerce')
        
    # Explode and clean names
    name_series = name_series.str.split(r'[、,，/]').explode()
    standard_df = standard_df.loc[name_series.index] # Align index before assigning new exploded column
    standard_df['name'] = name_series.apply(forensic_clean_text)
    
    if case_insensitive:
        standard_df['name'] = standard_df['name'].str.lower()
        
    standard_df = standard_df[standard_df['name'] != ''].reset_index(drop=True)
    return standard_df

def style_final_table(df):
    """Applies dynamic styling to the final consolidated table."""
    def apply_row_styles(row):
        style = [''] * len(row)
        result = row['比对结果']
        result_idx = df.columns.get_loc('比对结果')
        
        if '仅文件1有' in result:
            style[result_idx] = 'background-color: #FFF3CD' # Yellow
        elif '仅文件2有' in result:
            style[result_idx] = 'background-color: #D4EDDA' # Green
        elif '不一致' in result:
            style[result_idx] = 'background-color: #F8D7DA' # Red

        if '不一致' in result:
            compare_cols = ['入住日期', '离开日期', '房型', '房价']
            for col_base in compare_cols:
                col1_name, col2_name = f'{col_base}_1', f'{col_base}_2'
                if col1_name in df.columns and col2_name in df.columns:
                    val1, val2 = row.get(col1_name), row.get(col2_name)
                    if val1 != val2 and not (pd.isna(val1) and pd.isna(val2)):
                        col1_idx, col2_idx = df.columns.get_loc(col1_name), df.columns.get_loc(col2_name)
                        style[col1_idx] = 'background-color: #FFC7CE'
                        style[col2_idx] = 'background-color: #FFC7CE'
        return style
    return df.style.apply(apply_row_styles, axis=1)

# --- UI Layout ---

st.title("深度比对总览工具 V19.1 🌟")
st.info("稳定版：融合了总览对齐视图与深度细节比对功能，按需比较，结果更智能！")

st.header("第 1 步: 上传文件")
if 'df1' not in st.session_state: st.session_state.df1 = None
if 'df2' not in st.session_state: st.session_state.df2 = None

col1, col2 = st.columns(2)
with col1:
    uploaded_file1 = st.file_uploader("上传名单文件 1", type=['csv', 'xlsx'])
    if uploaded_file1:
        st.session_state.df1 = pd.read_excel(uploaded_file1) if uploaded_file1.name.endswith('xlsx') else pd.read_csv(uploaded_file1)
with col2:
    uploaded_file2 = st.file_uploader("上传名单文件 2", type=['csv', 'xlsx'])
    if uploaded_file2:
        st.session_state.df2 = pd.read_excel(uploaded_file2) if uploaded_file2.name.endswith('xlsx') else pd.read_csv(uploaded_file2)

if st.session_state.df1 is not None and st.session_state.df2 is not None:
    st.header("第 2 步: 选择要比对的列 (姓名必选)")
    mapping = {'file1': {}, 'file2': {}}
    cols1, cols2 = st.columns(2)
    with cols1:
        st.subheader(f"文件 1")
        df1_cols = [None] + list(st.session_state.df1.columns)
        mapping['file1']['name'] = st.selectbox("姓名", df1_cols, key='f1_name')
        mapping['file1']['start_date'] = st.selectbox("入住日期", df1_cols, key='f1_start')
        mapping['file1']['end_date'] = st.selectbox("离开日期", df1_cols, key='f1_end')
        mapping['file1']['room_type'] = st.selectbox("房型", df1_cols, key='f1_room')
        mapping['file1']['price'] = st.selectbox("房价", df1_cols, key='f1_price')
    with cols2:
        st.subheader(f"文件 2")
        df2_cols = [None] + list(st.session_state.df2.columns)
        mapping['file2']['name'] = st.selectbox("姓名", df2_cols, key='f2_name')
        mapping['file2']['start_date'] = st.selectbox("入住日期", df2_cols, key='f2_start')
        mapping['file2']['end_date'] = st.selectbox("离开日期", df2_cols, key='f2_end')
        mapping['file2']['room_type'] = st.selectbox("房型", df2_cols, key='f2_room')
        mapping['file2']['price'] = st.selectbox("房价", df2_cols, key='f2_price')
    
    st.header("第 3 步: 配置与执行")
    room_type_equivalents = {}
    if mapping['file1'].get('room_type') and mapping['file2'].get('room_type'):
        with st.expander("⭐ 功能：统一不同名称的房型 (例如：让'大床房'='King Room')"):
            unique_rooms1 = st.session_state.df1[mapping['file1']['room_type']].dropna().astype(str).unique()
            unique_rooms2 = list(st.session_state.df2[mapping['file2']['room_type']].dropna().astype(str).unique())
            for room1 in unique_rooms1:
                room_type_equivalents[room1] = st.multiselect(f"文件1的“{room1}”等同于:", unique_rooms2, key=f"map_{room1}")

    case_insensitive = st.checkbox("比对姓名时忽略大小写/全半角", True)
    
    if st.button("🚀 开始生成深度比对总览表", type="primary"):
        if not all(mapping['file1'].get(key) for key in ['name', 'start_date', 'end_date']) or \
           not all(mapping['file2'].get(key) for key in ['name', 'start_date', 'end_date']):
            st.error("请确保两边文件的“姓名”、“入住日期”、“离开日期”都已正确选择。")
        else:
            with st.spinner('正在执行深度比对...'):
                st.session_state.df1.sort_values(by=mapping['file1']['name'], inplace=True, ignore_index=True)
                st.session_state.df2.sort_values(by=mapping['file2']['name'], inplace=True, ignore_index=True)
                
                std_df1 = process_and_standardize(st.session_state.df1, mapping['file1'], case_insensitive, room_type_equivalents)
                std_df2 = process_and_standardize(st.session_state.df2, mapping['file2'], case_insensitive)
                
                names1, names2 = set(std_df1['name']), set(std_df2['name'])
                common_names = sorted(list(names1.intersection(names2)))
                only_in_1_names = sorted(list(names1 - names2))
                only_in_2_names = sorted(list(names2 - names1))
                
                consolidated_list = []
                compare_cols_map = {'入住日期': 'start_date', '离开日期': 'end_date', '房型': 'room_type', '房价': 'price'}
                selected_cols = {k: v for k, v in compare_cols_map.items() if mapping['file1'].get(k) and mapping['file2'].get(k)}

                for name in common_names:
                    row1, row2 = std_df1[std_df1['name'] == name].iloc[0], std_df2[std_df2['name'] == name].iloc[0]
                    diffs = []
                    details_row = {'姓名_1': name, '姓名_2': name}
                    for display_name, col_name in selected_cols.items():
                        val1, val2 = row1.get(col_name), row2.get(col_name)
                        details_row[f'{display_name}_1'] = val1
                        details_row[f'{display_name}_2'] = val2
                        if val1 != val2 and not (pd.isna(val1) and pd.isna(val2)):
                            diffs.append(f'{display_name}不一致')
                    details_row['比对结果'] = ', '.join(diffs) if diffs else '一致'
                    consolidated_list.append(details_row)

                for name in only_in_1_names:
                    row1 = std_df1[std_df1['name'] == name].iloc[0]
                    details_row = {'姓名_1': name, '姓名_2': ''}
                    for display_name, col_name in selected_cols.items():
                        details_row[f'{display_name}_1'] = row1.get(col_name)
                        details_row[f'{display_name}_2'] = ''
                    details_row['比对结果'] = '仅文件1有'
                    consolidated_list.append(details_row)

                for name in only_in_2_names:
                    row2 = std_df2[std_df2['name'] == name].iloc[0]
                    details_row = {'姓名_1': '', '姓名_2': name}
                    for display_name, col_name in selected_cols.items():
                        details_row[f'{display_name}_1'] = ''
                        details_row[f'{display_name}_2'] = row2.get(col_name)
                    details_row['比对结果'] = '仅文件2有'
                    consolidated_list.append(details_row)
                
                if not consolidated_list:
                    st.warning("比对完成，但未发现任何可比对的人员。")
                else:
                    final_df = pd.DataFrame(consolidated_list)
                    final_df.insert(0, '序号', range(1, 1 + len(final_df)))
                    st.header("✔️ 比对结果总览表")
                    st.dataframe(style_final_table(final_df), height=(len(final_df) + 1) * 35 + 3)
    
    st.divider()
    st.header("原始数据预览 (点击比对后会按姓名排序)")
    c1, c2 = st.columns(2)
    with c1:
        st.dataframe(st.session_state.df1)
    with c2:
        st.dataframe(st.session_state.df2)
