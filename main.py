import json
import os
from enum import Enum
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

DATA_FILE = Path(__file__).parent / "patient.json"


def load_patients() -> dict[str, dict]:
    if not DATA_FILE.exists():
        return {}
    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def save_patients() -> None:
    tmp = DATA_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(patients, f, indent=4)
    os.replace(tmp, DATA_FILE)  # safe swap, avoids a half-written file


app = FastAPI()


class Gender(str, Enum):
    male = "Male"
    female = "Female"
    rather_not_say = "Rather not to say"


class Verdict(str, Enum):
    underweight = "Underweight"  # < 18.5
    normal = "Normal"  # 18.5 - 24.99
    overweight = "Overweight"  # 25 - 29.99
    obese = "Obese"  # 30+


class patientSchema(BaseModel):
    id: str = Field(min_length=4, max_length=4)
    name: str
    age: int = Field(gt=0, lt=130)
    gender: Gender
    weight: float = Field(gt=0, description="Weight in kilos")
    height: float = Field(gt=0, description="Height in meters")


def calculate_bmi_verdict(height_m: float, weight_kg: float) -> tuple[float, Verdict]:
    bmi = weight_kg / height_m**2
    if bmi < 18.5:
        verdict = Verdict.underweight
    elif bmi < 25:
        verdict = Verdict.normal
    elif bmi < 30:
        verdict = Verdict.overweight
    else:
        verdict = Verdict.obese
    return round(bmi, 2), verdict


def build_record(patient: patientSchema) -> dict:
    record = patient.model_dump(mode="json")
    bmi, verdict = calculate_bmi_verdict(patient.height, patient.weight)
    record["bmi"] = bmi
    record["verdict"] = verdict.value
    return record


patients: dict[str, dict] = load_patients()


@app.get("/get_patients")
async def full_return():
    return patients


@app.get("/get_patient/")
async def single_patient_return(
    id: Annotated[str, Query(alias="item_id", min_length=4, max_length=4)],
):
    patient = patients.get(id)
    if not patient:
        raise HTTPException(status_code=404, detail="No patient found by that id")
    return {"success": True, "patient": patient}


@app.post("/load_patient", status_code=201)
async def add_patient(patient: patientSchema):
    if patient.id in patients:
        raise HTTPException(status_code=409, detail="Patient already exists")
    patients[patient.id] = build_record(patient)
    save_patients()
    return "Patient added successfully"


@app.delete("/delete_patient/")
async def delete_patient(id: Annotated[str, Query(alias="item_id")]):
    if patients.pop(id, None) is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    save_patients()
    return "Patient deleted successfully"


@app.put("/update_patients/{patient_id}")
async def update_patient(patient_id: str, patient: patientSchema):
    if patient_id not in patients:
        raise HTTPException(status_code=404, detail="Patient not found")
    if patient.id != patient_id and patient.id in patients:
        raise HTTPException(status_code=409, detail="New id already exists")
    patients.pop(patient_id)
    patients[patient.id] = build_record(patient)
    save_patients()
    return "Patient updated successfully"
