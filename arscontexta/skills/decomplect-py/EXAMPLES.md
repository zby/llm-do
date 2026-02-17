# Decomplect-Py Skill Examples

## Quick Start

Ask Claude to analyze your Python code changes:

```
"Review my staged changes for decomplection"
"Would Rich Hickey approve of this Python code?"
"Check my PR for simplicity issues"
```

## Example Analysis: Django Service

### Input (git diff)

```python
# services/user_service.py (changed)
+ class UserService:
+     def __init__(self):
+         self.db = PostgresDB()
+         self.cache = RedisCache()
+         self.logger = logging.getLogger(__name__)
+
+     def get_user(self, user_id):
+         self.logger.info(f"Getting user {user_id}")
+
+         cached = self.cache.get(user_id)
+         if cached:
+             return cached
+
+         user = self.db.query(f"SELECT * FROM users WHERE id = '{user_id}'")
+
+         if user:
+             user['full_name'] = user['first_name'] + ' ' + user['last_name']
+             user['is_admin'] = user['role'] == 'admin'
+             self.cache.set(user_id, user)
+
+         return user
```

### Output

```markdown
# Decomplection Analysis (Python)

## Overall Grade: D

## Summary
The UserService complects multiple concerns (caching, logging, persistence, business logic) and uses weak types. Significant refactoring recommended.

## Pillar Scores

| Pillar | Grade | Key Finding |
|--------|-------|-------------|
| Simplicity | D | State + I/O + logic complected |
| FCIS | F | No separation of pure logic |
| Coupling | D | Hard-coded dependencies, SQL injection |

## Findings & Refactoring Suggestions

### 1. Simplicity: D

**Issue:** `services/user_service.py:14-15` - Business logic complected with I/O
```python
user['full_name'] = user['first_name'] + ' ' + user['last_name']
user['is_admin'] = user['role'] == 'admin'
```

**Suggested refactor:**
```python
from dataclasses import dataclass
from typing import NamedTuple

@dataclass(frozen=True)
class User:
    id: str
    first_name: str
    last_name: str
    role: str

class EnrichedUser(NamedTuple):
    id: str
    first_name: str
    last_name: str
    role: str
    full_name: str
    is_admin: bool

def enrich_user(user: User) -> EnrichedUser:
    """Pure function - no I/O, no mutation."""
    return EnrichedUser(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role,
        full_name=f"{user.first_name} {user.last_name}",
        is_admin=user.role == 'admin',
    )
```

**Why:** Separates pure transformation from I/O, making it testable without mocks.

---

### 2. FCIS: F

**Issue:** `services/user_service.py:6-17` - Business logic mixed with I/O

**I/O detected in business logic:**
- Line 6: logging
- Line 8-10: cache read
- Line 12: database query
- Line 16: cache write

**Suggested refactor:**
```python
from dataclasses import dataclass
from typing import Protocol, Optional

# CORE: Pure types and functions
@dataclass(frozen=True)
class User:
    id: str
    first_name: str
    last_name: str
    role: str

@dataclass(frozen=True)
class EnrichedUser:
    user: User
    full_name: str
    is_admin: bool

def enrich_user(user: User) -> EnrichedUser:
    """Pure function - testable without mocks."""
    return EnrichedUser(
        user=user,
        full_name=f"{user.first_name} {user.last_name}",
        is_admin=user.role == 'admin',
    )

# Abstractions for dependencies
class UserRepository(Protocol):
    def find_by_id(self, user_id: str) -> Optional[User]: ...

class Cache(Protocol):
    def get(self, key: str) -> Optional[User]: ...
    def set(self, key: str, value: User) -> None: ...

