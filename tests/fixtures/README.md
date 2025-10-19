# Test Fixtures

This directory contains test data fixtures for the CBC registration test suite.

> ***NOTE: The participant records in the CSV dataset contain count areas that are 
> specific to the Vancouver Count Circle.  A portable implementation of the test data 
> would need to update the participant records to be compatible with the count circle being tested.***


## Files

### test_participants_2025.csv
Standard test participant dataset with 347 participants across all areas.

**Source:** Generated using `utils/generate_test_participants.py` and sanitized for testing.

**Sanitization:**
- All phone numbers use 555 area code (not real)
- All email addresses use test patterns (not real people)
- No real PII present

**Contents:**
- 347 total participants
- 115 participants with secondary phone numbers (33%)
- Mix of regular participants, feeders, and scribes
- Various skill levels (Beginner, Intermediate, Expert)
- Some participants marked as leaders (`is_leader=True`)
- Distributed across all 24 count areas (A-X)
- Various equipment configurations (binoculars, spotting scopes)
- Leadership and scribe interest flags

## Usage

### Load full dataset into test database:
```bash
python tests/utils/load_test_data.py --years 2025
```

### Load subset (first 50 participants):
```bash
python tests/utils/load_test_data.py --years 2025 --max-count 50
```

### Load specific areas only:
```bash
python tests/utils/load_test_data.py --years 2025 --areas A B C
```

### Load into multiple years:
```bash
python tests/utils/load_test_data.py --years 2024 2025
```

### In pytest tests:
```python
def test_something(test_data_full):
    # Full dataset loaded into current year
    pass

def test_with_subset(test_data_small):
    # Subset of 50 participants loaded
    pass

def test_multi_year(test_data_historical):
    # Dataset loaded into current year + 2 previous years
    pass
```

## Maintenance

When updating test data:
1. Generate new participants using `utils/generate_test_participants.py`
2. Export to CSV from admin interface
3. Sanitize with `tests/utils/sanitize_csv.py` (replaces area codes with 555)
4. Add secondary phones with `debug/add_secondary_phones.py` (33% of records)
5. Replace `test_participants_2025.csv` in this directory
6. Update this README if data structure changes

## Data Structure

The CSV contains all fields from the participant model:
- **Personal**: first_name, last_name, email, phone, phone2
- **Experience**: skill_level, experience
- **Participation**: preferred_area, participation_type
- **Equipment**: has_binoculars, spotting_scope
- **Interests**: interested_in_leadership, interested_in_scribe
- **Leadership**: is_leader, assigned_area_leader
- **Admin**: notes_to_organizers, assigned_by, assigned_at
- **Timestamps**: created_at, updated_at, year

Note: The `id` field from the original export is ignored during import - new Firestore IDs are generated.
