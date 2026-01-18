# Functional Core, Imperative Shell (Python Examples)

## Concept

Separate your code into two layers:

1. **Functional Core**: Pure functions containing business logic. No I/O, no side effects.
2. **Imperative Shell**: Thin layer that handles I/O and orchestrates the core.

## Why?

- **Testability**: Core logic testable without mocks
- **Predictability**: Pure functions always return same output for same input
- **Composability**: Pure functions compose easily
- **Debuggability**: No hidden state changes

## The Pattern

```
+-------------------------------------+
|         Imperative Shell            |
|  +-----------------------------+    |
|  |      Functional Core        |    |
|  |   (pure business logic)     |    |
|  +-----------------------------+    |
|           ^         v               |
|     [Read I/O]  [Write I/O]         |
+-------------------------------------+
```

## Python Examples

### Example 1: Order Processing

```python
# BAD: Mixed I/O and logic
def process_order(order_id: str) -> None:
    order = Order.objects.get(id=order_id)  # I/O

    if len(order.items) == 0:  # Logic
        raise ValueError('Empty order')

    total = sum(  # Logic
        item.price * item.qty
        for item in order.items
    )

    tax = total * 0.1  # Logic
    final_total = total + tax  # Logic

    order.total = final_total  # Mutation
    order.save()  # I/O
    send_confirmation_email(order.email, final_total)  # I/O
```

```python
# GOOD: Separated - Functional Core + Imperative Shell
from dataclasses import dataclass
from typing import Union

# CORE: Pure types and functions
@dataclass(frozen=True)
class OrderItem:
    price: float
    qty: int

@dataclass(frozen=True)
class OrderSuccess:
    total: float
    tax: float

@dataclass(frozen=True)
class OrderError:
    reason: str

OrderResult = Union[OrderSuccess, OrderError]

def calculate_order(items: list[OrderItem]) -> OrderResult:
    """Pure function - no I/O, deterministic, testable."""
    if len(items) == 0:
        return OrderError(reason='Empty order')

    subtotal = sum(item.price * item.qty for item in items)
    tax = subtotal * 0.1

    return OrderSuccess(total=subtotal + tax, tax=tax)


# SHELL: I/O orchestration
def process_order(order_id: str) -> None:
    """Thin shell - only I/O and orchestration."""
    # Input I/O
    order = Order.objects.get(id=order_id)

    # Pure computation
    result = calculate_order(order.items)

    # Output I/O
    if isinstance(result, OrderError):
        raise ValueError(result.reason)

    order.total = result.total
    order.save()
    send_confirmation_email(order.email, result.total)
```

### Example 2: Flask/Django View

```python
# BAD: Business logic in view
from flask import request, jsonify

@app.route('/api/users/<user_id>/level', methods=['POST'])
def update_user_level(user_id):
    user = User.query.get(user_id)  # I/O

    if user is None:
        return jsonify({'error': 'Not found'}), 404

    # Logic buried in view
    if user.score > 100:
        user.level = 'gold'
    elif user.score > 50:
        user.level = 'silver'
    else:
        user.level = 'bronze'

    db.session.commit()  # I/O
    return jsonify({'level': user.level})
```

```python
# GOOD: Separated
from dataclasses import dataclass
from typing import Optional

# CORE: Pure functions
def determine_level(score: int) -> str:
    """Pure function - easily testable."""
    if score > 100:
        return 'gold'
    elif score > 50:
        return 'silver'
    else:
        return 'bronze'


@dataclass(frozen=True)
class LevelUpdate:
    old_level: str
    new_level: str


def calculate_level_update(
    current_level: str,
    score: int,
) -> Optional[LevelUpdate]:
    """Pure function - returns what should change."""
    new_level = determine_level(score)
    if new_level != current_level:
        return LevelUpdate(old_level=current_level, new_level=new_level)
    return None


# SHELL: Flask view
@app.route('/api/users/<user_id>/level', methods=['POST'])
def update_user_level(user_id):
    # Input I/O
    user = User.query.get(user_id)
    if user is None:
        return jsonify({'error': 'Not found'}), 404

    # Pure computation
    update = calculate_level_update(user.level, user.score)

    # Output I/O
    if update:
        user.level = update.new_level
        db.session.commit()

    return jsonify({'level': user.level})
```

### Example 3: Data Processing

```python
# BAD: Mixed concerns
import csv
from datetime import datetime

def process_sales_report(filepath: str) -> None:
    with open(filepath) as f:  # I/O
        reader = csv.DictReader(f)
        total = 0
        for row in reader:  # Mixed I/O and logic
            amount = float(row['amount'])
            if row['status'] == 'completed':
                total += amount

    print(f"Total: {total}")  # I/O
    with open('report.txt', 'w') as f:  # I/O
        f.write(f"Report generated at {datetime.now()}\n")
        f.write(f"Total sales: {total}\n")
```

