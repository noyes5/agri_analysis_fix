import requests
import pandas as pd
import json
import os
from datetime import datetime, timedelta

def get_weather_data(api_key, start_date, end_date, station_id="108"):
    url = 'http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList'
    
    params = {
        'serviceKey': api_key,
        'pageNo': '1',
        'numOfRows': '999',
        'dataType': 'JSON',
        'dataCd': 'ASOS',
        'dateCd': 'DAY',
        'startDt': start_date,
        'endDt': end_date,
        'stnIds': station_id
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if data['response']['header']['resultCode'] == '00':
            items = data['response']['body']['items']['item']
            df = pd.DataFrame(items)
            
            # [수정] FastAPI schemas.py의 변수명과 일치시킵니다.
            # 원본(ASOS) -> 우리 서버(FastAPI)
            rename_map = {
                'tm': 'date',
                'avgTa': 'avg_ta',
                'maxTa': 'max_ta',
                'minTa': 'min_ta',
                'sumRn': 'sum_rn'
            }
            
            # 필요한 컬럼만 추출하고 이름 변경
            df = df[list(rename_map.keys())].copy()
            df.rename(columns=rename_map, inplace=True)
            
            # [전처리] 
            # 1. 강수량 공백은 0.0으로 채우기
            df['sum_rn'] = df['sum_rn'].replace('', '0.0')
            
            # 2. 숫자형 데이터 타입 변환 (문자열 -> 숫자)
            float_cols = ['avg_ta', 'max_ta', 'min_ta', 'sum_rn']
            for col in float_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            
            return df
            
        else:
            print(f"API 응답 에러: {data['response']['header']['resultMsg']}")
            return None
            
    except Exception as e:
        print(f"데이터 수집 중 오류가 발생했습니다: {e}")
        return None
    
def get_weather_forecast(api_key, nx="60", ny="127"):
    """
    기상청 단기예보 API를 사용하여 향후 3일간의 날씨 예보를 가져옵니다.
    (기본 좌표: 서울 60, 127)
    """
    url = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
    
    # [수정] 현재 시간 기준으로 가장 최근 발표된 base_time 찾기
    now = datetime.now()
    if now.hour < 2:
        # 새벽 2시 전이라면 어제 밤 23시 예보를 가져옴
        base_date = (now - timedelta(days=1)).strftime('%Y%m%d')
        base_time = "2300"
    else:
        # 현재 시간보다 직전의 예보 시간 계산 (예: 10시면 0800 사용)
        base_date = now.strftime('%Y%m%d')
        # 3시간 간격(2, 5, 8...)이므로 계산 로직 적용
        target_hour = (now.hour - 2) // 3 * 3 + 2
        base_time = f"{target_hour:02d}00"

    print(f"📡 {base_date} {base_time} 기준 예보 데이터 조회 중...")

    params = {
        'serviceKey': api_key,
        'pageNo': '1',
        'numOfRows': '1000',
        'dataType': 'JSON',
        'base_date': base_date,
        'base_time': base_time,
        'nx': nx,
        'ny': ny
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if data['response']['header']['resultCode'] == '00':
            items = data['response']['body']['items']['item']
            df = pd.DataFrame(items)
            
            # 1. 필요한 항목만 필터링 (TMP: 기온, POP: 강수확률, SKY: 하늘상태)
            df = df[df['category'].isin(['TMP', 'POP', 'SKY'])]
            
            # 2. 서버 규격(schemas.py)에 맞게 컬럼명 변경
            rename_map = {
                'fcstDate': 'date',
                'fcstTime': 'fcst_time',
                'category': 'category',
                'fcstValue': 'fcst_value'
            }
            df.rename(columns=rename_map, inplace=True)

            # 3. 추가 정보 및 타입 변환
            df['reg_date'] = base_date
            df['date'] = df['date'].apply(lambda x: f"{x[:4]}-{x[4:6]}-{x[6:]}")
            df['reg_date'] = df['reg_date'].apply(lambda x: f"{x[:4]}-{x[4:6]}-{x[6:]}")
            df['fcst_value'] = pd.to_numeric(df['fcst_value'], errors='coerce').fillna(0.0)
            
            # 필요한 컬럼만 최종 추출
            return df[['date', 'fcst_time', 'category', 'fcst_value', 'reg_date']]
            
        else:
            print(f"예보 API 응답 에러: {data['response']['header']['resultMsg']}")
            return None
            
    except Exception as e:
        print(f"예보 수집 중 오류 발생: {e}")
        return None

def get_region_weather(api_key, start_date, end_date, station_id):
    """
    [PR3] 산지 관측소별 ASOS 일자료 수집
    - 기존 get_weather_data는 서울(108) 한 곳만 수집하고 지점 정보를 버렸음
    - 여기서는 지점번호·지점명과 일조시간(sumSsHr)을 함께 저장
      (토마토는 시설재배가 많아 기온보다 일조량 영향이 클 수 있음)
    """
    url = 'http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList'
    params = {
        'serviceKey': api_key,
        'pageNo': '1',
        'numOfRows': '999',
        'dataType': 'JSON',
        'dataCd': 'ASOS',
        'dateCd': 'DAY',
        'startDt': start_date,
        'endDt': end_date,
        'stnIds': station_id
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()

        if data['response']['header']['resultCode'] != '00':
            print(f"API 응답 에러: {data['response']['header']['resultMsg']}")
            return None

        items = data['response']['body']['items']['item']
        df = pd.DataFrame(items)

        rename_map = {
            'tm': 'date',
            'stnId': 'station_id',
            'stnNm': 'station_name',
            'avgTa': 'avg_ta',
            'maxTa': 'max_ta',
            'minTa': 'min_ta',
            'sumRn': 'sum_rn',
            'sumSsHr': 'sum_ss_hr',
        }
        for col in rename_map:
            if col not in df.columns:
                df[col] = ''
        df = df[list(rename_map.keys())].rename(columns=rename_map)

        # 강수량·일조시간 공백은 0으로, 기온 공백은 결측(NaN → None)으로 유지
        for col in ['sum_rn', 'sum_ss_hr']:
            df[col] = pd.to_numeric(df[col].replace('', '0'), errors='coerce').fillna(0.0)
        for col in ['avg_ta', 'max_ta', 'min_ta']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df['station_id'] = df['station_id'].astype(str)

        # JSON 전송 시 NaN은 허용되지 않으므로 None으로 변환
        df = df.astype(object).where(pd.notna(df), None)
        return df

    except Exception as e:
        print(f"[{station_id}] 데이터 수집 중 오류: {e}")
        return None

# API 키를 외부에서 쉽게 가져올 수 있도록 변수 노출
current_dir = os.path.dirname(os.path.abspath(__file__))
secret_path = os.path.join(current_dir, '..', 'secret.json')
with open(secret_path, 'r', encoding='utf-8') as file:
    secrets = json.load(file)
    MY_WEATHER_KEY = secrets["WEATHER_API_KEY"]