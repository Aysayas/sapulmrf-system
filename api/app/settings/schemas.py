from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.masterdata.schemas import AlertPct, Capacity


class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    compost_temp_min: float
    compost_temp_max: float
    moisture_min: float
    moisture_max: float
    prediction_min_days: int
    anomaly_sd: float


class AreaLimit(BaseModel):
    id: int
    capacity_kg: Capacity
    alert_pct: AlertPct


class SettingsIn(BaseModel):
    compost_temp_min: Annotated[float, Field(ge=-10, le=100)]
    compost_temp_max: Annotated[float, Field(ge=-10, le=100)]
    moisture_min: Annotated[float, Field(ge=0, le=100)]
    moisture_max: Annotated[float, Field(ge=0, le=100)]
    prediction_min_days: Annotated[int, Field(ge=1, le=365)]
    anomaly_sd: Annotated[float, Field(ge=1, le=5)]
    storage_areas: list[AreaLimit] = []

    @model_validator(mode="after")
    def minimum_below_maximum(self):
        if self.compost_temp_min >= self.compost_temp_max:
            raise ValueError("The compost temperature minimum must be lower than the maximum.")
        if self.moisture_min >= self.moisture_max:
            raise ValueError("The moisture minimum must be lower than the maximum.")
        return self
