-- ============================================================================
-- Healthcare Database - PK/FK Constraint Setup (snake_case columns)
-- Run this script against: HealthCare.public
-- ============================================================================

-- ============================================================================
-- SECTION 1: Add Primary Keys (8 tables)
-- ============================================================================

ALTER TABLE patients ADD CONSTRAINT pk_patients PRIMARY KEY (id);
ALTER TABLE organizations ADD CONSTRAINT pk_organizations PRIMARY KEY (id);
ALTER TABLE providers ADD CONSTRAINT pk_providers PRIMARY KEY (id);
ALTER TABLE payers ADD CONSTRAINT pk_payers PRIMARY KEY (id);
ALTER TABLE encounters ADD CONSTRAINT pk_encounters PRIMARY KEY (id);
ALTER TABLE careplans ADD CONSTRAINT pk_careplans PRIMARY KEY (id);
ALTER TABLE claims ADD CONSTRAINT pk_claims PRIMARY KEY (id);
ALTER TABLE claims_transactions ADD CONSTRAINT pk_claims_transactions PRIMARY KEY (id);

-- ============================================================================
-- SECTION 2: Add Foreign Keys
-- ============================================================================

-- providers -> organizations
ALTER TABLE providers ADD CONSTRAINT fk_providers_organization
    FOREIGN KEY (organization) REFERENCES organizations(id);

-- encounters -> patients, organizations, providers, payers
ALTER TABLE encounters ADD CONSTRAINT fk_encounters_patient
    FOREIGN KEY (patient) REFERENCES patients(id);
ALTER TABLE encounters ADD CONSTRAINT fk_encounters_organization
    FOREIGN KEY (organization) REFERENCES organizations(id);
ALTER TABLE encounters ADD CONSTRAINT fk_encounters_provider
    FOREIGN KEY (provider) REFERENCES providers(id);
ALTER TABLE encounters ADD CONSTRAINT fk_encounters_payer
    FOREIGN KEY (payer) REFERENCES payers(id);

-- allergies -> patients, encounters
ALTER TABLE allergies ADD CONSTRAINT fk_allergies_patient
    FOREIGN KEY (patient) REFERENCES patients(id);
ALTER TABLE allergies ADD CONSTRAINT fk_allergies_encounter
    FOREIGN KEY (encounter) REFERENCES encounters(id);

-- careplans -> patients, encounters
ALTER TABLE careplans ADD CONSTRAINT fk_careplans_patient
    FOREIGN KEY (patient) REFERENCES patients(id);
ALTER TABLE careplans ADD CONSTRAINT fk_careplans_encounter
    FOREIGN KEY (encounter) REFERENCES encounters(id);

-- conditions -> patients, encounters
ALTER TABLE conditions ADD CONSTRAINT fk_conditions_patient
    FOREIGN KEY (patient) REFERENCES patients(id);
ALTER TABLE conditions ADD CONSTRAINT fk_conditions_encounter
    FOREIGN KEY (encounter) REFERENCES encounters(id);

-- devices -> patients, encounters
ALTER TABLE devices ADD CONSTRAINT fk_devices_patient
    FOREIGN KEY (patient) REFERENCES patients(id);
ALTER TABLE devices ADD CONSTRAINT fk_devices_encounter
    FOREIGN KEY (encounter) REFERENCES encounters(id);

-- imaging_studies -> patients, encounters
-- NOTE: NOT adding PK to imaging_studies.id (Synthea says non-unique)
ALTER TABLE imaging_studies ADD CONSTRAINT fk_imaging_studies_patient
    FOREIGN KEY (patient) REFERENCES patients(id);
ALTER TABLE imaging_studies ADD CONSTRAINT fk_imaging_studies_encounter
    FOREIGN KEY (encounter) REFERENCES encounters(id);

-- immunizations -> patients, encounters
ALTER TABLE immunizations ADD CONSTRAINT fk_immunizations_patient
    FOREIGN KEY (patient) REFERENCES patients(id);
ALTER TABLE immunizations ADD CONSTRAINT fk_immunizations_encounter
    FOREIGN KEY (encounter) REFERENCES encounters(id);

-- medications -> patients, payers, encounters
ALTER TABLE medications ADD CONSTRAINT fk_medications_patient
    FOREIGN KEY (patient) REFERENCES patients(id);
ALTER TABLE medications ADD CONSTRAINT fk_medications_payer
    FOREIGN KEY (payer) REFERENCES payers(id);
ALTER TABLE medications ADD CONSTRAINT fk_medications_encounter
    FOREIGN KEY (encounter) REFERENCES encounters(id);

-- observations -> patients, encounters
ALTER TABLE observations ADD CONSTRAINT fk_observations_patient
    FOREIGN KEY (patient) REFERENCES patients(id);
