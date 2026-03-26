import pandas as pd

file_path = r'C:\Users\임현수\Downloads\학교별 교육편제단위 정보_20250221기준.xlsx'
try:
    df = pd.read_excel(file_path, skiprows=4)
    status_values = df['학과상태'].unique().tolist()
    degree_values = df['학위과정'].unique().tolist()
    category_values = df['대학구분'].unique().tolist()
    
    print(f"Status Values: {status_values}")
    print(f"Degree Values: {degree_values}")
    print(f"Category Values: {category_values}")
    
    # Check counts for filtering
    print("\nFiltering Stats:")
    print(f"Total rows: {len(df)}")
    active_undergrad = df[
        (~df['학과상태'].str.contains('폐지', na=False)) &
        (df['학위과정'].isin(['학사', '전문학사', '학석사통합'])) &
        (df['대학구분'].isin(['대학', '전문대학']))
    ]
    print(f"Active Undergraduate rows: {len(active_undergrad)}")
    print(f"Unique Universities: {active_undergrad['학교명'].nunique()}")
    print(f"Unique Majors: {active_undergrad['학부·과(전공)명'].nunique()}")

except Exception as e:
    print(f"Error: {e}")
