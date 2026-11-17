from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Options(StrictModel):
    padding: int = Field(default=16, ge=0, le=300)
    white_threshold: int = Field(default=254, ge=235, le=255)


class Flags(StrictModel):
    image_ids: list[str] = Field(max_length=200)
    remove_background: bool


class Point(StrictModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class Stroke(StrictModel):
    mode: Literal["restore", "erase"]
    radius: float = Field(ge=1, le=500)
    points: list[Point] = Field(min_length=1, max_length=4000)


class Crop(StrictModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(ge=1)
    height: int = Field(ge=1)


class Edit(StrictModel):
    revision: int = Field(ge=0)
    strokes: list[Stroke] = Field(default_factory=list, max_length=200)
    crop: Crop | None = None
    auto_crop: bool = False
    reset_original: bool = False

    @model_validator(mode="after")
    def mutually_exclusive(self):
        if sum([self.crop is not None, self.auto_crop, self.reset_original]) > 1:
            raise ValueError("Choose one crop or reset operation.")
        return self


class DetectRegions(StrictModel):
    revision: int = Field(ge=0)
    threshold: float = Field(default=0.15, ge=0.05, le=0.9)
    queries: list[str] = Field(default_factory=lambda: ["a brand logo", "a printed logo", "a brand name"], min_length=1, max_length=5)

    @model_validator(mode="after")
    def valid_queries(self):
        if any(not q.strip() or len(q) > 80 for q in self.queries):
            raise ValueError("Use 1–5 detection phrases of 1–80 characters each.")
        return self


class CleanupPreview(StrictModel):
    revision: int = Field(ge=0)
    regions: list[Crop] = Field(min_length=1, max_length=20)


class ApplyPreview(StrictModel):
    revision: int = Field(ge=0)
    preview_id: str = Field(pattern=r"^[a-f0-9]{32}$")