ALTER TABLE observations ADD CONSTRAINT fk_observations_encounter
    FOREIGN KEY (encounter) REFERENCES encounters(id);

-- procedures -> patients, encounters
ALTER TABLE procedures ADD CONSTRAINT fk_procedures_patient
    FOREIGN KEY (patient) REFERENCES patients(id);
ALTER TABLE procedures ADD CONSTRAINT fk_procedures_encounter
    FOREIGN KEY (encounter) REFERENCES encounters(id);

-- supplies -> patients, encounters
ALTER TABLE supplies ADD CONSTRAINT fk_supplies_patient
    FOREIGN KEY (patient) REFERENCES patients(id);
ALTER TABLE supplies ADD CONSTRAINT fk_supplies_encounter
    FOREIGN KEY (encounter) REFERENCES encounters(id);

-- payer_transitions -> patients, payers
ALTER TABLE payer_transitions ADD CONSTRAINT fk_payer_transitions_patient
    FOREIGN KEY (patient) REFERENCES patients(id);
ALTER TABLE payer_transitions ADD CONSTRAINT fk_payer_transitions_payer
    FOREIGN KEY (payer) REFERENCES payers(id);
ALTER TABLE payer_transitions ADD CONSTRAINT fk_payer_transitions_secondary_payer
    FOREIGN KEY (secondary_payer) REFERENCES payers(id);

-- claims (snake_case columns)
ALTER TABLE claims ADD CONSTRAINT fk_claims_patient
    FOREIGN KEY (patient_id) REFERENCES patients(id);
ALTER TABLE claims ADD CONSTRAINT fk_claims_provider
    FOREIGN KEY (provider_id) REFERENCES providers(id);
ALTER TABLE claims ADD CONSTRAINT fk_claims_primary_payer
    FOREIGN KEY (primary_patient_insurance_id) REFERENCES payers(id);
ALTER TABLE claims ADD CONSTRAINT fk_claims_secondary_payer
    FOREIGN KEY (secondary_patient_insurance_id) REFERENCES payers(id);
ALTER TABLE claims ADD CONSTRAINT fk_claims_referring_provider
    FOREIGN KEY (referring_provider_id) REFERENCES providers(id);
ALTER TABLE claims ADD CONSTRAINT fk_claims_appointment
    FOREIGN KEY (appointment_id) REFERENCES encounters(id);
ALTER TABLE claims ADD CONSTRAINT fk_claims_supervising_provider
    FOREIGN KEY (supervising_provider_id) REFERENCES providers(id);

-- claims_transactions (snake_case columns)
ALTER TABLE claims_transactions ADD CONSTRAINT fk_claim_transactions_claim
    FOREIGN KEY (claim_id) REFERENCES claims(id);
ALTER TABLE claims_transactions ADD CONSTRAINT fk_claim_transactions_patient
    FOREIGN KEY (patient_id) REFERENCES patients(id);
ALTER TABLE claims_transactions ADD CONSTRAINT fk_claim_transactions_place_of_service
    FOREIGN KEY (place_of_service) REFERENCES organizations(id);
ALTER TABLE claims_transactions ADD CONSTRAINT fk_claim_transactions_appointment
    FOREIGN KEY (appointment_id) REFERENCES encounters(id);
ALTER TABLE claims_transactions ADD CONSTRAINT fk_claim_transactions_provider
    FOREIGN KEY (provider_id) REFERENCES providers(id);
ALTER TABLE claims_transactions ADD CONSTRAINT fk_claim_transactions_supervising_provider
    FOREIGN KEY (supervising_provider_id) REFERENCES providers(id);

-- ============================================================================
-- SECTION 3: Optional - patientinsuranceid FK (requires unique member_id)
-- Only run if member_id is unique in payer_transitions
-- ============================================================================
/*
-- Check uniqueness first:
SELECT member_id, COUNT(*) FROM payer_transitions
WHERE member_id IS NOT NULL GROUP BY member_id HAVING COUNT(*) > 1;

-- If 0 rows, uncomment these:
-- ALTER TABLE payer_transitions ADD CONSTRAINT uq_payer_transitions_memberid UNIQUE (member_id);
-- ALTER TABLE claims_transactions ADD CONSTRAINT fk_claim_transactions_patient_insurance
--     FOREIGN KEY (patient_insurance_id) REFERENCES payer_transitions(member_id);
*/

-- ============================================================================
-- SECTION 4: Verification
-- ============================================================================
/*
SELECT
    tc.table_name,
    tc.constraint_name,
    tc.constraint_type
FROM information_schema.table_constraints tc
WHERE tc.table_schema = 'public'
  AND tc.constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY')
ORDER BY tc.table_name, tc.constraint_type;
*/
