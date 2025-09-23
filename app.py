import pandas as pd
import streamlit as st
import re

def find_flexible_column(df, keywords):
    """(用于销售名单) 根据关键词在DataFrame中灵活查找列名"""
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

def compare_lists(sales_df, hotel_df):
    """
    V5.0: 精确匹配酒店名单列，灵活匹配销售名单列。
    """
    
    # --- 1. 灵活识别销售名单列 ---
    sales_name_keys = ['姓名', 'name']
    sales_start_keys = ['入住', 'checkin', '到达', 'arrival', '抵店']
    sales_end_keys = ['退房', 'checkout', '离开', 'departure', '离店']
    sales_room_type_keys = ['房型', '房类', '房间安排', 'roomtype', '房间']
    sales_price_keys = ['房价', '定价', 'price']
    
    sales_name_col = find_flexible_column(sales_df, sales_name_keys)
    sales_start_col = find_flexible_column(sales_df, sales_start_keys)
    sales_end_col = find_flexible_column(sales_df, sales_end_keys)
    sales_room_type_col = find_flexible_column(sales_df, sales_room_type_keys)
    sales_price_col = find_flexible_column(sales_df, sales_price_keys)

    if not all([sales_name_col, sales_start_col, sales_end_col]):
        st.error("错误：无法在'销售名单'中找到所有核心列（姓名、入住日期、退房日期）。")
        return None

    # --- 2. 精确匹配酒店系统列 ---
    hotel_cols_map = {
        'Name': 'name', 'Arrival': 'start_date', 'Departure': 'end_date',
        'Room Type': 'room_type', 'Rate': 'price'
    }
    # 检查酒店文件的必需列是否存在
    required_hotel_cols = ['Name', 'Arrival', 'Departure']
    for col in required_hotel_cols:
        if col not in hotel_df.columns:
            st.error(f"错误：'酒店系统名单'中缺少必需的列: '{col}'。请确认上传的是正确的酒店系统导出文件。")
            return None
    
    # --- 3. 数据处理与拆分 ---
    sales_processed = process_guest_list(sales_df.copy(), sales_name_col)
    hotel_processed = process_guest_list(hotel_df.copy(), 'Name')

    # --- 4. 数据准备 ---
    cols_to_use_sales = {sales_name_col: 'name', sales_start_col: 'start_date', sales_end_col: 'end_date'}
    if sales_room_type_col: cols_to_use_sales[sales_room_type_col] = 'room_type'
    if sales_price_col: cols_to_use_sales[sales_price_col] = 'price'
    
    # 只选择酒店文件中存在的列
    cols_to_use_hotel = {k: v for k, v in hotel_cols_map.items() if k in hotel_processed.columns}

    sales_final = sales_processed[list(cols_to_use_sales.keys())].rename(columns=cols_to_use_sales)
    hotel_final = hotel_processed[list(cols_to_use_hotel.keys())].rename(columns=cols_to_use_hotel)

    # 清理数据
    for df in [sales_final, hotel_final]:
        df['name'] = df['name'].astype(str).str.strip()
        df['start_date'] = clean_date(df['start_date'])
        df['end_date'] = clean_date(df['end_date'])
        df.dropna(subset=['name', 'start_date', 'end_date'], inplace=True)
        df['name'] = df['name'].apply(lambda x: ''.join(re.findall(r'[\u4e00-\u9fa5a-zA-Z]+', x)))
        df.dropna(subset=['name'], inplace=True)
        df = df[df['name'] != '']
    
    # --- 5. 执行比较 ---
    merged_df = pd.merge(sales_final, hotel_final, on='name', suffixes=('_sales', '_hotel'), how='outer')
    
    # (后续的分类和返回逻辑与之前版本相同)
    date_mismatch_filter = ((merged_df['start_date_sales'] != merged_df['start_date_hotel']) | (merged_df['end_date_sales'] != merged_df['end_date_hotel']))
    date_mismatch = merged_df[date_mismatch_filter.fillna(False)].dropna(subset=['start_date_sales', 'start_date_hotel'])
    fully_matched_filter = ((merged_df['start_date_sales'] == merged_df['start_date_hotel']) & (merged_df['end_date_sales'] == merged_df['end_date_hotel']))
    fully_matched = merged_df[fully_matched_filter.fillna(False)].dropna(subset=['start_date_sales', 'start_date_hotel'])
    in_sales_not_in_hotel = merged_df[merged_df['start_date_hotel'].isnull()]
    in_hotel_not_in_sales = merged_df[merged_df['start_date_sales'].isnull()]
    return {"date_mismatch": date_mismatch, "in_sales_only": in_sales_not_in_hotel, "in_hotel_only": in_hotel_not_in_sales, "fully_matched": fully_matched}

# --- Streamlit App 界面 ---
st.set_page_config(page_title="智能名单比对工具", layout="wide")
st.title("智能名单比对工具 📄 V5.0")

st.info("""
**使用说明:**
1.  **上传您的销售/自制名单**: 此文件格式灵活，程序会自动识别 `姓名`, `入住/抵店`, `退房/离店`, `房型/房间` 等列。
2.  **上传酒店系统导出的名单**: 程序会精确查找 `Name`, `Arrival`, `Departure`, `Room Type`, `Rate` 等固定列。
3.  **智能处理**: 工具会自动处理一个单元格内包含多个名字（如 `张三、李四`）的情况。
4.  点击“开始比对”，下方将显示详细结果。
""")

