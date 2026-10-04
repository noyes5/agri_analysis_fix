import pandas as pd
import numpy as np
import joblib
import os

# 모델 라이브러리
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor

# 평가 지표
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

def evaluate(name, y_true, y_pred):
    """공통 평가 지표 계산"""
    return {
        "Model": name,
        "MAE": round(mean_absolute_error(y_true, y_pred), 2),
        "RMSE": round(np.sqrt(mean_squared_error(y_true, y_pred)), 2),
        "R2_Score": round(r2_score(y_true, y_pred), 4),
    }


def train_model(target_item="토마토"):
    file_path = f'analytics/data/{target_item}_features.csv'
    if not os.path.exists(file_path):
        print(f"❌ 학습용 데이터 파일을 찾을 수 없습니다: {file_path}")
        return

    # 1. 데이터 로드 및 학습 변수 설정
    df = pd.read_csv(file_path)
    
    # AI 학습에 사용할 특성들
    features = [
        'avg_ta', 'max_ta', 'min_ta', 'sum_rn', 
        'month', 'day_of_week', 'is_weekend', 
        'price_lag_1', 'price_lag_7', 'price_rolling_7', 
        'temp_rolling_7', 'rain_sum_3d'
    ]
    
    X = df[features]
    y = df['price']

    # 시계열 데이터이므로 shuffle=False로 설정하여 과거로 학습하고 미래를 테스트
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

    # 2. [PR2] 베이스라인: "직전 거래일 가격이 그대로 유지된다"고 찍는 방법
    # 모델이 이 단순한 방법보다 못하면, 모델이 아무것도 배우지 못한 것
    results = [evaluate("Baseline(전일가)", y_test, X_test['price_lag_1'])]
    baseline_mae = results[0]['MAE']

    # 3. 비교할 모델 정의
    models = {
        "RandomForest": RandomForestRegressor(n_estimators=300, random_state=42),
        "XGBoost": XGBRegressor(n_estimators=1000, learning_rate=0.05, max_depth=5, random_state=42),
        "LightGBM": LGBMRegressor(n_estimators=1000, learning_rate=0.05, verbose=-1, random_state=42)
    }

    best_model = None
    best_mae = float('inf')
    best_name = ""

    print(f"🚀 [{target_item}] 모델 성능 비교 및 학습 시작...\n")

    # 4. 루프를 돌며 모델별 학습 및 평가
    for name, model in models.items():
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        result = evaluate(name, y_test, preds)
        results.append(result) 

        # [PR2] 선정 기준을 R2에서 MAE(원 단위 평균 오차)로 변경
        # 가격 예측에서는 "평균 몇 원 틀리나"가 해석하기 수비고, 베이스라인과 직접 비교 가능
        if result["MAE"] < best_mae:
            best_mae = result["MAE"]
            best_model = model
            best_name = name

        # 5. 결과 출력
        report_df = pd.DataFrame(results)
        report_df["vs_Baseline"] = (
            (baseline_mae - report_df["MAE"]) / baseline_mae * 100
        ).round(1).astype(str) + '%'
        report_df.loc[0, "vs_Baseline"] = "-"

        print("--- 최종 모델 성적표 (vs_Baseline: +면 베이스라인보다 오차 감소) ---")
        print(report_df.to_string(index=False))
        print(f"\n🥇 최우수 모델: {best_name} (MAE: {best_mae:.0f}원)")

        if best_mae >= baseline_mae:
            print(f"⚠️ 최우수 모델도 베이스라인(전일가, MAE {baseline_mae:,.0f}원)보다 정확하지 않습니다.")
            print("   → 단기(익일) 가격은 직전 가격이 대부분을 설명함. 기상 영향은 더 긴 시차로 분석 필요.")
        else:
            print(f"✅ 베이스라인 대비 오차 {baseline_mae - best_mae:,.0f}원 감소")


        # 6. 최우수 모델 저장
        os.makedirs('analytics/models', exist_ok=True)
        save_path = f'analytics/models/{target_item}_best_model.pkl'
        joblib.dump(best_model, save_path)
    
    print(f"✅ 모델 저장 완료: {save_path}")

if __name__ == "__main__":
    train_model(target_item="토마토")