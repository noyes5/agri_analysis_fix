import pandas as pd
import numpy as np
import requests
import os

# 설정
BASE_URL = "http://127.0.0.1:8000/api/v1"

# [PR1]  분석 기준 등급
# KAMIS의 등급은 수집 단계에서 location 컬럼에 저장되어 있음
TARGET_GRADE = "상품"



def fetch_data(endpoint):
    """FastAPI 서버에서 데이터를 가져와 DataFrame으로 변환"""
    try:
        response = requests.get(f"{BASE_URL}/{endpoint}")
        response.raise_for_status()
        return pd.DataFrame(response.json())
    except Exception as e:
        print(f"❌ {endpoint} 호출 중 오류 발생: {e}")
        return pd.DataFrame()

def process_and_save_data(target_item="토마토", target_grade=TARGET_GRADE):
    print(f"🔄 [{target_item} / {target_grade}] 데이터 통합 및 정제 시작...")

    # 1. 데이터 가져오기
    weather_df = fetch_data("weather-history")
    price_df = fetch_data("price")

    if weather_df.empty or price_df.empty:
        print("⚠️ 통합할 데이터가 부족합니다. DB를 확인해주세요.")
        return

    # 2. 날짜 형식 통일
    weather_df['date'] = pd.to_datetime(weather_df['date']).dt.strftime('%Y-%m-%d')
    price_df['date'] = pd.to_datetime(price_df['date']).dt.strftime('%Y-%m-%d')

    # 3. 가격 데이터 필터링: 품목 + 등급
    # [PR1] 기존에는 품목명만 걸러서 상품·중품이 하루 2행씩 섞였음
    #    -> price_lag_1(어제 가격)이 '같은 날 다른 등급 가격'이 되는 문제
    filtered_price = price_df[
        (price_df['item_name'] == target_item) &
        (price_df['location'] == target_grade)
    ].copy()

    if filtered_price.empty:
        grades = price_df.loc[price_df['item_name'] == target_item, 'location'].unique()
        print(f"⚠️ DB에 '{target_item}' / {target_grade}' 데이터가 없습니다. (등급 목록: {grades})")
        return

    # [PR1] 0원은 '가격 0'이 아니라 '가격 없음'(KAMIS의 '-')이므로 결측으로 되돌림
    filtered_price['price'] = filtered_price['price'].replace(0, np.nan)

    # [PR1] 하루 1행 보장 (중복 수집 대비)
    filtered_price = filtered_price.drop_duplicates(subset=['date'], keep='last')

    cols = ['date', 'price', 'item_name']
    if 'unit' in filtered_price.columns:
        cols.append('unit')

    # 4. 데이터 병합: 날씨(매일) 기준 Left Join
    final_df = pd.merge(
        weather_df[['date', 'avg_ta', 'max_ta', 'min_ta', 'sum_rn']], 
        filtered_price[cols], 
        on='date', 
        how='left'
    )

    # 5. 정제 및 결측치 처리
    final_df = final_df.sort_values('date').reset_index(drop=True)
    
    # 비 안온 날 0처리
    final_df['sum_rn'] = final_df['sum_rn'].fillna(0.0)

    # [PR1] 실제로 시장이 열려 가격이 집계된 날인지 표시
    final_df['is_trading_day'] = final_df['price'].notna().astype(int)

    # 품목명·단위는 채워도 무방
    final_df['item_name'] = final_df['item_name'].ffill().bfill()
    if 'unit' in final_df.columns:
        final_df['unit'] = final_df['unit'].ffill().bfill()

    # [PR1] 가격은 채우지 않고, 거래일만 남김
    # 주말·공휴일을 직전 가격으로 채우면 '어제 가격 = 오늘 가격'인 가짜 정답이 생겨
    # 모델 성능이 실제보다 좋아보이게 됨
    before = len(final_df)
    final_df = final_df[final_df['is_trading_day'] == 1].drop(columns='is_trading_day')
    final_df = final_df.reset_index(drop=True)

    # 6. 결과 저장
    os.makedirs('analytics/data', exist_ok=True)
    save_path = f'analytics/data/{target_item}_integrated_data.csv'
    final_df.to_csv(save_path, index=False, encoding='utf-8-sig')

    print(f"✅ {target_item} 통합 완료! (전체 {before}일 중 거래일 {len(final_df)}일)")
    print(f"📂 저장 경로: {save_path}")
    
    return final_df

if __name__ == "__main__":
    process_and_save_data(target_item="토마토")