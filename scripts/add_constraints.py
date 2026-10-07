"""Add PK/FK constraints to Healthcare database."""
import psycopg2

conn = psycopg2.connect(
    host='localhost', port=5432, dbname='HealthCare',
    user='postgres', password='postgres'
)
conn.autocommit = True
cur = conn.cursor()

print("=" * 60)
print("ADDING PRIMARY KEYS")
print("=" * 60)

pks = [
    ("pk_patients", "ALTER TABLE patients ADD CONSTRAINT pk_patients PRIMARY KEY (id)"),
    ("pk_organizations", "ALTER TABLE organizations ADD CONSTRAINT pk_organizations PRIMARY KEY (id)"),
    ("pk_providers", "ALTER TABLE providers ADD CONSTRAINT pk_providers PRIMARY KEY (id)"),
    ("pk_payers", "ALTER TABLE payers ADD CONSTRAINT pk_payers PRIMARY KEY (id)"),
    ("pk_encounters", "ALTER TABLE encounters ADD CONSTRAINT pk_encounters PRIMARY KEY (id)"),
    ("pk_careplans", "ALTER TABLE careplans ADD CONSTRAINT pk_careplans PRIMARY KEY (id)"),
    ("pk_claims", "ALTER TABLE claims ADD CONSTRAINT pk_claims PRIMARY KEY (id)"),
    ("pk_claims_transactions", "ALTER TABLE claims_transactions ADD CONSTRAINT pk_claims_transactions PRIMARY KEY (id)"),
]

for name, sql in pks:
    try:
        cur.execute(sql)
        print(f"[OK] {name}")
    except Exception as e:
        print(f"[ERROR] {name}: {str(e)[:80]}")

print("\n" + "=" * 60)
print("ADDING FOREIGN KEYS")
print("=" * 60)

fks = [
    # providers
    ("fk_providers_organization", "ALTER TABLE providers ADD CONSTRAINT fk_providers_organization FOREIGN KEY (organization) REFERENCES organizations(id)"),

    # encounters
    ("fk_encounters_patient", "ALTER TABLE encounters ADD CONSTRAINT fk_encounters_patient FOREIGN KEY (patient) REFERENCES patients(id)"),
    ("fk_encounters_organization", "ALTER TABLE encounters ADD CONSTRAINT fk_encounters_organization FOREIGN KEY (organization) REFERENCES organizations(id)"),
    ("fk_encounters_provider", "ALTER TABLE encounters ADD CONSTRAINT fk_encounters_provider FOREIGN KEY (provider) REFERENCES providers(id)"),
    ("fk_encounters_payer", "ALTER TABLE encounters ADD CONSTRAINT fk_encounters_payer FOREIGN KEY (payer) REFERENCES payers(id)"),

    # allergies
    ("fk_allergies_patient", "ALTER TABLE allergies ADD CONSTRAINT fk_allergies_patient FOREIGN KEY (patient) REFERENCES patients(id)"),
    ("fk_allergies_encounter", "ALTER TABLE allergies ADD CONSTRAINT fk_allergies_encounter FOREIGN KEY (encounter) REFERENCES encounters(id)"),

    # careplans
    ("fk_careplans_patient", "ALTER TABLE careplans ADD CONSTRAINT fk_careplans_patient FOREIGN KEY (patient) REFERENCES patients(id)"),
    ("fk_careplans_encounter", "ALTER TABLE careplans ADD CONSTRAINT fk_careplans_encounter FOREIGN KEY (encounter) REFERENCES encounters(id)"),

    # conditions
    ("fk_conditions_patient", "ALTER TABLE conditions ADD CONSTRAINT fk_conditions_patient FOREIGN KEY (patient) REFERENCES patients(id)"),
    ("fk_conditions_encounter", "ALTER TABLE conditions ADD CONSTRAINT fk_conditions_encounter FOREIGN KEY (encounter) REFERENCES encounters(id)"),

    # devices
    ("fk_devices_patient", "ALTER TABLE devices ADD CONSTRAINT fk_devices_patient FOREIGN KEY (patient) REFERENCES patients(id)"),
    ("fk_devices_encounter", "ALTER TABLE devices ADD CONSTRAINT fk_devices_encounter FOREIGN KEY (encounter) REFERENCES encounters(id)"),

    # imaging_studies (no PK)
    ("fk_imaging_studies_patient", "ALTER TABLE imaging_studies ADD CONSTRAINT fk_imaging_studies_patient FOREIGN KEY (patient) REFERENCES patients(id)"),
    ("fk_imaging_studies_encounter", "ALTER TABLE imaging_studies ADD CONSTRAINT fk_imaging_studies_encounter FOREIGN KEY (encounter) REFERENCES encounters(id)"),

    # immunizations
    ("fk_immunizations_patient", "ALTER TABLE immunizations ADD CONSTRAINT fk_immunizations_patient FOREIGN KEY (patient) REFERENCES patients(id)"),
    ("fk_immunizations_encounter", "ALTER TABLE immunizations ADD CONSTRAINT fk_immunizations_encounter FOREIGN KEY (encounter) REFERENCES encounters(id)"),

    # medications
    ("fk_medications_patient", "ALTER TABLE medications ADD CONSTRAINT fk_medications_patient FOREIGN KEY (patient) REFERENCES patients(id)"),
    ("fk_medications_payer", "ALTER TABLE medications ADD CONSTRAINT fk_medications_payer FOREIGN KEY (payer) REFERENCES payers(id)"),
    ("fk_medications_encounter", "ALTER TABLE medications ADD CONSTRAINT fk_medications_encounter FOREIGN KEY (encounter) REFERENCES encounters(id)"),

    # observations
    ("fk_observations_patient", "ALTER TABLE observations ADD CONSTRAINT fk_observations_patient FOREIGN KEY (patient) REFERENCES patients(id)"),
    ("fk_observations_encounter", "ALTER TABLE observations ADD CONSTRAINT fk_observations_encounter FOREIGN KEY (encounter) REFERENCES encounters(id)"),

    # procedures
    ("fk_procedures_patient", "ALTER TABLE procedures ADD CONSTRAINT fk_procedures_patient FOREIGN KEY (patient) REFERENCES patients(id)"),
    ("fk_procedures_encounter", "ALTER TABLE procedures ADD CONSTRAINT fk_procedures_encounter FOREIGN KEY (encounter) REFERENCES encounters(id)"),

    # supplies
    ("fk_supplies_patient", "ALTER TABLE supplies ADD CONSTRAINT fk_supplies_patient FOREIGN KEY (patient) REFERENCES patients(id)"),
    ("fk_supplies_encounter", "ALTER TABLE supplies ADD CONSTRAINT fk_supplies_encounter FOREIGN KEY (encounter) REFERENCES encounters(id)"),

    # payer_transitions
    ("fk_payer_transitions_patient", "ALTER TABLE payer_transitions ADD CONSTRAINT fk_payer_transitions_patient FOREIGN KEY (patient) REFERENCES patients(id)"),
    ("fk_payer_transitions_payer", "ALTER TABLE payer_transitions ADD CONSTRAINT fk_payer_transitions_payer FOREIGN KEY (payer) REFERENCES payers(id)"),
    ("fk_payer_transitions_secondary_payer", "ALTER TABLE payer_transitions ADD CONSTRAINT fk_payer_transitions_secondary_payer FOREIGN KEY (secondary_payer) REFERENCES payers(id)"),
]

