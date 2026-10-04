from sqlalchemy import Column, Integer, String, Float
from database import Base

class WeatherHistory(Base):
    __tablename__ = "weather_history"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(String, index=True)       # 날짜
    avg_ta = Column(Float)
    max_ta = Column(Float)
    min_ta = Column(Float)
    sum_rn = Column(Float)

class Price(Base):
    __tablename__ = "prices"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(String, index=True)   # 날짜 (YYYY-MM-DD)
    item_code = Column(String)            # 작물 코드
    item_name = Column(String)            # 작물명
    kind_name = Column(String)            # 품종/등급
    location = Column(String, index=True) # 지역
    unit = Column(String)                 # 단위
    price = Column(Float)                 # 가격

class WeatherForecast(Base):
    __tablename__ = "weather_forecast"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(String, index=True)  # 예보 대상 날짜 (YYYYMMDD)
    fcst_time = Column(String)              # 예보 시각
    category = Column(String)               # 항목 (기온, 강수 등)
    fcst_value = Column(Float)              # 예보 값
    reg_date = Column(String)               # 예보 생성일 (조회 시점)

class WeatherRegion(Base):
    """[PR3] 산지 관측소별 일별 날씨 (지점번호 + 날짜가 고유키)"""
    __tablename__ = "weather_region"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(String, index=True)
    station_id = Column(String, index=True)
    station_name = Column(String)
    avg_ta = Column(Float)
    max_ta = Column(Float)
    min_ta = Column(Float)
    sum_rn = Column(Float)
    sum_ss_hr = Column(Float)