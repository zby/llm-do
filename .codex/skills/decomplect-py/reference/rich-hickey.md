# Rich Hickey's Simplicity Principles (Python Examples)

## Core Philosophy

Rich Hickey (creator of Clojure) distinguishes between **simple** and **easy**:

- **Simple**: Not intertwined. One role, one concept, one dimension. Opposite of complex (complected).
- **Easy**: Near at hand. Familiar. Convenient. Opposite of hard.

**Key insight**: Easy is relative to the person. Simple is objective.

## What is Complecting?

**Complecting** = braiding/intertwining concerns that should be separate.

### Common Complections

| Complected | Decomplected |
|------------|--------------|
| State + Identity | Values + Managed references |
| What + How | Declarative + Implementation |
| What + When | Logic + Scheduling/Ordering |
| What + Who | Logic + Polymorphism dispatch |
| Values + Place | Immutable values + References |
| Rules + Enforcement | Data validation + Schema |

## Simple Made Easy (Key Concepts with Python)

### 1. Values Over State

```python
# Complected: value tied to place/identity
class User:
    def __init__(self, name: str):
        self.name = name

    def set_name(self, name: str):
        self.name = name

# Decomplected: immutable values
from dataclasses import dataclass

@dataclass(frozen=True)
class User:
    name: str

def rename(user: User, name: str) -> User:
    return User(name=name)
```

### 2. Functions Over Methods

```python
# Complected: behavior tied to class
class User:
    def __init__(self, email: str, age: int):
        self.email = email
        self.age = age

    def validate(self) -> list[str]:
        errors = []
        if '@' not in self.email:
            errors.append('Invalid email')
        if self.age < 0:
            errors.append('Invalid age')
        return errors

# Decomplected: function operates on data
from dataclasses import dataclass

@dataclass(frozen=True)
class User:
    email: str
    age: int

def validate_user(user: User) -> list[str]:
    errors = []
    if '@' not in user.email:
        errors.append('Invalid email')
    if user.age < 0:
        errors.append('Invalid age')
    return errors
```

### 3. Data Over Objects

```python
# Complected: data + behavior + identity
class OrderProcessor:
    def __init__(self):
        self.orders: list[Order] = []

    def add_order(self, order: Order):
        self.orders.append(order)

    def process(self):
        for order in self.orders:
            self._process_one(order)

# Decomplected: plain data + separate functions
from dataclasses import dataclass
from typing import NamedTuple

@dataclass(frozen=True)
class Order:
    id: str
    items: tuple[OrderItem, ...]
    total: float

class ProcessedOrder(NamedTuple):
    order_id: str
    status: str
    result: float

def process_orders(orders: list[Order]) -> list[ProcessedOrder]:
    return [process_order(order) for order in orders]

def process_order(order: Order) -> ProcessedOrder:
    # Pure transformation
    return ProcessedOrder(
        order_id=order.id,
        status='completed',
        result=order.total * 1.1,
    )
```

### 4. Comprehensions Over Iteration with Mutation

```python
# Complected: how (loop) with what (transformation)
result = []
for item in items:
    if item.active:
        result.append(transform(item))

# Decomplected: declarative
result = [transform(item) for item in items if item.active]
```

### 5. Explicit Dependencies Over Module State

```python
# Complected: shared mutable state
_config: dict = {}  # global, mutable

def get_setting(key: str) -> str:
    return _config[key]

def set_setting(key: str, value: str):
    _config[key] = value

# Decomplected: explicit dependency
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    database_url: str
    api_key: str
    debug: bool

def create_service(config: Config) -> Service:
    return Service(database_url=config.database_url)
```

## The Simplicity Checklist

When reviewing Python code, ask:

1. **Can I understand this in isolation?** (no hidden dependencies)
2. **Can I change this without fear?** (no action at a distance)
3. **Can I test this without mocks?** (pure functions)
4. **Can I reuse this in a different context?** (not tied to framework)
5. **Can I reason about this locally?** (referential transparency)

## Complexity Smells in Python

- Mutable state shared across functions
- Module-level mutable variables (`_cache = {}`)
- Classes with `self` state modified by multiple methods
- Callbacks that modify external state
- Classes that are both data containers and actors
- Methods that do I/O and computation
- Inheritance hierarchies for code reuse
- `global` keyword usage
- Mutable default arguments

## Simplicity Patterns

### Pattern: Replace Mutation with Transformation

```python
# Before
def process_items(items: list[Item]) -> list[Item]:
    for item in items:
        item.processed = True  # mutation
        item.result = compute(item)  # mutation
    return items

# After
from dataclasses import dataclass

@dataclass(frozen=True)
class ProcessedItem:
    original: Item
    processed: bool
    result: float

def process_items(items: list[Item]) -> list[ProcessedItem]:
    return [
        ProcessedItem(
            original=item,
            processed=True,
            result=compute(item),
        )
        for item in items
    ]
```

### Pattern: Replace Hidden State with Explicit Parameters

```python
# Before: hidden dependency
import logging
logger = logging.getLogger(__name__)

def process(data: Data) -> Result:
    logger.info("processing")  # where does logger come from?
    return transform(data)

# After: explicit dependency (or no logging in pure functions)
def process(data: Data) -> Result:
    return transform(data)

# If logging needed, do it in the shell
def process_with_logging(data: Data) -> Result:
    logger.info("processing")  # I/O in shell
    result = process(data)  # pure core
    logger.info("done")  # I/O in shell
    return result
```

### Pattern: Replace Time Coupling with Data Flow

```python
# Before: operations must happen in order
def process():
    validate()  # must be first
    transform()  # must be second
    save()      # must be third

# After: data flow enforces order
def process(input_data: Input) -> Result:
    validated = validate(input_data)  # returns data
    if validated.errors:
        return Result(errors=validated.errors)
    transformed = transform(validated.data)  # requires validated
    return save(transformed)  # requires transformed
```

### Pattern: Use NamedTuple/dataclass Instead of Dict

```python
# Before: stringly-typed dict
def get_user(user_id: str) -> dict:
    return {
        'id': user_id,
        'name': 'Alice',
        'email': 'alice@example.com',
    }

# After: typed, immutable data
from typing import NamedTuple

class User(NamedTuple):
    id: str
    name: str
    email: str

def get_user(user_id: str) -> User:
    return User(id=user_id, name='Alice', email='alice@example.com')
```

## Rich Hickey Talks (Reference)

- **Simple Made Easy** (2011): Core simplicity concepts
- **The Value of Values** (2012): Immutability and facts
- **The Language of the System** (2012): System-level simplicity
- **Hammock Driven Development** (2010): Thinking before coding