for name, sql in fks:
    try:
        cur.execute(sql)
        print(f"[OK] {name}")
    except Exception as e:
        print(f"[ERROR] {name}: {str(e)[:80]}")

print("\n" + "=" * 60)
print("ADDING CLAIMS & TRANSACTIONS FOREIGN KEYS (snake_case)")
print("=" * 60)

claims_fks = [
    # claims (snake_case columns)
    ("fk_claims_patient", "ALTER TABLE claims ADD CONSTRAINT fk_claims_patient FOREIGN KEY (patient_id) REFERENCES patients(id)"),
    ("fk_claims_provider", "ALTER TABLE claims ADD CONSTRAINT fk_claims_provider FOREIGN KEY (provider_id) REFERENCES providers(id)"),
    ("fk_claims_primary_payer", "ALTER TABLE claims ADD CONSTRAINT fk_claims_primary_payer FOREIGN KEY (primary_patient_insurance_id) REFERENCES payers(id)"),
    ("fk_claims_secondary_payer", "ALTER TABLE claims ADD CONSTRAINT fk_claims_secondary_payer FOREIGN KEY (secondary_patient_insurance_id) REFERENCES payers(id)"),
    ("fk_claims_referring_provider", "ALTER TABLE claims ADD CONSTRAINT fk_claims_referring_provider FOREIGN KEY (referring_provider_id) REFERENCES providers(id)"),
    ("fk_claims_appointment", "ALTER TABLE claims ADD CONSTRAINT fk_claims_appointment FOREIGN KEY (appointment_id) REFERENCES encounters(id)"),
    ("fk_claims_supervising_provider", "ALTER TABLE claims ADD CONSTRAINT fk_claims_supervising_provider FOREIGN KEY (supervising_provider_id) REFERENCES providers(id)"),

    # claims_transactions (snake_case columns)
    ("fk_claim_transactions_claim", "ALTER TABLE claims_transactions ADD CONSTRAINT fk_claim_transactions_claim FOREIGN KEY (claim_id) REFERENCES claims(id)"),
    ("fk_claim_transactions_patient", "ALTER TABLE claims_transactions ADD CONSTRAINT fk_claim_transactions_patient FOREIGN KEY (patient_id) REFERENCES patients(id)"),
    ("fk_claim_transactions_place_of_service", "ALTER TABLE claims_transactions ADD CONSTRAINT fk_claim_transactions_place_of_service FOREIGN KEY (place_of_service) REFERENCES organizations(id)"),
    ("fk_claim_transactions_appointment", "ALTER TABLE claims_transactions ADD CONSTRAINT fk_claim_transactions_appointment FOREIGN KEY (appointment_id) REFERENCES encounters(id)"),
    ("fk_claim_transactions_provider", "ALTER TABLE claims_transactions ADD CONSTRAINT fk_claim_transactions_provider FOREIGN KEY (provider_id) REFERENCES providers(id)"),
    ("fk_claim_transactions_supervising_provider", "ALTER TABLE claims_transactions ADD CONSTRAINT fk_claim_transactions_supervising_provider FOREIGN KEY (supervising_provider_id) REFERENCES providers(id)"),
]

for name, sql in claims_fks:
    try:
        cur.execute(sql)
        print(f"[OK] {name}")
    except Exception as e:
        print(f"[ERROR] {name}: {str(e)[:80]}")

conn.close()
print("\n" + "=" * 60)
print("DONE - Constraints added successfully!")
print("=" * 60)