# SHELL: I/O orchestration
class UserService:
    def __init__(
        self,
        repo: UserRepository,
        cache: Cache,
        logger: logging.Logger,
    ):
        self._repo = repo
        self._cache = cache
        self._logger = logger

    def get_user(self, user_id: str) -> Optional[EnrichedUser]:
        self._logger.info(f"Getting user {user_id}")

        # I/O: cache lookup
        cached = self._cache.get(user_id)
        if cached:
            return enrich_user(cached)  # Pure transformation

        # I/O: database lookup
        user = self._repo.find_by_id(user_id)
        if user is None:
            return None

        # I/O: cache write
        self._cache.set(user_id, user)

        # Pure transformation
        return enrich_user(user)
```

**Why:** Pure `enrich_user` is testable without mocks. Shell handles I/O at edges.

---

### 3. Coupling: D

**Issue:** `services/user_service.py:3-5` - Hard-coded concrete dependencies
```python
def __init__(self):
    self.db = PostgresDB()
    self.cache = RedisCache()
    self.logger = logging.getLogger(__name__)
```

**Issue:** `services/user_service.py:12` - SQL injection vulnerability
```python
user = self.db.query(f"SELECT * FROM users WHERE id = '{user_id}'")
```

**Suggested refactor:**
```python
from typing import Protocol, Optional

class UserRepository(Protocol):
    def find_by_id(self, user_id: str) -> Optional[User]: ...

class PostgresUserRepository:
    def __init__(self, connection):
        self._conn = connection

    def find_by_id(self, user_id: str) -> Optional[User]:
        # Parameterized query prevents SQL injection
        result = self._conn.execute(
            "SELECT * FROM users WHERE id = %s",
            (user_id,)
        )
        row = result.fetchone()
        if row is None:
            return None
        return User(
            id=row['id'],
            first_name=row['first_name'],
            last_name=row['last_name'],
            role=row['role'],
        )

class UserService:
    def __init__(
        self,
        repo: UserRepository,  # Abstract dependency
        cache: Cache,
        logger: logging.Logger,
    ):
        self._repo = repo
        self._cache = cache
        self._logger = logger
```

**Why:** Dependency injection enables testing, swapping implementations, and follows the Dependency Inversion Principle.

## Priority Recommendations

1. **Fix SQL injection (Critical)**: Use parameterized queries immediately
2. **Extract pure functions**: Move business logic to pure functions for testability
3. **Dependency injection**: Accept dependencies in constructor for flexibility
4. **Add proper types**: Use dataclasses/NamedTuple instead of dicts
```

---

## Example Analysis: Flask API Handler

### Input (git diff)

```python
# handlers/order.py (changed)
+ @app.route('/api/orders', methods=['POST'])
+ def create_order():
+     data = request.get_json()
+
+     # Validate
+     if len(data.get('items', [])) == 0:
+         return jsonify({'error': 'no items'}), 400
+
+     # Calculate
+     total = 0
+     for item in data['items']:
+         total += item['price'] * item['qty']
+     total = total * 1.1  # Add tax
+
+     # Check inventory
+     for item in data['items']:
+         stock = Inventory.query.filter_by(sku=item['sku']).first()
+         if stock.qty < item['qty']:
+             return jsonify({'error': f"Not enough {item['sku']}"}), 400
+
+     # Save
+     order = Order(
+         id=str(uuid.uuid4()),
+         user_id=data['user_id'],
+         total=total,
+         created_at=datetime.now()
+     )
+     db.session.add(order)
+     db.session.commit()
+
+     return jsonify({'id': order.id, 'total': order.total})
```

### Output

```markdown
# Decomplection Analysis (Python)

## Overall Grade: C

## Summary
Handler mixes HTTP concerns with business logic. Multiple responsibilities complected. Extracting pure calculation functions would improve testability.

## Pillar Scores

| Pillar | Grade | Key Finding |
|--------|-------|-------------|
| Simplicity | C | Logic mixed with HTTP handling |
| FCIS | D | No pure functions, all mixed |
| Coupling | C | Direct ORM usage in handler |

## Findings & Refactoring Suggestions

### 1. Simplicity: C

**Issue:** `handlers/order.py:10-12` - Calculation complected with HTTP handling

**Suggested refactor:**
```python
from dataclasses import dataclass
from typing import NamedTuple

