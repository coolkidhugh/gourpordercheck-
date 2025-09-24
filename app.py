import pandas as pd
import streamlit as st
import re
import unicodedata

st.set_page_config(page_title="总览对齐比对工具", layout="wide")

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

def process_and_get_names(df, name_col):
    """Cleans the name column and returns a clean set of unique names."""
    if not name_col or name_col not in df.columns:
        return set()
    
    names = df[name_col].dropna().astype(str)
    
    # Split names by various delimiters and explode into separate rows
    names = names.str.split(r'[、,，/]').explode()
    
    # Apply forensic cleaning to each name
    names = names.apply(forensic_clean_text)
    
    # Remove any empty strings that might result from splitting
    names = names[names != '']
    
    return set(names)

def style_results(row):
    """Applies color to the '比对结果' column based on its value."""
    val = row['比对结果']
    if '仅文件1有' in val:
        color = '#FFF3CD' # Light Yellow
    elif '仅文件2有' in val:
        color = '#D4EDDA' # Light Green
    else:
        color = ''
    return [f'background-color: {color}' if col == '比对结果' else '' for col in row.index]

# --- UI Layout ---

st.title("智能总览对齐比对工具 V18.0 🎯")
st.info("全新模式！根据您的范例重写，生成单一、对齐的总览结果表，人员有无一目了然。")

st.header("第 1 步: 上传文件")
col1, col2 = st.columns(2)
with col1:
    uploaded_file1 = st.file_uploader("上传名单文件 1", type=['csv', 'xlsx'])
with col2:
    uploaded_file2 = st.file_uploader("上传名单文件 2", type=['csv', 'xlsx'])

if uploaded_file1 and uploaded_file2:
    try:
        df1 = pd.read_excel(uploaded_file1) if uploaded_file1.name.endswith('xlsx') else pd.read_csv(uploaded_file1)
        st.session_state.df1 = df1
        st.session_state.df1_name = uploaded_file1.name
    except Exception as e:
        st.error(f"读取文件1失败: {e}")
        st.stop()
        
    try:
        df2 = pd.read_excel(uploaded_file2) if uploaded_file2.name.endswith('xlsx') else pd.read_csv(uploaded_file2)
        st.session_state.df2 = df2
        st.session_state.df2_name = uploaded_file2.name
    except Exception as e:
        st.error(f"读取文件2失败: {e}")
        st.stop()

    st.success("文件上传成功！请选择姓名列进行比对。")

    st.header("第 2 步: 选择姓名列")
    cols1, cols2 = st.columns(2)
    with cols1:
        st.subheader(f"文件 1: {st.session_state.df1_name}")
        name_col1 = st.selectbox("请选择包含姓名的列", [None] + list(st.session_state.df1.columns), key='name_col1')
    with cols2:
        st.subheader(f"文件 2: {st.session_state.df2_name}")
        name_col2 = st.selectbox("请选择包含姓名的列", [None] + list(st.session_state.df2.columns), key='name_col2')

    if st.button("🚀 开始生成总览对齐表", type="primary"):
        if not name_col1 or not name_col2:
            st.error("请为两个文件都选择包含姓名的列。")
        else:
            with st.spinner('正在清洗数据并生成总览表...'):
                # Get clean sets of names from each file
                names1 = process_and_get_names(st.session_state.df1, name_col1)
                names2 = process_and_get_names(st.session_state.df2, name_col2)
                
                # Perform set operations to find common and unique names
                common_names = sorted(list(names1.intersection(names2)))
                only_in_1_names = sorted(list(names1 - names2))
                only_in_2_names = sorted(list(names2 - names1))
                
                # Build the consolidated list of results
                consolidated_list = []
                
                # Add common names
                for name in common_names:
                    consolidated_list.append({
                        f'文件1 ({st.session_state.df1_name})': name,
                        f'文件2 ({st.session_state.df2_name})': name,
                        '比对结果': '一致'
                    })
                
                # Add names only in file 1
                for name in only_in_1_names:
                    consolidated_list.append({
                        f'文件1 ({st.session_state.df1_name})': name,
                        f'文件2 ({st.session_state.df2_name})': '',
                        '比对结果': '仅文件1有'
                    })

                # Add names only in file 2
                for name in only_in_2_names:
                    consolidated_list.append({
                        f'文件1 ({st.session_state.df1_name})': '',
                        f'文件2 ({st.session_state.df2_name})': name,
                        '比对结果': '仅文件2有'
                    })
                
                if not consolidated_list:
                    st.warning("比对完成，但两个名单中没有找到任何相同或不同的人员。")
                else:
                    # Create and display the final DataFrame
                    final_df = pd.DataFrame(consolidated_list)
                    
                    # Add a serial number column
                    final_df.insert(0, '序号', range(1, 1 + len(final_df)))
                    
                    st.header("✔️ 比对结果总览表")
                    
                    # Apply styling to highlight results
                    styled_df = final_df.style.apply(style_results, axis=1)
                    
                    st.dataframe(styled_df, height=(len(final_df) + 1) * 35 + 3)

    st.divider()
    st.header("原始数据预览")
    c1, c2 = st.columns(2)
    with c1:
        st.caption(f"文件 1: {st.session_state.df1_name}")
        st.dataframe(st.session_state.df1)
    with c2:
        st.caption(f"文件 2: {st.session_state.df2_name}")
        st.dataframe(st.session_state.df2)
