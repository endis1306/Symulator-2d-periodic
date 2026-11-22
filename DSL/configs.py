from typing import List, Tuple, Dict, Any, Literal, Union
from pydantic import BaseModel, Field, field_validator, model_validator
import math

Vec2 = Tuple[float, float]


class ShapeBase(BaseModel):
    type: str

    @model_validator(mode="before")
    @classmethod
    def from_dsl_call(cls, data):
        if "__call__" in data:
            return {
                "type": data["__call__"],
                **{k: v for k, v in data.items() if k != "__call__"}
            }
        return data


class CircleShapeConfig(ShapeBase):
    type: Literal["circle"]
    r: float = Field(..., gt=0)


class PolygonShapeConfig(ShapeBase):
    type: Literal["polygon"]
    points: List[Vec2]

    @field_validator("points")
    @classmethod
    def validate_points(cls, pts):
        if len(pts) < 3:
            raise ValueError("Polygon musi mieć co najmniej 3 punkty")
        return pts


ShapeConfig = Union[CircleShapeConfig, PolygonShapeConfig]



class BodyParamsConfig(BaseModel):
    drag_lin_forward: float = Field(..., gt=0)
    drag_lin_side: float = Field(..., gt=0)
    drag_rot: float = Field(0.0, ge=0)
    I: float = Field(..., gt=0)
    mass: float = Field(..., gt=0)


class RotorConfig(BaseModel):
    id: str = Field(..., min_length=1)
    rotor_omega_max: float = Field(..., ge=0)
    tau_motor: float = Field(..., gt=0)
    k_thrust: float = Field(..., ge=0)
    angle_offset: float = 0.0
    position_local: Vec2 = (0.0, 0.0)


class EnginesControlConfig(BaseModel):
    engines: List[RotorConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_engines(self):
        ids = [e.id for e in self.engines]
        if len(ids) != len(set(ids)):
            raise ValueError("Zduplikowane id silników")

        if len(self.engines) == 1:
            raise ValueError("Obiekt nie może mieć dokładnie jednego silnika")

        return self


class SensorConfig(BaseModel):
    id: str = Field(..., min_length=1)
    category: str
    rays_count: int = Field(..., ge=1)
    max_range: float = Field(..., gt=0)
    fov: float = Field(..., gt=0, le=2 * math.pi)
    offset_theta: float = 0.0


class SensorsControlConfig(BaseModel):
    sensors: List[SensorConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_ids(self):
        ids = [s.id for s in self.sensors]
        if len(ids) != len(set(ids)):
            raise ValueError("Zduplikowane id sensorów")
        return self


class LogicConfig(BaseModel):
    type: str
    params: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_dsl_logic(cls, data):
        # DSL: { "type": "seek_control", "target_id": "obj1" }
        # JSON: { "type": "seek_control", "params": {...} }

        if isinstance(data, dict):
            if "type" in data and "params" not in data:
                return {
                    "type": data["type"],
                    "params": {
                        k: v for k, v in data.items()
                        if k != "type"
                    }
                }
        return data

    @model_validator(mode="after")
    def validate_logic(self):
        if self.type == "seek_control":
            if "target_id" not in self.params:
                raise ValueError("seek_control wymaga parametru target_id")
        return self




class SimObjectConfig(BaseModel):
    id: str = Field(..., min_length=1)

    shape: ShapeConfig

    positionXY: Vec2 = (0.0, 0.0)
    velocityXY: Vec2 = (0.0, 0.0)

    theta: float = 0.0
    omega: float = 0.0

    static: bool = False

    bodyParams: BodyParamsConfig

    engines: List[RotorConfig] = Field(default_factory=list)
    sensors: List[SensorConfig] = Field(default_factory=list)

    logic: LogicConfig


class WorldConfig(BaseModel):
    delta_t: float = Field(..., gt=0)
    iterations: int = Field(..., gt=0)
    boundary_point: Vec2
    log_file: str = Field(
        ...,
        description="Ścieżka do pliku logów (wymagana)"
    )

    objects: List[SimObjectConfig]

    @field_validator("boundary_point")
    @classmethod
    def validate_boundary(cls, bp):
        if bp[0] <= 0 or bp[1] <= 0:
            raise ValueError("boundary_point musi mieć dodatnie wartości")
        return bp


