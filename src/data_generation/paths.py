from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
ROOT = PACKAGE_DIR.parents[1]
DATA_DIR = ROOT / "data"
CASES_DIR = DATA_DIR / "cases"
POLICIES_DIR = DATA_DIR / "policies"
PA_REQUIREMENTS_DIR = DATA_DIR / "pa_requirements"
SYNTHEA_DIR = ROOT / "synthea_data"
TEMPLATES_DIR = PACKAGE_DIR / "templates"
CATALOG_PATH = PACKAGE_DIR / "catalog.yaml"
SPLITS_PATH = DATA_DIR / "generation" / "splits.yaml"