@dataclass(frozen=True)
class OrderItem:
    sku: str
    price: float
    qty: int

class OrderTotal(NamedTuple):
    subtotal: float
    tax: float
    total: float

def calculate_order_total(
    items: list[OrderItem],
    tax_rate: float = 0.1,
) -> OrderTotal:
    """Pure calculation function - no I/O."""
    subtotal = sum(item.price * item.qty for item in items)
    tax = subtotal * tax_rate
    return OrderTotal(
        subtotal=subtotal,
        tax=tax,
        total=subtotal + tax,
    )
```

---

### 2. FCIS: D

**Issue:** No separation between pure logic and I/O

**I/O detected in business logic:**
- Line 2: HTTP request parsing
- Line 15-17: Database query in validation
- Line 20-26: Order creation with uuid/datetime
- Line 27-28: Database save

**Suggested refactor:**
```python
from dataclasses import dataclass
from typing import Union
from datetime import datetime

# CORE: Pure types and functions
@dataclass(frozen=True)
class OrderItem:
    sku: str
    price: float
    qty: int

@dataclass(frozen=True)
class OrderRequest:
    user_id: str
    items: list[OrderItem]

@dataclass(frozen=True)
class OrderResult:
    subtotal: float
    tax: float
    total: float

@dataclass(frozen=True)
class ValidationError:
    message: str

def validate_order_request(request: OrderRequest) -> Union[OrderResult, ValidationError]:
    """Pure validation and calculation - no I/O."""
    if len(request.items) == 0:
        return ValidationError(message='no items')

    subtotal = sum(item.price * item.qty for item in request.items)
    tax = subtotal * 0.1

    return OrderResult(
        subtotal=subtotal,
        tax=tax,
        total=subtotal + tax,
    )

@dataclass(frozen=True)
class NewOrder:
    id: str
    user_id: str
    total: float
    created_at: datetime
    items: list[OrderItem]

def create_order_data(
    request: OrderRequest,
    result: OrderResult,
    order_id: str,
    created_at: datetime,
) -> NewOrder:
    """Pure function - creates order data without I/O."""
    return NewOrder(
        id=order_id,
        user_id=request.user_id,
        total=result.total,
        created_at=created_at,
        items=request.items,
    )


# SHELL: Flask handler
@app.route('/api/orders', methods=['POST'])
def create_order():
    # Parse (I/O)
    data = request.get_json()
    order_request = OrderRequest(
        user_id=data['user_id'],
        items=[
            OrderItem(sku=i['sku'], price=i['price'], qty=i['qty'])
            for i in data.get('items', [])
        ],
    )

    # Validate and calculate (pure)
    result = validate_order_request(order_request)
    if isinstance(result, ValidationError):
        return jsonify({'error': result.message}), 400

    # Check inventory (I/O)
    for item in order_request.items:
        stock = Inventory.query.filter_by(sku=item.sku).first()
        if stock.qty < item.qty:
            return jsonify({'error': f"Not enough {item.sku}"}), 400

    # Create order data (pure)
    new_order = create_order_data(
        request=order_request,
        result=result,
        order_id=str(uuid.uuid4()),
        created_at=datetime.now(),
    )

    # Save (I/O)
    order = Order(
        id=new_order.id,
        user_id=new_order.user_id,
        total=new_order.total,
        created_at=new_order.created_at,
    )
    db.session.add(order)
    db.session.commit()

    return jsonify({'id': order.id, 'total': order.total})
```

**Why:** Pure `validate_order_request` and `create_order_data` are testable without mocks or database.

---

### 3. Coupling: C

**Issue:** Handler has multiple responsibilities
- HTTP request parsing
- Validation
- Calculation
- Inventory checking
- Order persistence

**Suggested refactor:** Extract services
```python
from typing import Protocol

class InventoryChecker(Protocol):
    def check_availability(self, items: list[OrderItem]) -> list[str]:
        """Returns list of unavailable SKUs."""
        ...

class OrderRepository(Protocol):
    def save(self, order: NewOrder) -> None: ...

