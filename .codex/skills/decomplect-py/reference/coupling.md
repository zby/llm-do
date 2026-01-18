# High-Cohesion, Low-Coupling (Python Examples)

## Definitions

**Cohesion**: How closely related the elements within a module are. High cohesion means the module does one thing well.

**Coupling**: How dependent modules are on each other. Low coupling means modules can change independently.

## The Goal

- **Maximize cohesion**: Group related functionality
- **Minimize coupling**: Reduce dependencies between groups

## Types of Coupling (Worst to Best)

### 1. Content Coupling (Worst)
One module modifies the internals of another.

```python
# Bad: directly accessing internal state
class UserService:
    def __init__(self):
        self._users: dict[str, User] = {}

class OrderService:
    def create_order(self, user_service: UserService, user_id: str):
        # Directly accessing UserService internals
        user = user_service._users[user_id]  # Accessing private!
```

### 2. Common Coupling
Modules share global data.

```python
# Bad: shared global state
_app_config: dict = {}

def service_a():
    return _app_config['key']

def service_b():
    _app_config['key'] = 'value'  # Mutation!
```

### 3. Control Coupling
One module controls the flow of another via flags.

```python
# Bad: flag determines behavior
def process(data: Data, mode: str) -> Result:
    if mode == 'fast':
        return fast_process(data)
    elif mode == 'slow':
        return slow_process(data)
    else:
        raise ValueError(f'Unknown mode: {mode}')

# Better: separate functions or strategy pattern
def fast_process(data: Data) -> Result: ...
def slow_process(data: Data) -> Result: ...

# Or using Protocol
from typing import Protocol

class Processor(Protocol):
    def process(self, data: Data) -> Result: ...

class FastProcessor:
    def process(self, data: Data) -> Result:
        return fast_process(data)

class SlowProcessor:
    def process(self, data: Data) -> Result:
        return slow_process(data)
```

### 4. Stamp Coupling
Modules share composite data but only use parts.

```python
# Bad: passing whole User when only name needed
@dataclass
class User:
    id: str
    name: str
    email: str
    address: Address
    preferences: Preferences

def greet(user: User) -> str:
    return f"Hello, {user.name}"

# Better: pass only what's needed
def greet(name: str) -> str:
    return f"Hello, {name}"
```

### 5. Data Coupling (Best)
Modules share only necessary primitive data.

```python
# Good: minimal data sharing
def calculate_discount(price: float, percentage: float) -> float:
    return price * (percentage / 100)
```

## Types of Cohesion (Worst to Best)

### 1. Coincidental Cohesion (Worst)
Unrelated functionality grouped together.

```python
# Bad: unrelated utilities
class Utils:
    @staticmethod
    def format_date(d: datetime) -> str: ...

    @staticmethod
    def calculate_tax(amount: float) -> float: ...

    @staticmethod
    def send_email(to: str, body: str) -> None: ...

    @staticmethod
    def parse_csv(content: str) -> list[dict]: ...
```

### 2. Logical Cohesion
Grouped by category, not by function.

```python
# Bad: grouped by "type"
class Handlers:
    def handle_user_request(self, request): ...
    def handle_order_request(self, request): ...
    def handle_payment_request(self, request): ...
```

### 3. Temporal Cohesion
Grouped by when they execute.

```python
# Bad: grouped by "initialization time"
def init_app():
    init_logging()
    init_database()
    init_cache()
    init_metrics()
    init_email()
```

### 4. Functional Cohesion (Best)
Every element contributes to a single well-defined task.

```python
# Good: single responsibility
from typing import Protocol

class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...
    def verify(self, password: str, hash: str) -> bool: ...
    def needs_rehash(self, hash: str) -> bool: ...
```

## Python-Specific Coupling Issues

### Circular Imports

```python
# models.py
from services import UserService  # Imports services

class User:
    def get_service(self) -> "UserService":
        return UserService(self)

# services.py
from models import User  # Circular import!

class UserService:
    def __init__(self, user: User):
        self.user = user
```

**Solutions:**

#### Solution 1: TYPE_CHECKING guard

```python
# services.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models import User

class UserService:
    def __init__(self, user: "User"):
        self.user = user
```

#### Solution 2: Lazy import

```python
# models.py
class User:
    def get_service(self):
        from services import UserService  # Import when needed
        return UserService(self)
```

#### Solution 3: Restructure (best)

```python
# interfaces.py - no dependencies
from typing import Protocol

class UserProtocol(Protocol):
    id: str
    name: str

# models.py
from interfaces import UserProtocol

class User(UserProtocol):
    def __init__(self, id: str, name: str):
        self.id = id
        self.name = name

# services.py
from interfaces import UserProtocol

class UserService:
    def __init__(self, user: UserProtocol):
        self.user = user
```

### Module-Level Mutable State

```python
# Bad: module-level mutable state
_cache: dict[str, User] = {}
_config: dict = {}

def get_user(user_id: str) -> User:
    if user_id not in _cache:
        _cache[user_id] = fetch_user(user_id)
    return _cache[user_id]
```

```python
# Good: explicit dependency injection
from dataclasses import dataclass, field

@dataclass
class UserCache:
    _cache: dict[str, User] = field(default_factory=dict)

    def get(self, user_id: str) -> User | None:
        return self._cache.get(user_id)

    def set(self, user_id: str, user: User) -> None:
        self._cache[user_id] = user

class UserRepository:
    def __init__(self, cache: UserCache, db: Database):
        self._cache = cache
        self._db = db

    def get_user(self, user_id: str) -> User:
        cached = self._cache.get(user_id)
        if cached:
            return cached
        user = self._db.fetch_user(user_id)
        self._cache.set(user_id, user)
        return user
```

