import pandas as pd
import streamlit as st
import re

def find_column(df, keywords):
    """(全能版) 根据关键词在DataFrame中灵活查找列名"""
    # 转换为小写进行匹配，以提高兼容性
    normalized_columns = {col: str(col).lower().replace(' ', '') for col in df.columns}
    
    for keyword in keywords:
        for original_col, normalized_col in normalized_columns.items():
            if keyword in normalized_col:
                return original_col
    return None

def clean_date(series):
    """将日期列转换为仅包含年月日的datetime对象"""
    return pd.to_datetime(series, errors='coerce').dt.date

def process_guest_list(df, name_col):
    """处理可能包含多个姓名的列，将其拆分并展开为多行"""
    if name_col not in df.columns:
        return df
        
    df[name_col] = df[name_col].astype(str).str.strip()
    if df[name_col].str.contains('、|,', na=False).any():
        df[name_col] = df[name_col].str.replace(',', '、')
        df[name_col] = df[name_col].str.split('、')
        df = df.explode(name_col)
        df[name_col] = df[name_col].str.strip()
    return df

def compare_lists(df1, df2):
    """
    V6.0: 对两个文件都采用最灵活的列名识别方式。
    """
    # --- 1. 定义关键词词典 ---
    name_keys = ['姓名', 'name']
    start_date_keys = ['入住', 'checkin', '到达', 'arrival', '抵店']
    end_date_keys = ['退房', 'checkout', '离开', 'departure', '离店']
    room_type_keys = ['房型', '房类', '房间安排', 'roomtype', '房间']
    price_keys = ['房价', '定价', 'price', 'rate']

    # --- 2. 灵活识别文件1的列 ---
    name_col1 = find_column(df1, name_keys)
    start_date_col1 = find_column(df1, start_date_keys)
    end_date_col1 = find_column(df1, end_date_keys)
    room_type_col1 = find_column(df1, room_type_keys)
    price_col1 = find_column(df1, price_keys)

    # --- 3. 灵活识别文件2的列 ---
    name_col2 = find_column(df2, name_keys)
    start_date_col2 = find_column(df2, start_date_keys)
    end_date_col2 = find_column(df2, end_date_keys)
    room_type_col2 = find_column(df2, room_type_keys)
    price_col2 = find_column(df2, price_keys)

    # 检查核心列是否存在
    if not all([name_col1, start_date_col1, end_date_col1]):
        st.error("错误：无法在第一个文件中找到所有核心列（姓名、入住日期、退房日期）。")
        return None
    if not all([name_col2, start_date_col2, end_date_col2]):
        st.error("错误：无法在第二个文件中找到所有核心列（姓名、到达日期、离开日期）。")
        return None

    # --- 4. 数据处理与准备 ---
    df1_processed = process_guest_list(df1.copy(), name_col1)
    df2_processed = process_guest_list(df2.copy(), name_col2)
    
    cols_to_use1 = {name_col1: 'name', start_date_col1: 'start_date', end_date_col1: 'end_date'}
    if room_type_col1: cols_to_use1[room_type_col1] = 'room_type'
    if price_col1: cols_to_use1[price_col1] = 'price'

    cols_to_use2 = {name_col2: 'name', start_date_col2: 'start_date', end_date_col2: 'end_date'}
    if room_type_col2: cols_to_use2[room_type_col2] = 'room_type'
    if price_col2: cols_to_use2[price_col2] = 'price'

    df1_final = df1_processed[list(cols_to_use1.keys())].rename(columns=cols_to_use1)
    df2_final = df2_processed[list(cols_to_use2.keys())].rename(columns=cols_to_use2)

    # 清理数据
    for df in [df1_final, df2_final]:
        df['name'] = df['name'].astype(str).str.strip()
        df['start_date'] = clean_date(df['start_date'])
        df['end_date'] = clean_date(df['end_date'])
        df.dropna(subset=['name', 'start_date', 'end_date'], inplace=True)
        # 清理姓名列，只保留中英文，避免匹配到'/'等无效字符
        df['name'] = df['name'].apply(lambda x: ''.join(re.findall(r'[\u4e00-\u9fa5a-zA-Z]+', x)))
        df.dropna(subset=['name'], inplace=True)
        df = df[df['name'] != '']
    
    # --- 5. 执行最终比较 ---
    merged_df = pd.merge(df1_final, df2_final, on='name', suffixes=('_file1', '_file2'), how='outer')
    
    # (分类和返回逻辑不变)
    mismatch_filter = ((merged_df['start_date_file1'] != merged_df['start_date_file2']) | (merged_df['end_date_file1'] != merged_df['end_date_file2']))
    date_mismatch = merged_df[mismatch_filter.fillna(False)].dropna(subset=['start_date_file1', 'start_date_file2'])
    fully_matched_filter = ((merged_df['start_date_file1'] == merged_df['start_date_file2']) & (merged_df['end_date_file1'] == merged_df['end_date_file2']))
    fully_matched = merged_df[fully_matched_filter.fillna(False)].dropna(subset=['start_date_file1', 'start_date_file2'])
    in_file1_not_in_file2 = merged_df[merged_df['start_date_file2'].isnull()]
    in_file2_not_in_file1 = merged_df[merged_df['start_date_file1'].isnull()]
    
    return {
        "mismatch": date_mismatch, 
        "in_file1_only": in_file1_not_in_file2, 
        "in_file2_only": in_file2_not_in_file1, 
        "fully_matched": fully_matched
    }

