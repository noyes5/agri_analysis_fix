from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models, schemas, database # 여기서 모듈을 불러옵니다!

# DB 테이블 자동 생성
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Agri-Data Hub")

# DB 세션 함수
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/api/v1/ingest/weather-history")
def ingest_weather(weather_list: List[schemas.WeatherHistoryCreate], db: Session = Depends(get_db)):
    try:
        updated_count = 0
        inserted_count = 0

        for w in weather_list:
            # 1. 날짜(date)를 기준으로 이미 저장된 데이터가 있는지 확인
            existing = db.query(models.WeatherHistory).filter(
                models.WeatherHistory.date == w.date
            ).first()

            if existing:
                # 2. 이미 있다면: 최신 기온/강수량 정보로 업데이트
                existing.avg_ta = w.avg_ta
                existing.max_ta = w.max_ta
                existing.min_ta = w.min_ta
                existing.sum_rn = w.sum_rn
                updated_count += 1
            else:
                # 3. 없다면: 새로 추가
                db_item = models.WeatherHistory(**w.dict())
                db.add(db_item)
                inserted_count += 1
        
        db.commit()
        return {
            "status": "success", 
            "total": len(weather_list),
            "inserted": inserted_count,
            "updated": updated_count
        }
    
    except Exception as e:
        db.rollback()
        print(f"❌ 날씨 데이터 저장 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/api/v1/ingest/price")
def ingest_price(prices: List[schemas.PriceCreate], db: Session = Depends(get_db)):
    try:
        for p in prices:
            # 1. 같은 날짜, 같은 품목, 같은 품종, 같은 지역 데이터가 이미 있는지 확인
            existing = db.query(models.Price).filter(
                models.Price.date == p.date,
                models.Price.item_name == p.item_name,
                models.Price.kind_name == p.kind_name,
                models.Price.location == p.location
            ).first()

            if existing:
                # 2. 이미 있다면 가격이나 단위 등 업데이트
                existing.price = p.price
                existing.unit = p.unit
                # 필요한 다른 필드들도 업데이트 가능
            else:
                # 3. 없으면 새로 추가
                db_item = models.Price(**p.dict())
                db.add(db_item)
        
        db.commit()
        return {"status": "success", "count": len(prices)}
    except Exception as e:
        db.rollback()
        print(f"❌ 가격 데이터 저장 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/ingest/weather-forecast")
def ingest_forecast(forecasts: List[schemas.WeatherForecastCreate], db: Session = Depends(get_db)):
    try:
        # 먼저 기존 데이터를 확실히 삭제하고 '커밋'까지 완료
        # DB 파일에서 데이터가 먼저 물리적으로 비워짐
        num_deleted = db.query(models.WeatherForecast).delete()
        db.commit() 
        print(f"🗑️ 기존 예보 데이터 {num_deleted}건 삭제 완료.")

        # 새 데이터를 삽입
        for f in forecasts:
            db_item = models.WeatherForecast(**f.dict())
            db.add(db_item)
        
        db.commit()
        
        return {
            "status": "success", 
            "message": f"기존 {num_deleted}건 삭제 후 새 데이터 {len(forecasts)}건 교체 완료",
            "count": len(forecasts)
        }
        
    except Exception as e:
        db.rollback()
        print(f"❌ 날씨 예보 데이터 교체 중 오류 발생: {str(e)}")
        # 에러 메시지를 프론트(Pusher)에서도 볼 수 있게 상세히 전달
        raise HTTPException(status_code=500, detail=f"DB Error: {str(e)}")

@app.get("/api/v1/price")
def get_all_prices(db: Session = Depends(get_db)):
    # DB에서 모든 가격 데이터를 가져와서 반환
    prices = db.query(models.Price).all()
    return prices

@app.get("/api/v1/weather-history")
def get_all_weather(db: Session = Depends(get_db)):
    # DB에서 모든 과거 날씨 데이터를 가져와서 반환
    weather = db.query(models.WeatherHistory).all()
    return weather

# ---------------------------------------------------------------
# [PR3] 산지 관측소 날씨
# 기존 weather_history는 '날짜'만으로 중복을 판단해서
# 여러 지점을 넣으면 서로 덮어씀 → 지점번호+날짜 기준 별도 테이블 사용
# ---------------------------------------------------------------
@app.post("/api/v1/ingest/weather-region")
def ingest_weather_region(rows: List[schemas.WeatherRegionCreate], db: Session = Depends(get_db)):
    try:
        if not rows:
            return {"status": "success", "inserted": 0, "updated": 0}

        # 한 번 요청에 들어온 지점들의 기존 데이터를 미리 불러와 매 행마다 조회하지 않도록 함
        station_ids = {r.station_id for r in rows}
        dates = {r.date for r in rows}
        existing = {
            (w.station_id, w.date): w
            for w in db.query(models.WeatherRegion).filter(
                models.WeatherRegion.station_id.in_(station_ids),
                models.WeatherRegion.date.in_(dates)
            )
        }

        inserted, updated = 0, 0
        for r in rows:
            key = (r.station_id, r.date)
            if key in existing:
                for field, value in r.dict().items():
                    setattr(existing[key], field, value)
                updated += 1
            else:
                db.add(models.WeatherRegion(**r.dict()))
                inserted += 1

        db.commit()
        return {"status": "success", "inserted": inserted, "updated": updated}

    except Exception as e:
        db.rollback()
        print(f"❌ 산지 날씨 저장 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/weather-region")
def get_weather_region(station_id: str = None, db: Session = Depends(get_db)):
    query = db.query(models.WeatherRegion)
    if station_id:
        query = query.filter(models.WeatherRegion.station_id == station_id)
    return query.order_by(models.WeatherRegion.station_id, models.WeatherRegion.date).all()