### Large Base Classes

```python
# Bad: god base class
class BaseService:
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def query(self, sql: str) -> list: ...
    def execute(self, sql: str) -> None: ...
    def begin_transaction(self) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def log(self, message: str) -> None: ...
    def cache_get(self, key: str) -> Any: ...
    def cache_set(self, key: str, value: Any) -> None: ...
```

```python
# Good: small focused protocols
from typing import Protocol

class Connectable(Protocol):
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...

class Queryable(Protocol):
    def query(self, sql: str) -> list: ...

class Executable(Protocol):
    def execute(self, sql: str) -> None: ...

class Transactional(Protocol):
    def begin_transaction(self) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...

# Compose only what you need
class UserRepository:
    def __init__(
        self,
        db: Queryable,  # Only needs query capability
    ):
        self._db = db
```

### Django Fat Model Anti-Pattern

```python
# Bad: everything in the model
class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    items = models.JSONField()
    total = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20)

    def calculate_total(self) -> Decimal: ...
    def apply_discount(self, code: str) -> None: ...
    def send_confirmation_email(self) -> None: ...  # I/O in model!
    def update_inventory(self) -> None: ...  # Cross-concern!
    def generate_invoice(self) -> str: ...
    def sync_with_erp(self) -> None: ...  # External system!
```

```python
# Good: thin model + separate services
class Order(models.Model):
    """Just fields and simple properties."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    items = models.JSONField()
    total = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20)


# Pure functions for calculations
def calculate_order_total(items: list[dict]) -> Decimal:
    return sum(Decimal(item['price']) * item['qty'] for item in items)

def apply_discount(total: Decimal, discount_percent: Decimal) -> Decimal:
    return total * (1 - discount_percent / 100)


# Separate services for I/O
class OrderNotificationService:
    def __init__(self, email_client: EmailClient):
        self._email = email_client

    def send_confirmation(self, order: Order) -> None:
        self._email.send(order.user.email, self._format_confirmation(order))


class InventoryService:
    def __init__(self, inventory_repo: InventoryRepository):
        self._repo = inventory_repo

    def reserve_for_order(self, order: Order) -> None:
        for item in order.items:
            self._repo.reserve(item['sku'], item['qty'])
```

## Dependency Direction

Dependencies should point toward stability and abstraction.

```
Unstable (changes often)  ->  Stable (rarely changes)
Concrete (implementation) ->  Abstract (interfaces)
```

### Example: Dependency Inversion

```python
# Bad: high-level depends on low-level
class OrderService:
    def __init__(self):
        self.db = PostgresDB()  # Concrete dependency

    def save_order(self, order: Order) -> None:
        self.db.execute(f"INSERT INTO orders ...")
```

```python
# Good: depend on abstraction
from typing import Protocol

class OrderRepository(Protocol):
    def save(self, order: Order) -> None: ...
    def find(self, order_id: str) -> Order | None: ...

class PostgresOrderRepository:
    def __init__(self, connection: Connection):
        self._conn = connection

    def save(self, order: Order) -> None:
        self._conn.execute("INSERT INTO orders ...")

    def find(self, order_id: str) -> Order | None:
        ...

class OrderService:
    def __init__(self, repo: OrderRepository):  # Abstract dependency
        self._repo = repo

    def save_order(self, order: Order) -> None:
        self._repo.save(order)
```

## Coupling Checklist

When reviewing Python code, check:

1. **Import graph**: Can you draw a clean dependency diagram?
2. **Change impact**: If module A changes, how many others are affected?
3. **Test isolation**: Can you test a module without its dependencies?
4. **Interface size**: Are protocols/ABCs minimal (ISP)?
5. **Circular dependencies**: Any A -> B -> A cycles?

## Decoupling Strategies

1. **Dependency injection**: Pass dependencies, don't create them
2. **Events/Messages**: Communicate via events, not direct calls
3. **Protocols**: Depend on contracts, not implementations
4. **Data transfer objects**: Copy data at boundaries
5. **Configuration**: Externalize environment-specific values

```python
# Example: Event-based decoupling
from typing import Callable

# Event types
@dataclass(frozen=True)
class OrderCreated:
    order_id: str
    user_id: str
    total: float

# Event bus
class EventBus:
    def __init__(self):
        self._handlers: dict[type, list[Callable]] = {}

    def subscribe(self, event_type: type, handler: Callable) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def publish(self, event: Any) -> None:
        for handler in self._handlers.get(type(event), []):
            handler(event)

# Services are decoupled
class OrderService:
    def __init__(self, repo: OrderRepository, events: EventBus):
        self._repo = repo
        self._events = events

    def create_order(self, items: list[Item]) -> Order:
        order = Order(items=items)
        self._repo.save(order)
        self._events.publish(OrderCreated(
            order_id=order.id,
            user_id=order.user_id,
            total=order.total,
        ))
        return order

class InventoryService:
    def __init__(self, events: EventBus):
        events.subscribe(OrderCreated, self._on_order_created)

    def _on_order_created(self, event: OrderCreated) -> None:
        # React to order without direct coupling
        self._reserve_inventory(event.order_id)
```
