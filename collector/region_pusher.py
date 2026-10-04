"""
[PR3] 산지 관측소 날씨 수집 → FastAPI 허브로 전송

실행 위치: collector 폴더 (기존 init_pusher.py와 동일)
    python region_pusher.py
"""
import time
import requests
from weather_api import get_region_weather, MY_WEATHER_KEY

INGEST_URL = "http://127.0.0.1:8000/api/v1/ingest/weather-region"

# 관측 지점 (기상청 ASOS 지점번호)
# 토마토는 계절별로 주산지가 바뀜 → 출하 시기가 다른 두 산지 + 비교용 소비지
STATIONS = {
    "108": "서울(소비지, 기존 분석 기준)",
    "236": "부여(충남, 주로 겨울~봄 출하)",
    "101": "춘천(강원, 주로 여름~가을 출하)",
}

# 가격 데이터 기간에 맞춤 (DB 가격: 2021-03-01 ~ 2026-04)
START_YEAR, END_YEAR = 2021, 2026
START_DATE_2021 = "20210301"
END_DATE_LAST = "20260408"


def push(df):
    payload = df.to_dict(orient='records')
    res = requests.post(INGEST_URL, json=payload)
    if res.status_code == 200:
        body = res.json()
        print(f"    ✅ 저장 {body['inserted']}건 / 갱신 {body['updated']}건")
    else:
        print(f"    ❌ 전송 실패({res.status_code}): {res.text}")


def run():
    for station_id, label in STATIONS.items():
        print(f"\n📍 {station_id} {label}")
        for year in range(START_YEAR, END_YEAR + 1):
            start = START_DATE_2021 if year == START_YEAR else f"{year}0101"
            end = END_DATE_LAST if year == END_YEAR else f"{year}1231"

            df = get_region_weather(MY_WEATHER_KEY, start, end, station_id)
            if df is None or df.empty:
                print(f"  -> {year}년: 데이터 없음")
                continue

            # 지점번호가 엉뚱한 곳이면 여기서 바로 드러나도록 지점명 출력
            name = df['station_name'].iloc[0]
            print(f"  -> {year}년 ({start}~{end}) 지점명: {name}, {len(df)}일")
            push(df)
            time.sleep(1)

    print("\n✨ 산지 날씨 수집 완료")


if __name__ == "__main__":
    run()