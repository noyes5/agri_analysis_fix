from pydantic import BaseModel
from typing import Optional

class WeatherHistoryCreate(BaseModel):
    date: str
    avg_ta: float
    max_ta: float
    min_ta: float
    sum_rn: float

class PriceCreate(BaseModel):
    date: str
    item_name: str
    kind_name: str
    item_code: Optional[str] = "" 
    location: Optional[str] = ""
    unit: Optional[str] = ""
    price: float

    class Config:
        from_attributes = True

class WeatherForecastCreate(BaseModel):
    date: str
    fcst_time: str
    category: str
    fcst_value: float
    reg_date: str

    class Config:
        from_attributes = True

class WeatherRegionCreate(BaseModel):
    """[PR3] 산지 관측소 날씨. 기온은 관측 결측이 있을 수 있어 Optional"""
    date: str
    station_id: str
    station_name: Optional[str] = ""
    avg_ta: Optional[float] = None
    max_ta: Optional[float] = None
    min_ta: Optional[float] = None
    sum_rn: float = 0.0
    sum_ss_hr: float = 0.0