# --- Streamlit App 界面 ---
st.set_page_config(page_title="全能名单比对工具", layout="wide")
st.title("全能名单比对工具 📄 V6.0 (最终版)")

st.info("""
**使用说明:**
1.  分别上传任意两份需要比对的名单文件（Excel 或 CSV）。
2.  **超强兼容性**: 
    - **不区分文件类型**：您可以在任意一边上传销售名单或酒店名单。
    - **自动识别列表头**：能识别如 `姓名`, `入住/抵店`, `退房/离店`, `房型/房间`, `房价/Rate` 等多种中英文表头。
    - **自动处理同住人**：能自动拆分一个单元格内的多个名字（如 `张三、李四`）。
3.  点击“开始比对”，下方将显示详细结果。
""")

col1, col2 = st.columns(2)
with col1:
    uploaded_file1 = st.file_uploader("上传名单文件 1", type=['csv', 'xlsx'])
with col2:
    uploaded_file2 = st.file_uploader("上传名单文件 2", type=['csv', 'xlsx'])

if st.button("🚀 开始比对"):
    if uploaded_file1 and uploaded_file2:
        try:
            df1 = pd.read_excel(uploaded_file1, engine='openpyxl') if uploaded_file1.name.endswith('xlsx') else pd.read_csv(uploaded_file1)
            df2 = pd.read_excel(uploaded_file2, engine='openpyxl') if uploaded_file2.name.endswith('xlsx') else pd.read_csv(uploaded_file2)
            results = compare_lists(df1, df2)
            
            if results:
                st.success("比对完成！结果如下：")
                
                # --- 结果展示 ---
                st.header("1. 信息不一致的名单")
                if not results["mismatch"].empty:
                    st.dataframe(results["mismatch"], use_container_width=True)
                else:
                    st.write("✅ 两份名单中共同存在的人员，信息均一致。")

                st.header(f"2. 仅存在于名单 1 ({uploaded_file1.name}) 的人员")
                if not results["in_file1_only"].empty:
                    st.warning(f"共发现 {len(results['in_file1_only'])} 人，请关注！")
                    with st.expander("点击查看详细名单"):
                        st.dataframe(results["in_file1_only"], use_container_width=True)
                else:
                    st.write("✅ 名单1中的所有人员都在名单2中。")

                st.header(f"3. 仅存在于名单 2 ({uploaded_file2.name}) 的人员")
                if not results["in_file2_only"].empty:
                    st.info(f"共发现 {len(results['in_file2_only'])} 人，请确认。")
                    with st.expander("点击查看详细名单"):
                        st.dataframe(results["in_file2_only"], use_container_width=True)
                else:
                    st.write("✅ 名单2中的所有人员都在名单1中。")

                st.header("4. 信息完全一致的名单")
                if not results["fully_matched"].empty:
                     with st.expander(f"共 {len(results['fully_matched'])} 人信息完全一致，点击查看"):
                        st.dataframe(results["fully_matched"], use_container_width=True)
                else:
                    st.write("没有找到信息完全一致的人员。")

        except Exception as e:
            st.error(f"处理文件时发生错误: {e}")
            st.error("请检查文件格式是否正确，并确保核心的“姓名”和“日期”列数据有效。")
    else:
        st.warning("请确保两个文件都已上传。")
