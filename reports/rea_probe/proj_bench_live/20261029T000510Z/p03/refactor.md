# Refactoring Plan: Splitting `core.py`

## Objective
Split the oversized `core.py` module into two focused modules:
1. `core/parser.py` - Handles input parsing and validation
2. `core/processor.py` - Handles data processing and transformation

## Constraints
- **Tests must remain green**
- **Public API must remain unchanged**
- **No behavioral changes**

## Current Structure
```
core.py
├── parse_input(data: str) -> dict
├── validate_schema(data: dict) -> bool
├── transform_data(data: dict) -> dict
├── process_record(record: dict) -> dict
└── main()
```

## Target Structure
```
core/
├── __init__.py
│   ├── from .parser import parse_input, validate_schema
│   └── from .processor import transform_data, process_record
├── parser.py
│   ├── parse_input(data: str) -> dict
│   └── validate_schema(data: dict) -> bool
└── processor.py
    ├── transform_data(data: dict) -> dict
    └── process_record(record: dict) -> dict
```

## Implementation Steps

### 1. Create Package Structure
```bash
mkdir -p core
touch core/__init__.py
```

### 2. Extract Parser Functions
Move `parse_input` and `validate_schema` to `core/parser.py`:
```python
# core/parser.py
import json

def parse_input(data: str) -> dict:
    """Parse input string into dictionary."""
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON input")

def validate_schema(data: dict) -> bool:
    """Validate data against expected schema."""
    required_keys = {"id", "name", "value"}
    return required_keys.issubset(data.keys())
```

### 3. Extract Processor Functions
Move `transform_data` and `process_record` to `core/processor.py`:
```python
# core/processor.py
from .parser import validate_schema

def transform_data(data: dict) -> dict:
    """Transform data structure."""
    if not validate_schema(data):
        raise ValueError("Invalid schema")
    return {
        "id": data["id"],
        "name": data["name"].upper(),
        "value": float(data["value"]) * 2
    }

def process_record(record: dict) -> dict:
    """Process a single record."""
    return transform_data(record)
```

### 4. Update `__init__.py` for Backward Compatibility
```python
# core/__init__.py
from .parser import parse_input, validate_schema
from .processor import transform_data, process_record

__all__ = [
    "parse_input",
    "validate_schema",
    "transform_data",
    "process_record"
]
```

### 5. Update Import Statements
Change all imports from:
```python
from core import parse_input, validate_schema, transform_data, process_record
```
To:
```python
from core import parse_input, validate_schema, transform_data, process_record
```
