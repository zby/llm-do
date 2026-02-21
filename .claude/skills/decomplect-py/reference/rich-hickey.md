# Rich Hickey's Simplicity Principles (Python Examples)

## The Philosophy

Rich Hickey, creator of Clojure, draws a crucial distinction:

- **Simple**: Focused on one thing. Untangled from other concerns. An objective property of the code itself.
- **Easy**: Familiar and accessible. A subjective feeling that varies by person.

The insight: We often mistake *easy* for *simple*. Familiarity feels like simplicity, but they're not the same.

## Complecting: The Enemy of Simplicity

**Complecting** means weaving together things that don't belong together—creating hidden dependencies between concepts that should stand alone.

### Tangled vs. Untangled

| Tangled | Untangled |
|---------|-----------|
| State + Identity | Immutable values + Managed references |
| What + How | Specification + Implementation |
| What + When | Logic + Scheduling |
| What + Who | Logic + Dispatch mechanism |
| Values + Location | Data + References to data |
| Rules + Enforcement | Validation rules + Schema definitions |

## Core Principles Applied to Python

### 1. Values Over State

```python
# Tangled: value bound to mutable identity
class User:
    def __init__(self, name: str):
        self.name = name

    def set_name(self, name: str):
        self.name = name

# Untangled: immutable values
from dataclasses import dataclass

@dataclass(frozen=True)
class User:
    name: str

def rename(user: User, name: str) -> User:
    return User(name=name)
```

### 2. Functions Over Methods

```python
# Tangled: behavior bound to class
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

# Untangled: standalone function operating on data
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
# Tangled: data + behavior + identity in one
class OrderProcessor:
    def __init__(self):
        self.orders: list[Order] = []

    def add_order(self, order: Order):
        self.orders.append(order)

    def process(self):
        for order in self.orders:
            self._process_one(order)

# Untangled: plain data + separate functions
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
# Tangled: mechanics (loop) woven with intent (transformation)
result = []
for item in items:
    if item.active:
        result.append(transform(item))

# Untangled: declares intent directly
result = [transform(item) for item in items if item.active]
```

### 5. Explicit Dependencies Over Module State

```python
# Tangled: hidden shared state
_config: dict = {}  # global, mutable

def get_setting(key: str) -> str:
    return _config[key]

def set_setting(key: str, value: str):
    _config[key] = value

# Untangled: dependencies passed explicitly
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    database_url: str
    api_key: str
    debug: bool

def create_service(config: Config) -> Service:
    return Service(database_url=config.database_url)
```

## Questions for Evaluating Simplicity

When examining Python code:

1. **Self-contained?** Can I understand this without chasing imports?
2. **Safe to modify?** Can I change this without side effects elsewhere?
3. **Directly testable?** Can I test with plain values, no mocks?
4. **Portable?** Could I use this in another project unchanged?
5. **Locally comprehensible?** Can I reason about what happens here, right here?

## Warning Signs in Python Code

- Mutable state shared across functions
- Module-level mutable variables (`_cache = {}`)
- Classes with `self` state modified by multiple methods
- Callbacks that modify external state
- Classes that are both data containers and actors
- Methods that do I/O and computation
- Inheritance hierarchies for code reuse
- `global` keyword usage
- Mutable default arguments

## Simplification Patterns

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
# Before: implicit ordering
def process():
    validate()  # must be first
    transform()  # must be second
    save()      # must be third

# After: data flow makes ordering explicit
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

## Further Reading

Rich Hickey's talks that shaped these ideas:

- **Simple Made Easy** (2011): The foundational talk on simplicity vs. ease
- **The Value of Values** (2012): Why immutability matters
- **The Language of the System** (2012): Simplicity at the system level
- **Hammock Driven Development** (2010): The value of thinking before coding