class CreateOrderUseCase:
    def __init__(
        self,
        inventory: InventoryChecker,
        orders: OrderRepository,
    ):
        self._inventory = inventory
        self._orders = orders

    def execute(
        self,
        request: OrderRequest,
        order_id: str,
        now: datetime,
    ) -> Union[NewOrder, ValidationError]:
        # Pure validation
        result = validate_order_request(request)
        if isinstance(result, ValidationError):
            return result

        # Check inventory
        unavailable = self._inventory.check_availability(request.items)
        if unavailable:
            return ValidationError(f"Not enough: {', '.join(unavailable)}")

        # Create and save
        order = create_order_data(request, result, order_id, now)
        self._orders.save(order)
        return order
```

## Priority Recommendations

1. **Extract pure functions**: `validate_order_request`, `calculate_order_total`
2. **Inject non-determinism**: Pass `uuid` and `datetime` as parameters
3. **Extract services**: Separate inventory checking and order persistence
```

---

## Example Analysis: Data Processing Script

### Input (git diff)

```python
# process_data.py (changed)
+ import csv
+ import json
+ from datetime import datetime
+
+ _cache = {}
+
+ def process_sales(filepath):
+     global _cache
+
+     with open(filepath) as f:
+         reader = csv.DictReader(f)
+         results = []
+
+         for row in reader:
+             if row['region'] in _cache:
+                 multiplier = _cache[row['region']]
+             else:
+                 with open('config.json') as cfg:
+                     config = json.load(cfg)
+                     multiplier = config['regions'][row['region']]
+                     _cache[row['region']] = multiplier
+
+             amount = float(row['amount']) * multiplier
+             results.append({
+                 'id': row['id'],
+                 'amount': amount,
+                 'processed_at': str(datetime.now())
+             })
+
+     return results
```

### Output

```markdown
# Decomplection Analysis (Python)

## Overall Grade: D

## Summary
Module-level mutable state, I/O mixed throughout, and non-determinism in core logic. Classic Python anti-patterns.

## Pillar Scores

| Pillar | Grade | Key Finding |
|--------|-------|-------------|
| Simplicity | D | Module-level mutable cache |
| FCIS | F | I/O interwoven with calculations |
| Coupling | D | Hidden file dependencies |

## Findings & Refactoring Suggestions

### 1. Simplicity: D

**Issue:** `process_data.py:5-6` - Module-level mutable state
```python
_cache = {}
# ...
global _cache
```

**Suggested refactor:**
```python
from dataclasses import dataclass
from functools import lru_cache

@dataclass(frozen=True)
class RegionConfig:
    region: str
    multiplier: float

# Option 1: Pure function with explicit cache
def get_multiplier(region: str, config: dict[str, float]) -> float:
    """Pure function - config passed explicitly."""
    return config.get(region, 1.0)

# Option 2: Use functools for memoization
@lru_cache(maxsize=100)
def load_config() -> dict[str, float]:
    """Cached config loading - explicit caching behavior."""
    with open('config.json') as f:
        return json.load(f)['regions']
```

---

### 2. FCIS: F

**Issue:** I/O interleaved with business logic throughout

**I/O detected:**
- Line 10: File read (sales CSV)
- Line 17-20: File read (config JSON) inside loop
- Line 26: `datetime.now()` in data transformation

**Suggested refactor:**
```python
from dataclasses import dataclass
from datetime import datetime
from typing import NamedTuple

# CORE: Pure types
@dataclass(frozen=True)
class SalesRecord:
    id: str
    region: str
    amount: float

class ProcessedRecord(NamedTuple):
    id: str
    amount: float
    processed_at: datetime

# CORE: Pure functions
def calculate_adjusted_amount(
    amount: float,
    multiplier: float,
) -> float:
    """Pure calculation."""
    return amount * multiplier

