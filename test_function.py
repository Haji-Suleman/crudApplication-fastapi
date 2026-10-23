VALID_PATIENT = {
    "id": "1001",
    "name": "Ali",
    "age": 30,
    "gender": "Male",
    "weight": 70,
    "height": 1.75,
}


def test_add_patient(client):
    response = client.post("/load_patient", json=VALID_PATIENT)
    assert response.status_code == 201


def test_bmi_and_verdict_are_calculated(client):
    client.post("/load_patient", json=VALID_PATIENT)
    response = client.get("/get_patient/", params={"item_id": "1001"})
    patient = response.json()
    print(patient)
    assert patient["bmi"] == 22.86
    assert patient["verdict"] == "Normal"


def test_duplicate_id_is_rejected(client):
    client.post("/load_patient", json=VALID_PATIENT)
    response = client.post("/load_patient", json=VALID_PATIENT)
    assert response.status_code == 409


def test_get_unknown_patient_returns_404(client):
    response = client.get("/get_patient/", params={"item_id": "9999"})
    assert response.status_code == 404


def test_invalid_height_is_rejected(client):
    bad = {**VALID_PATIENT, "height": 0}
    response = client.post("/load_patient", json=bad)
    assert response.status_code == 422


def test_invalid_gender_is_rejected(client):
    bad = {**VALID_PATIENT, "gender": "Other"}
    response = client.post("/load_patient", json=bad)
    assert response.status_code == 422


def test_delete_patient(client):
    client.post("/load_patient", json=VALID_PATIENT)
    assert (
        client.delete("/delete_patient/", params={"item_id": "1001"}).status_code == 200
    )
    assert client.get("/get_patient/", params={"item_id": "1001"}).status_code == 404


def test_update_patient_recalculates_bmi(client):
    client.post("/load_patient", json=VALID_PATIENT)
    updated = {**VALID_PATIENT, "weight": 85}
    assert client.put("/update_patients/1001", json=updated).status_code == 200
    patient = client.get("/get_patient/", params={"item_id": "1001"}).json()
    assert patient["bmi"] == 27.76
    assert patient["verdict"] == "Overweight"