```python
# GOOD: Separated
from dataclasses import dataclass
from typing import Iterable
from datetime import datetime

# CORE: Pure types and functions
@dataclass(frozen=True)
class SaleRecord:
    amount: float
    status: str

@dataclass(frozen=True)
class SalesReport:
    total: float
    record_count: int

def calculate_sales_total(records: Iterable[SaleRecord]) -> SalesReport:
    """Pure function - testable without files."""
    completed = [r for r in records if r.status == 'completed']
    total = sum(r.amount for r in completed)
    return SalesReport(total=total, record_count=len(completed))

def format_report(report: SalesReport, generated_at: datetime) -> str:
    """Pure function - deterministic output."""
    return (
        f"Report generated at {generated_at}\n"
        f"Total sales: {report.total}\n"
        f"Records processed: {report.record_count}\n"
    )


# SHELL: I/O orchestration
import csv

def process_sales_report(
    input_path: str,
    output_path: str,
    now: datetime,
) -> None:
    """Shell - handles all I/O."""
    # Input I/O
    with open(input_path) as f:
        reader = csv.DictReader(f)
        records = [
            SaleRecord(amount=float(row['amount']), status=row['status'])
            for row in reader
        ]

    # Pure computation
    report = calculate_sales_total(records)
    content = format_report(report, now)

    # Output I/O
    print(f"Total: {report.total}")
    with open(output_path, 'w') as f:
        f.write(content)


# Usage in main
if __name__ == '__main__':
    process_sales_report(
        'sales.csv',
        'report.txt',
        datetime.now(),  # Non-determinism at edges
    )
```

## Testing Benefits

```python
# Core is trivially testable - no mocks needed!
import pytest
from myapp.core import calculate_order, OrderItem, OrderSuccess, OrderError


def test_calculate_order_with_items():
    items = [
        OrderItem(price=10.0, qty=2),
        OrderItem(price=5.0, qty=1),
    ]

    result = calculate_order(items)

    assert isinstance(result, OrderSuccess)
    assert result.total == 27.5  # (20 + 5) * 1.1
    assert result.tax == 2.5


def test_calculate_order_empty():
    result = calculate_order([])

    assert isinstance(result, OrderError)
    assert result.reason == 'Empty order'


def test_determine_level():
    assert determine_level(150) == 'gold'
    assert determine_level(75) == 'silver'
    assert determine_level(25) == 'bronze'
```

## Python I/O Checklist

What counts as I/O in Python:

1. **File operations**: `open()`, `read()`, `write()`, `pathlib` I/O
2. **Database**: SQLAlchemy, Django ORM, raw SQL
3. **Network**: `requests`, `httpx`, `aiohttp`, sockets
4. **Console**: `print()`, `input()`
5. **Logging**: `logging.*`, `logger.*`
6. **Time/Random**: `datetime.now()`, `time.time()`, `random.*`, `uuid.uuid4()`
7. **Environment**: `os.environ`, `os.getenv()`

## Common Mistakes

### Mistake 1: Logger in Core

```python
# Bad: I/O in core
import logging
logger = logging.getLogger(__name__)

def calculate(data: Data) -> float:
    logger.info('Calculating...')  # I/O!
    return data.a + data.b

# Good: No logging in core, or return log events
@dataclass(frozen=True)
class CalculationResult:
    value: float
    events: list[str]

def calculate(data: Data) -> CalculationResult:
    return CalculationResult(
        value=data.a + data.b,
        events=['calculation_performed'],
    )
```

### Mistake 2: Time/Random in Core

```python
# Bad: non-deterministic
from datetime import datetime
import uuid

def create_order(items: list[Item]) -> Order:
    return Order(
        id=str(uuid.uuid4()),  # Non-deterministic!
        created_at=datetime.now(),  # Non-deterministic!
        items=items,
    )

# Good: inject non-determinism
def create_order(
    items: list[Item],
    order_id: str,
    created_at: datetime,
) -> Order:
    return Order(id=order_id, created_at=created_at, items=items)

# Shell generates the values
def create_order_handler(items: list[Item]) -> Order:
    return create_order(
        items=items,
        order_id=str(uuid.uuid4()),
        created_at=datetime.now(),
    )
```

### Mistake 3: Exceptions in Core

```python
# Bad: exceptions are side effects
def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError('Division by zero')
    return a / b

# Good: return result type
from typing import Union
from dataclasses import dataclass

@dataclass(frozen=True)
class DivisionResult:
    value: float

@dataclass(frozen=True)
class DivisionError:
    reason: str

def divide(a: float, b: float) -> Union[DivisionResult, DivisionError]:
    if b == 0:
        return DivisionError(reason='Division by zero')
    return DivisionResult(value=a / b)
```