def process_record(
    record: SalesRecord,
    region_multipliers: dict[str, float],
    processed_at: datetime,
) -> ProcessedRecord:
    """Pure transformation - all dependencies explicit."""
    multiplier = region_multipliers.get(record.region, 1.0)
    return ProcessedRecord(
        id=record.id,
        amount=calculate_adjusted_amount(record.amount, multiplier),
        processed_at=processed_at,
    )

def process_all_records(
    records: list[SalesRecord],
    region_multipliers: dict[str, float],
    processed_at: datetime,
) -> list[ProcessedRecord]:
    """Pure batch transformation."""
    return [
        process_record(record, region_multipliers, processed_at)
        for record in records
    ]


# SHELL: I/O orchestration
import csv
import json

def load_sales_records(filepath: str) -> list[SalesRecord]:
    """I/O: Read sales CSV."""
    with open(filepath) as f:
        reader = csv.DictReader(f)
        return [
            SalesRecord(
                id=row['id'],
                region=row['region'],
                amount=float(row['amount']),
            )
            for row in reader
        ]

def load_region_config(config_path: str) -> dict[str, float]:
    """I/O: Read config JSON."""
    with open(config_path) as f:
        return json.load(f)['regions']

def process_sales(
    sales_path: str,
    config_path: str = 'config.json',
) -> list[ProcessedRecord]:
    """Shell: Orchestrates I/O and pure computation."""
    # Load data (I/O)
    records = load_sales_records(sales_path)
    multipliers = load_region_config(config_path)

    # Process (pure)
    return process_all_records(
        records=records,
        region_multipliers=multipliers,
        processed_at=datetime.now(),
    )
```

**Why:** Pure `process_all_records` is now testable with explicit inputs, no file mocking needed.

---

### 3. Coupling: D

**Issue:** Hidden dependency on `config.json` file path

**Suggested refactor:** Make dependencies explicit
```python
def process_sales(
    sales_path: str,
    config_path: str = 'config.json',  # Explicit, with default
) -> list[ProcessedRecord]:
    ...

# Or inject config directly
def process_sales_with_config(
    sales_path: str,
    region_multipliers: dict[str, float],
) -> list[ProcessedRecord]:
    records = load_sales_records(sales_path)
    return process_all_records(
        records=records,
        region_multipliers=region_multipliers,
        processed_at=datetime.now(),
    )
```

## Priority Recommendations

1. **Remove global state**: Eliminate `_cache` module variable
2. **Extract pure functions**: Separate calculation from I/O
3. **Inject non-determinism**: Pass `datetime.now()` as parameter
4. **Make dependencies explicit**: Pass config path or config data
```

---

## Testing the Refactored Code

After applying FCIS principles, testing becomes trivial:

```python
import pytest
from datetime import datetime
from process_data import (
    SalesRecord,
    ProcessedRecord,
    process_record,
    process_all_records,
)


def test_process_record():
    record = SalesRecord(id='001', region='US', amount=100.0)
    multipliers = {'US': 1.5, 'EU': 1.2}
    timestamp = datetime(2024, 1, 1, 12, 0, 0)

    result = process_record(record, multipliers, timestamp)

    assert result == ProcessedRecord(
        id='001',
        amount=150.0,
        processed_at=timestamp,
    )


def test_process_record_unknown_region_uses_default():
    record = SalesRecord(id='002', region='UNKNOWN', amount=100.0)
    multipliers = {'US': 1.5}
    timestamp = datetime(2024, 1, 1)

    result = process_record(record, multipliers, timestamp)

    assert result.amount == 100.0  # 1.0 default multiplier


def test_process_all_records():
    records = [
        SalesRecord(id='001', region='US', amount=100.0),
        SalesRecord(id='002', region='EU', amount=200.0),
    ]
    multipliers = {'US': 1.5, 'EU': 1.2}
    timestamp = datetime(2024, 1, 1)

    results = process_all_records(records, multipliers, timestamp)

    assert len(results) == 2
    assert results[0].amount == 150.0
    assert results[1].amount == 240.0
```

No mocks, no file system setup, no dependency injection frameworks - just pure functions with explicit inputs and outputs.