col1, col2 = st.columns(2)
with col1:
    uploaded_file1 = st.file_uploader("1. 上传销售名单 / 自制名单", type=['csv', 'xlsx'])
with col2:
    uploaded_file2 = st.file_uploader("2. 上传酒店系统导出的名单", type=['csv', 'xlsx'])

if st.button("🚀 开始比对"):
    if uploaded_file1 and uploaded_file2:
        try:
            df1 = pd.read_excel(uploaded_file1, engine='openpyxl') if uploaded_file1.name.endswith('xlsx') else pd.read_csv(uploaded_file1)
            df2 = pd.read_excel(uploaded_file2, engine='openpyxl') if uploaded_file2.name.endswith('xlsx') else pd.read_csv(uploaded_file2)
            results = compare_lists(df1, df2)
            if results:
                st.success("比对完成！结果如下：")
                # (显示逻辑与之前版本完全相同)
                mismatch_cols = ['name', 'start_date_sales', 'end_date_sales']
                if 'room_type_sales' in results['date_mismatch'].columns: mismatch_cols.append('room_type_sales')
                if 'price_sales' in results['date_mismatch'].columns: mismatch_cols.append('price_sales')
                mismatch_cols.extend(['start_date_hotel', 'end_date_hotel'])
                if 'room_type_hotel' in results['date_mismatch'].columns: mismatch_cols.append('room_type_hotel')
                if 'price_hotel' in results['date_mismatch'].columns: mismatch_cols.append('price_hotel')

                sales_only_cols = ['name', 'start_date_sales', 'end_date_sales']
                if 'room_type_sales' in results['in_sales_only'].columns: sales_only_cols.append('room_type_sales')
                if 'price_sales' in results['in_sales_only'].columns: sales_only_cols.append('price_sales')
                
                hotel_only_cols = ['name', 'start_date_hotel', 'end_date_hotel']
                if 'room_type_hotel' in results['in_hotel_only'].columns: hotel_only_cols.append('room_type_hotel')
                if 'price_hotel' in results['in_hotel_only'].columns: hotel_only_cols.append('price_hotel')
                
                matched_cols = ['name', 'start_date_sales', 'end_date_sales']
                if 'room_type_sales' in results['fully_matched'].columns: matched_cols.append('room_type_sales')
                if 'price_hotel' in results['fully_matched'].columns : matched_cols.append('price_hotel')

                st.header("1. 信息不一致的名单")
                if not results["date_mismatch"].empty:
                    st.dataframe(results["date_mismatch"][mismatch_cols].rename(columns={
                        'name': '姓名', 'start_date_sales': '销售-入住', 'end_date_sales': '销售-退房', 
                        'room_type_sales': '销售-房型', 'price_sales': '销售-价格',
                        'start_date_hotel': '酒店-到达', 'end_date_hotel': '酒店-离开',
                        'room_type_hotel': '酒店-房型', 'price_hotel': '酒店-价格'
                    }), use_container_width=True)
                else:
                    st.write("✅ 两份名单中共同存在的人员，信息均一致。")
                st.header("2. 销售名单中存在但酒店名单中缺失的人员")
                if not results["in_sales_only"].empty:
                    st.warning(f"共发现 {len(results['in_sales_only'])} 人缺失预订，请重点关注！")
                    with st.expander("点击查看详细名单"):
                        st.dataframe(results["in_sales_only"][sales_only_cols].rename(columns={'name': '姓名', 'start_date_sales': '入住日期', 'end_date_sales': '退房日期','room_type_sales': '房间安排', 'price_sales': '价格'}), use_container_width=True)
                else:
                    st.write("✅ 所有销售名单上的人员都在酒店预订名单中。")
                st.header("3. 酒店名单中存在但销售名单中缺失的人员")
                if not results["in_hotel_only"].empty:
                    st.info(f"共发现 {len(results['in_hotel_only'])} 人不在销售名单中，请确认预订是否有效。")
                    with st.expander("点击查看详细名单"):
                        st.dataframe(results["in_hotel_only"][hotel_only_cols].rename(columns={'name': '姓名', 'start_date_hotel': '到达日期', 'end_date_hotel': '离开日期','room_type_hotel': '房型', 'price_hotel': '定价'}), use_container_width=True)
                else:
                    st.write("✅ 酒店预订名单上的人员都在销售名单中。")
                st.header("4. 信息完全一致的名单")
                if not results["fully_matched"].empty:
                     with st.expander(f"共 {len(results['fully_matched'])} 人信息完全一致，点击查看"):
                        st.dataframe(results["fully_matched"][matched_cols].rename(columns={'name': '姓名', 'start_date_sales': '入住日期', 'end_date_sales': '退房日期','room_type_sales': '房型', 'price_hotel': '价格'}), use_container_width=True)
                else:
                    st.write("没有找到信息完全一致的人员。")
        except Exception as e:
            st.error(f"处理文件时发生错误: {e}")
            st.error("请检查文件格式是否正确，特别是日期和姓名列。")
    else:
        st.warning("请确保两个文件都已上传。")
