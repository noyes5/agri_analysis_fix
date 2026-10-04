"""
[PR3] 산지 날씨 → 몇 달 뒤 가격 시차 분석

질문: "산지 날씨가 나빴던 달이 있으면, 몇 달 뒤 가격이 평소보다 올랐는가?"

실행 위치: 프로젝트 최상위 폴더 (FastAPI 허브가 켜져 있어야 함)
    python analytics/lag_analysis.py
선행 조건: processor.py 실행 완료, region_pusher.py로 산지 날씨 수집 완료
"""
import os
import requests
import numpy as np
import pandas as pd
from scipy.stats import pearsonr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

BASE_URL = "http://127.0.0.1:8000/api/v1"
MAX_LAG = 6  # 0~6개월 뒤까지 확인

WEATHER_VARS = {
    "avg_ta": ("평균기온", "mean"),
    "min_ta": ("최저기온", "mean"),
    "sum_rn": ("강수량", "sum"),
    "sum_ss_hr": ("일조시간", "sum"),
}


def set_korean_font():
    """윈도우/맥/리눅스에서 쓸 수 있는 한글 폰트를 찾아 차트에 적용"""
    installed = {f.name for f in font_manager.fontManager.ttflist}
    candidates = ["Malgun Gothic", "AppleGothic", "NanumGothic"]
    candidates += sorted(n for n in installed if "CJK" in n)  # 리눅스 등 기타 환경
    for name in candidates:
        if name in installed:
            plt.rcParams["font.family"] = name
            break
    plt.rcParams["axes.unicode_minus"] = False


def load_monthly_price(target_item):
    """processor.py 결과(상품 등급, 거래일만)를 월평균 가격으로 변환"""
    path = f"analytics/data/{target_item}_integrated_data.csv"
    df = pd.read_csv(path, parse_dates=["date"])
    monthly = df.set_index("date")["price"].resample("MS").mean()
    return monthly.rename("price")


def load_monthly_weather():
    """FastAPI 허브에서 산지 날씨를 받아 지점별 월 단위로 집계"""
    res = requests.get(f"{BASE_URL}/weather-region")
    res.raise_for_status()
    df = pd.DataFrame(res.json())
    if df.empty:
        raise RuntimeError("산지 날씨가 없습니다. collector/region_pusher.py를 먼저 실행하세요.")

    df["date"] = pd.to_datetime(df["date"])
    agg = {col: how for col, (_, how) in WEATHER_VARS.items()}
    monthly = (
        df.set_index("date")
          .groupby(["station_id", "station_name"])
          .resample("MS")
          .agg(agg)
          .reset_index()
    )
    return monthly


def to_anomaly(series):
    """
    [PR3-1] 추세 + 계절성 제거
    1) 추세 제거: 5년 동안 꾸준히 오른 부분(물가 상승, 온난화)을 직선으로 빼냄
       → 안 빼면 '최근일수록 덥고, 최근일수록 비싸다'가 날씨 효과처럼 보임
    2) 계절성 제거: 같은 달의 평균과의 차이
       → 안 빼면 '여름엔 덥고 여름엔 토마토가 싸다' 같은 계절 패턴이 섞임
    """
    t = np.arange(len(series))
    mask = series.notna().values
    slope, intercept = np.polyfit(t[mask], series.values[mask], 1)
    detrended = series - (slope * t + intercept)
    return detrended - detrended.groupby(series.index.month).transform("mean")


def run(target_item="토마토"):
    set_korean_font()
    price = load_monthly_price(target_item)
    weather = load_monthly_weather()

    # 가격: 로그를 취해 '몇 % 차이'로 해석되도록 한 뒤 추세·계절성 제거
    price_anom = to_anomaly(np.log(price)) * 100

    rows = []
    for (station_id, station_name), w in weather.groupby(["station_id", "station_name"]):
        w = w.set_index("date").reindex(price.index)
        for col, (label, _) in WEATHER_VARS.items():
            w_anom = to_anomaly(w[col])
            for lag in range(MAX_LAG + 1):
                # lag개월 전 날씨 vs 이번 달 가격
                pair = pd.concat([w_anom.shift(lag), price_anom], axis=1).dropna()
                if len(pair) < 12:
                    continue
                r, p = pearsonr(pair.iloc[:, 0], pair.iloc[:, 1])
                rows.append({
                    "지점": f"{station_name}({station_id})",
                    "변수": label,
                    "시차(개월)": lag,
                    "상관계수": round(r, 3),
                    "p값": round(p, 4),
                    "표본(개월)": len(pair),
                })

    result = pd.DataFrame(rows)
    os.makedirs("analytics/data", exist_ok=True)
    result.to_csv(f"analytics/data/{target_item}_lag_analysis.csv", index=False, encoding="utf-8-sig")

    # 1) 지점·변수별로 상관이 가장 강했던 시차
    best = result.loc[result.groupby(["지점", "변수"])["상관계수"].apply(lambda s: s.abs().idxmax())]
    best = best.sort_values("상관계수", key=abs, ascending=False)
    best["유의(p<0.05)"] = np.where(best["p값"] < 0.05, "O", "")

    print(f"\n📊 [{target_item}] 날씨 이상치 → n개월 뒤 가격 이상치 상관 (지점·변수별 최강 시차)")
    print("   상관계수 + : 그 날씨가 평소보다 높을수록 n개월 뒤 가격도 평소보다 높음")
    print(best.to_string(index=False))

    # 2) 히트맵: 행=지점·변수, 열=시차
    pivot = result.pivot_table(index=["지점", "변수"], columns="시차(개월)", values="상관계수")
    fig, ax = plt.subplots(figsize=(9, 0.45 * len(pivot) + 1.5))
    im = ax.imshow(pivot.values, cmap="RdBu_r", vmin=-0.6, vmax=0.6, aspect="auto")
    ax.set_xticks(range(pivot.shape[1]), [f"{c}개월" for c in pivot.columns])
    ax.set_yticks(range(pivot.shape[0]), [f"{a} · {b}" for a, b in pivot.index])
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            v = pivot.values[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=8)
    ax.set_title(f"{target_item}: 날씨 이상치 → n개월 뒤 가격 이상치 상관계수")
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    chart_path = f"analytics/data/{target_item}_lag_heatmap.png"
    fig.savefig(chart_path, dpi=150)

    print(f"\n✅ 결과 저장: analytics/data/{target_item}_lag_analysis.csv")
    print(f"✅ 히트맵 저장: {chart_path}")
    print("\n⚠️ 표본이 약 60개월이라, 상관계수 0.25 안팎은 우연일 수 있음 (p값 함께 확인)")
    return result


if __name__ == "__main__":
    run(target_item="토마토")