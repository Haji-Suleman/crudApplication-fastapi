from enum import Enum
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Field as SQLField
from sqlmodel import Session, SQLModel, create_engine, select

# ---------- database ----------
engine = create_engine(
    "sqlite:///patients.db", connect_args={"check_same_thread": False}
)


class Patient(SQLModel, table=True):
    id: str = SQLField(primary_key=True, min_length=4, max_length=4)
    name: str
    age: int
    gender: str
    weight: float
    height: float
    bmi: float
    verdict: str


SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]

app = FastAPI()


# ---------- schemas ----------
class Gender(str, Enum):
    male = "Male"
    female = "Female"
    rather_not_say = "Rather not to say"


class Verdict(str, Enum):
    underweight = "Underweight"
    normal = "Normal"
    overweight = "Overweight"
    obese = "Obese"


class patientSchemaIn(BaseModel):
    id: str = Field(min_length=4, max_length=4)
    name: str
    age: int = Field(gt=0, lt=130)
    gender: Gender
    weight: float = Field(gt=0, description="Weight in kilos")
    height: float = Field(gt=0, description="Height in meters")


class patientSchemaOut(patientSchemaIn):
    bmi: float = Field(gt=0, description="BMI = weight (kg) / height (m)²")
    verdict: Verdict


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


def build_patient(data: patientSchemaIn) -> Patient:
    bmi, verdict = calculate_bmi_verdict(data.height, data.weight)
    return Patient(
        **data.model_dump(mode="json"),  # enums become plain strings
        bmi=bmi,
        verdict=verdict.value,
    )


# ---------- routes (plain def: SQLite driver is blocking) ----------
@app.get("/get_patients", response_model=list[patientSchemaOut])
def full_return(session: SessionDep):
    return session.exec(select(Patient)).all()


@app.get("/get_patient/", response_model=patientSchemaOut)
def single_patient_return(
    session: SessionDep,
    id: Annotated[str, Query(alias="item_id", min_length=4, max_length=4)],
):
    patient = session.get(Patient, id)
    if not patient:
        raise HTTPException(status_code=404, detail="No patient found by that id")
    return patient


@app.post("/load_patient", status_code=201, response_model=patientSchemaOut)
def add_patient(patient: patientSchemaIn, session: SessionDep):
    if session.get(Patient, patient.id):
        raise HTTPException(status_code=409, detail="Patient already exists")
    record = build_patient(patient)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


@app.delete("/delete_patient/")
def delete_patient(session: SessionDep, id: Annotated[str, Query(alias="item_id")]):
    patient = session.get(Patient, id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    session.delete(patient)
    session.commit()
    return "Patient deleted successfully"


@app.put("/update_patients/{patient_id}", response_model=patientSchemaOut)
def update_patient(patient_id: str, patient: patientSchemaIn, session: SessionDep):
    old = session.get(Patient, patient_id)
    if not old:
        raise HTTPException(status_code=404, detail="Patient not found")
    if patient.id != patient_id and session.get(Patient, patient.id):
        raise HTTPException(status_code=409, detail="New id already exists")
    session.delete(old)
    new = build_patient(patient)
    session.add(new)
    session.commit()
    session.refresh(new)
    return new
