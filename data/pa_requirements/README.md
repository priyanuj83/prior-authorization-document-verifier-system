# Prior authorisation requirements

These files answer a **different question** from the ones in `../policies/`, and
keeping them separate is deliberate.

```
../policies/*.yaml          ->  "What clinical circumstances justify this service?"
./pa_requirements/*.yaml    ->  "Does this service require authorisation for this
                                 plan, on this date?"
```

The distinction is taken from UnitedHealthcare, which states explicitly that its
medical policies do not themselves indicate whether prior authorisation is
required, because those requirements are maintained separately.
See <https://www.uhcprovider.com/en/policies-protocols/commercial-policies/commercial-medical-drug-policies.html>.

## Why this matters for the corpus

Modelling it as two objects buys **gate outcomes** that sit before the
Supported / Missing / Contradicted judgement and can pre-empt it entirely:

| Gate result | Meaning |
|---|---|
| `AUTH_REQUIRED` | Authorisation is required. Verify the criteria in the governing policy. |
| `COVERAGE_REVIEW_REQUIRED` | Authorisation is not required *before* the service, but it is reviewable afterwards against the same criteria. Verify them anyway. |
| `NO_AUTH_REQUIRED` | This plan does not require authorisation for this service on this date, and it is not subject to review. No criterion is evaluated and there is nothing for the provider to prepare. |

`NO_AUTH_REQUIRED` is a real and common real-world result. Including it prevents
the verifier from learning that every input it sees must be verified, which is the
single easiest degenerate behaviour for a PA system to acquire.

`COVERAGE_REVIEW_REQUIRED` is the harder one, and it exists because
`MEDICARE-FFS-01` sets `requires_prior_auth: false` and
`requires_coverage_review: true` on the same service. Collapsing those two fields
into one boolean is the trap in `KNEE-ARTHRO-0003`.

## How a case resolves its policy

This is **runtime step one**, and the verifier must do it itself. The three input
fields all come from the model-visible form:

```
cases/<id>/input/pa_form.yaml
   member.plan_id  +  requested_service.service_key  +  submitted_date
                                        |
                                        v
                            pa_requirements/<plan_id>.yaml
                                        |
              requires_prior_auth?  --no--> requires_coverage_review?
                     |                            |            |
                    yes                          yes           no
                     |                            |            |
                     v                            v            v
              AUTH_REQUIRED         COVERAGE_REVIEW_REQUIRED   NO_AUTH_REQUIRED
                     |                            |            |
                     +--------------+-------------+         (stop, no criteria)
                                    v
                            governing_policy -> policies/<POLICY>.yaml
                                    v
                            criteria to verify the records against
```

Note the date check inside the requirements file: a service can be
`NO_AUTH_REQUIRED` for a request made before the requirement's
`effective_from` date and `AUTH_REQUIRED` for the identical request made after it.
`HUMANA-COMMERCIAL-01` uses a 2013-06-01 effective date for exactly this reason.

For **generation** rather than runtime, the payer can also be resolved from
Synthea directly, since `gold/ledger.yaml` carries the `payer_id`:

```
cases/<id>/gold/ledger.yaml
   payer_id  ------------------> synthea_data/payers.csv (Id -> NAME)
```

`synthea_data/payer_transitions.csv` maps patient to payer by year range and can
also be used, but it is **sparse for the late years** in this extract. All three
seed patients have episodes in 2014 and 2015 with no covering transition row, so
the cases resolve the payer from the `PAYER` column on the episode encounter in
`synthea_data/encounters.csv` instead. That column is populated for every
encounter and is the more reliable join.

## Plans in this corpus

The plan IDs below are fictional constructs layered on top of the payer names that
Synthea already uses. The real Aetna, Humana and Medicare do not publish plans
under these identifiers, and the authorisation requirements below are illustrative
rather than a transcription of any real plan's requirement list.

| File | Payer name in Synthea | Synthea payer Id | Used by |
|---|---|---|---|
| `AETNA-COMMERCIAL-01.yaml` | Aetna | `4d71f845-a6a9-3c39-b242-14d25ef86a8d` | `KNEE-ARTHRO-0002` |
| `HUMANA-COMMERCIAL-01.yaml` | Humana | `d47b3510-2895-3b70-9897-342d681c769d` | `KNEE-ARTHRO-0001` |
| `MEDICARE-FFS-01.yaml` | Medicare | `7caa7254-5050-3b5e-9eae-bd5ea30e809c` | `KNEE-ARTHRO-0003` |
