# StayNest — How It Works

This document explains the full internal mechanics of the StayNest backend: how requests flow through the system, how data is structured, how permissions work, and why things are built the way they are.

---

## Table of Contents

1. [Big Picture](#1-big-picture)
2. [Request Lifecycle](#2-request-lifecycle)
3. [Authentication — JWT in Cookies](#3-authentication--jwt-in-cookies)
4. [Data Models](#4-data-models)
5. [Permissions](#5-permissions)
6. [Properties](#6-properties)
7. [Bookings](#7-bookings)
8. [Reviews](#8-reviews)
9. [Stats](#9-stats)
10. [Serializers — Validation Layer](#10-serializers--validation-layer)
11. [How Everything Connects](#11-how-everything-connects)

---

## 1. Big Picture

StayNest is a **Django REST Framework** API. There is no frontend — it only speaks JSON over HTTP.

The system has two types of users:

- **Landlord** — creates and manages property listings, confirms or rejects booking requests.
- **Tenant** — searches for properties, makes bookings, leaves reviews.

Every request goes through this chain:

```
HTTP Request
    │
    ▼
Django Middleware Stack
    │  (security, sessions, CSRF, auth, JWT cookie refresh)
    ▼
URL Router  →  ViewSet / APIView
    │
    ▼
Permission Check
    │
    ▼
Serializer (validate input)
    │
    ▼
Business Logic (view method)
    │
    ▼
Database (MySQL via Django ORM)
    │
    ▼
Serializer (format output)
    │
    ▼
JSON Response
```

---

## 2. Request Lifecycle

### Step 1 — Middleware

Before any view runs, the request passes through Django's middleware stack (defined in `config/settings.py → MIDDLEWARE`). The most important custom middleware is `JWTMiddleware`.

#### JWTMiddleware (`my_app/middlewares.py`)

This middleware handles **silent token refresh** — the user never has to manually refresh their token.

Here is the exact logic on every request:

```
Does the request have auth cookies?
│
├── NO  → pass through unchanged
│
└── YES
    │
    ├── Is the refresh token valid?
    │   └── NO  → clear both cookies, pass through (user will get 401)
    │
    └── YES
        │
        ├── Is the access token still fresh (not expiring soon)?
        │   └── YES → inject "Authorization: Bearer <access>" into request headers
        │
        └── NO (expired or expiring within refresh_window_seconds)
            │
            ├── Mint a new access token from the refresh token
            │   └── SUCCESS → inject new token into headers, set new access cookie on response
            └── FAILURE → clear both cookies
```

`refresh_window_seconds` is calculated as `min(30, access_lifetime / 4)`. With the default 180-minute access lifetime, this is 30 seconds — meaning the token is refreshed when it has less than 30 seconds left.

**Why cookies instead of localStorage?**  
httpOnly cookies cannot be read by JavaScript, which protects against XSS attacks. The middleware bridges the gap between "token in cookie" and "DRF expects token in Authorization header" by injecting the header itself.

**Excluded paths** (middleware skips these entirely):
- `/auth/login/`
- `/auth/register/`
- `/auth/logout/`
- `/auth/token/refresh/`
- `/admin/*`

### Step 2 — URL Routing

`config/urls.py` maps URLs to views. Two DRF routers are used:

```python
router = DefaultRouter()
router.register("properties", PropertyViewSet)
router.register("bookings", BookingViewSet)

reviews_router = DefaultRouter()
reviews_router.register("reviews", ReviewViewSet)
```

`DefaultRouter` automatically generates all standard REST URLs:
- `GET /properties/` → list
- `POST /properties/` → create
- `GET /properties/{id}/` → retrieve
- `PUT/PATCH /properties/{id}/` → update
- `DELETE /properties/{id}/` → destroy

Custom actions (like `toggle`, `incoming`, `update_status`) are added with the `@action` decorator.

Reviews are **nested** under properties:
```
/properties/{property_pk}/reviews/
```
This means a review always belongs to a specific property, and the `property_pk` is available in the view via `self.kwargs["property_pk"]`.

### Step 3 — Permission Check

Before the view method runs, DRF checks permissions. See [Section 5](#5-permissions) for full details.

### Step 4 — Serializer validates input

For write operations (POST, PUT, PATCH), the serializer checks that the incoming data is valid. If not, it returns a `400 Bad Request` with error details. See [Section 10](#10-serializers--validation-layer).

### Step 5 — View executes business logic

The view method runs: queries the database, applies filters, calls `serializer.save()`, etc.

### Step 6 — Response

The serializer converts the model instance(s) to a Python dict, which DRF renders as JSON.

---

## 3. Authentication — JWT in Cookies

### Registration — `POST /auth/register/`

Anyone can register. The `RegisterSerializer` validates:
- Email is unique and normalized to lowercase
- `full_name` contains only letters, spaces, hyphens, apostrophes
- Password meets Django's password validators
- `password` and `re_password` match

On success, `User.objects.create_user()` is called, which hashes the password before saving.

### Login — `POST /auth/login/`

```
Client sends: { "email": "...", "password": "..." }
    │
    ▼
CustomTokenObtainPairSerializer validates credentials
    │
    ├── User not found or wrong password → 401
    ├── user.deleted == True → 400 "account deactivated"
    └── OK
        │
        ▼
Generate refresh token + access token for this user
serializer.user holds the authenticated User object — no extra DB query needed
    │
    ▼
Set httpOnly cookies:
    access_token  (expires in 180 min)
    refresh_token (expires in 7 days)
    │
    ▼
Return: { "detail": "Login successful.", "role": "...", "full_name": "..." }
```

The tokens themselves are **never returned in the response body** — only in cookies.

The JWT payload contains extra claims added by `CustomTokenObtainPairSerializer.get_token()`:
```json
{
  "user_id": 42,
  "role": "tenant",
  "full_name": "John Doe",
  "exp": 1234567890,
  "jti": "unique-token-id"
}
```

### Logout — `POST /auth/logout/`

Reads the `refresh_token` cookie, calls `token.blacklist()` to invalidate it server-side (stored in the `token_blacklist` table), then deletes both cookies.

### Token Rotation

`ROTATE_REFRESH_TOKENS = True` means every time a refresh token is used to mint a new access token, a **new refresh token is also issued** and the old one is blacklisted (`BLACKLIST_AFTER_ROTATION = True`). This limits the damage if a refresh token is stolen.

### Profile — `GET /PATCH /auth/me/`

Returns or updates the current user's profile. Only `full_name` is writable — `email`, `role`, `date_joined`, `deleted` are all read-only.

---

## 4. Data Models

All models live in `my_app/models/`. Here is the full schema and the relationships between tables.

### User (`my_app/models/users.py`)

```
users
├── id            (PK, auto)
├── email         (unique, max 80 chars) ← used as USERNAME_FIELD
├── full_name     (optional)
├── role          ("landlord" | "tenant")
├── password      (hashed by Django)
├── is_active     (bool, default True) ← set to False on soft delete
├── deleted       (bool, default False)
├── deleted_at    (datetime, nullable)
├── date_joined   (auto)
└── is_staff      (bool, for admin access)
```

`User` extends Django's `AbstractUser` but removes the `username` field — email is the login identifier.

**Soft delete**: calling `user.delete()` does NOT remove the row from the database. Instead it sets `deleted=True`, `deleted_at=now()`, and `is_active=False`. This preserves historical data (bookings, reviews) while blocking the user from logging in.

**UserManager**: custom manager that overrides `create_user` (requires email, not username) and `create_superuser` (defaults role to `landlord`).

---

### Property (`my_app/models/properties.py`)

```
properties
├── id            (PK, auto)
├── owner         (FK → users)
├── title         (max 200)
├── description   (text)
├── city          (max 100)
├── district      (max 100, optional)
├── location      (max 255, full address)
├── price         (decimal 10,2)
├── rooms         (positive int)
├── type          ("apartment" | "house" | "studio" | "room")
├── is_active     (bool, default True) ← landlord can toggle this
├── date_created  (auto)
└── views_count   (positive int, db_index) ← incremented on first view
```

---

### Booking (`my_app/models/bookings.py`)

```
bookings
├── id         (PK, auto)
├── user       (FK → users) ← the tenant who made the booking
├── property   (FK → properties)
├── check_in   (date)
├── check_out  (date)
├── status     ("pending" | "confirmed" | "rejected" | "cancelled")
├── checked_in (bool, default False) ← physical check-in flag
└── created_at (auto)
```

**Status lifecycle:**

```
                    ┌─────────────┐
                    │   PENDING   │ ← created here
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        (landlord)   (landlord)    (tenant)
              │            │            │
              ▼            ▼            ▼
         CONFIRMED      REJECTED    CANCELLED
              │
         (tenant)
              │
              ▼
          CANCELLED
```

---

### Review (`my_app/models/reviews.py`)

```
reviews
├── id          (PK, auto)
├── user        (FK → users)
├── property    (FK → properties)
├── rating      (1–5, validated)
├── comment     (text, optional)
└── created_at  (auto)

UNIQUE CONSTRAINT: (user, property) — one review per stay
```

---

### PropertyView (`my_app/models/stats.py`)

Tracks which user viewed which property and when. Used for the view history feature.

```
property_views
├── id             (PK, auto)
├── user           (FK → users)
├── property       (FK → properties)
├── created_at     (auto) ← first view
└── last_viewed_at (auto_now) ← updated on every subsequent view

UNIQUE CONSTRAINT: (user, property)
```

---

### SearchQuery (`my_app/models/stats.py`)

Tracks search terms used by each user.

```
search_queries
├── id              (PK, auto)
├── user            (FK → users)
├── term            (max 255, normalized to lowercase)
├── count           (positive int) ← incremented on repeat searches
└── last_searched_at (auto_now)

UNIQUE CONSTRAINT: (user, term)
```

---

## 5. Permissions

DRF permissions work at two levels:

- **View-level** (`has_permission`) — checked before the view runs. Blocks access entirely.
- **Object-level** (`has_object_permission`) — checked when a specific object is retrieved. Used for ownership checks.

### Built-in DRF permissions used

| Permission | Meaning |
|---|---|
| `AllowAny` | No authentication required |
| `IsAuthenticated` | Must be logged in |
| `IsAuthenticatedOrReadOnly` | Anonymous users can read (GET), must be logged in to write |

### Custom permissions (`my_app/permissions.py`)

#### `IsLandlord`
Checks **both** view-level conditions:
1. User is authenticated
2. `user.role == "landlord"`
3. `user.deleted == False`

Used on: create property, update property, delete property, toggle property, `GET /properties/my/`

#### `IsLandlordOwner`
Object-level only. Checks that `obj.owner_id == request.user.pk`.  
Used together with `IsLandlord` — first we confirm the user is a landlord, then that they own this specific listing.

#### `IsOwnerOrReadOnly`
Object-level. Safe methods (GET, HEAD, OPTIONS) always pass. For write methods, checks `obj.user_id == request.user.pk`.  
Used on: update/delete review — only the author can modify their own review.

#### `IsBookingParticipant`
Object-level. Passes if the user is either:
- The tenant who made the booking (`obj.user_id == user.pk`)
- The landlord who owns the property (`obj.property.owner_id == user.pk`)

Used on: retrieve booking detail.

#### `IsPropertyOwnerForBooking`
Object-level. Checks `obj.property.owner_id == request.user.pk`.  
Used on: confirm/reject a booking — only the property owner can do this.

### Permission matrix by endpoint

| Endpoint | Anonymous | Tenant | Landlord (own) | Landlord (other) |
|---|---|---|---|---|
| `GET /properties/` | ✅ (active only) | ✅ (active only) | ✅ (own inactive too) | ✅ (active only) |
| `POST /properties/` | ❌ | ❌ | ✅ | ✅ |
| `PATCH /properties/{id}/` | ❌ | ❌ | ✅ | ❌ |
| `DELETE /properties/{id}/` | ❌ | ❌ | ✅ (no active bookings) | ❌ |
| `POST /bookings/` | ❌ | ✅ | ❌ (own property) | ✅ |
| `GET /bookings/{id}/` | ❌ | ✅ (participant) | ✅ (participant) | ❌ |
| `PATCH /bookings/{id}/status/` | ❌ | ✅ (cancel own) | ✅ (confirm/reject) | ❌ |
| `GET /properties/{id}/reviews/` | ✅ | ✅ | ✅ | ✅ |
| `POST /properties/{id}/reviews/` | ❌ | ✅ (after stay) | ✅ (after stay) | ✅ (after stay) |

---

## 6. Properties

### ViewSet: `PropertyViewSet` (`my_app/views/properties.py`)

This is a full `ModelViewSet` — it handles all CRUD operations plus two custom actions.

#### Queryset building (`get_queryset`)

Every query annotates properties with computed fields:
```python
Property.objects.select_related("owner").annotate(
    avg_rating=Avg("reviews__rating"),   # average of all review ratings
    reviews_count=Count("reviews"),       # total number of reviews
)
```

These annotations are not stored in the database — they are calculated on the fly by SQL `AVG()` and `COUNT()` and attached to each object.

**Visibility rules:**
- Anonymous users and tenants → only `is_active=True` listings
- Landlords on `list` → active listings + their own inactive ones
- Landlords on `retrieve/update/delete` → all their own listings regardless of `is_active`

#### Filtering

Four systems work together:

1. **DjangoFilterBackend** — exact match: `?city=Kyiv&type=apartment&is_active=true`
2. **SearchFilter** — full-text search across `title` and `description`: `?search=cozy studio`
3. **OrderingFilter** — sort results: `?ordering=-price` or `?ordering=avg_rating`
4. **Manual range filters** — applied in `get_queryset`: `?price_min=500&price_max=2000&rooms_min=2`

All four range parameters are validated before being passed to the ORM. Non-numeric or non-positive values return `400 Bad Request` with a per-field error message instead of crashing with a database error:
```json
{ "price_min": ["'price_min' must be a valid number."] }
```

#### View counter (`retrieve`)

When a user opens a property detail page:
1. `PropertyView.objects.get_or_create(user=request.user, property=instance)` is called
2. If this is the **first time** this user views this property (`created=True`):
   - `Property.objects.filter(pk=...).update(views_count=F("views_count") + 1)` — atomic SQL increment, no race condition
3. If the user has viewed it before: only `last_viewed_at` is updated, counter stays the same

This prevents a single user from inflating the view count by refreshing the page.

#### Search history (`list`)

When an authenticated user searches with `?search=something`:
1. `SearchQuery.objects.get_or_create(user=user, term=term)` is called
2. If the term already exists: `count` is incremented atomically with `F("count") + 1`

#### Toggle (`PATCH /properties/{id}/toggle/`)

Uses `PropertyAvailabilitySerializer` which only exposes the `is_active` field. The landlord sends `{"is_active": false}` to deactivate a listing.

#### Delete protection (`perform_destroy`)

Before deleting a property, the system checks for active bookings:
```python
instance.bookings.filter(status__in=("pending", "confirmed")).exists()
```
If any exist, a `ValidationError` is raised and the property is NOT deleted. The landlord must cancel/reject all bookings first.

#### My properties (`GET /properties/my/`)

Returns all listings by the current landlord (including inactive ones), with pagination. This is separate from the main `list` action which mixes in other landlords' active listings.

---

## 7. Bookings

### ViewSet: `BookingViewSet` (`my_app/views/bookings.py`)

Only `create`, `retrieve`, `list` mixins are included — no update or delete. Status changes go through a dedicated action.

#### Create booking (`POST /bookings/`)

The entire creation is wrapped in `@transaction.atomic` — if anything fails, the database is rolled back.

**Validation in `BookingCreateSerializer`:**

1. `check_out` must be after `check_in`
2. `check_in` cannot be in the past
3. The property must be `is_active=True`
4. The tenant cannot book their own property
5. No overlapping bookings exist for the same property with `pending` or `confirmed` status

**Race condition protection:**

Two users could simultaneously pass validation (both see no overlapping bookings) and both create a booking for the same dates. To prevent this, the view uses `SELECT FOR UPDATE`:

```python
list(
    Booking.objects.select_for_update().filter(
        property=prop,
        status__in=("pending", "confirmed"),
        check_in__lt=check_out,
        check_out__gt=check_in,
    )
)
```

`SELECT FOR UPDATE` places a database-level lock on the matching rows. The second concurrent request will wait until the first transaction commits. By the time it proceeds, the first booking already exists, and the overlap check in the serializer will catch it.

> Note: `list()` is required to actually evaluate the queryset — Django querysets are lazy and won't execute SQL until iterated.

#### List bookings (`GET /bookings/`)

- **Tenant** sees their own bookings, filterable by `?status=pending|confirmed|rejected|cancelled`
- Passing an invalid status value returns `400` with a list of allowed values
- **Landlord** should use `GET /bookings/incoming/` instead (the `list` action filters by `user=request.user`, so a landlord would see nothing here)

#### Incoming bookings (`GET /bookings/incoming/`)

Landlord-only endpoint. Returns all bookings for properties owned by the current user. Supports `?status=` filter (validated against allowed values) and standard pagination.

#### Update status (`PATCH /bookings/{id}/status/`)

The status transition logic lives in `BookingStatusSerializer.validate_status()`:

**Landlord transitions:**
```
PENDING → CONFIRMED
PENDING → REJECTED
```

**Tenant transitions:**
```
PENDING   → CANCELLED
CONFIRMED → CANCELLED  (only if check_out is more than 1 day away)
```

Any other transition raises a `400 ValidationError` with a descriptive message.

The serializer also enforces that a landlord can only act on bookings for **their own properties** — if `instance.property.owner_id != request_user.pk`, a `400` is returned immediately, before the transition matrix is even checked.

The view additionally checks that a landlord can only confirm/reject bookings for **their own properties** using `IsPropertyOwnerForBooking`.

---

## 8. Reviews

### ViewSet: `ReviewViewSet` (`my_app/views/reviews.py`)

Nested under `/properties/{property_pk}/reviews/`. No `retrieve` action — reviews are only listed as a collection.

#### Who can review?

`ReviewWriteSerializer.validate()` checks:
```python
Booking.objects.filter(
    user=user,
    property=prop,
    status="confirmed",
    check_out__lte=timezone.localdate(),  # stay must be completed
).exists()
```

A user can only leave a review after their confirmed booking's `check_out` date has passed. This prevents reviewing a property before actually staying there.

#### One review per stay

The `Review` model has a `UniqueConstraint` on `(user, property)`. If a user tries to submit a second review, the database raises an `IntegrityError`, which the serializer catches and converts to a `400` response.

#### Editing and deleting

Only the author of a review can edit or delete it, enforced by `IsOwnerOrReadOnly`. The permission checks `obj.user_id == request.user.pk`.

---

## 9. Stats

Two simple read-only endpoints, both require authentication.

### `GET /stats/views/` — `MyViewHistoryView`

Returns the current user's `PropertyView` records, ordered by the property's `views_count` descending (most popular properties the user has visited appear first).

Uses `select_related("property", "property__owner")` to avoid N+1 queries — all related data is fetched in a single SQL JOIN.

### `GET /stats/searches/` — `MySearchHistoryView`

Returns the current user's `SearchQuery` records, ordered by `count` descending then `last_searched_at` descending (most frequent and most recent searches first).

---

## 10. Serializers — Validation Layer

Serializers serve two purposes:
1. **Deserialize** — validate and clean incoming request data
2. **Serialize** — convert model instances to JSON for responses

### Read vs Write serializers

Many resources have separate serializers for reading and writing:

| Resource | Read serializer | Write serializer |
|---|---|---|
| Property | `PropertyListSerializer` / `PropertyDetailSerializer` | `PropertyWriteSerializer` |
| Booking | `BookingReadSerializer` | `BookingCreateSerializer` / `BookingStatusSerializer` |
| Review | `ReviewReadSerializer` | `ReviewWriteSerializer` |

**Why separate?**  
Read serializers include nested objects (e.g., `owner` as a full `UserPublicSerializer` object). Write serializers accept only IDs and writable fields — you don't want a user to be able to submit a nested owner object and override ownership.

### Nested serializers

`UserPublicSerializer` is embedded in multiple read serializers:
```python
class PropertyListSerializer(serializers.ModelSerializer):
    owner = UserPublicSerializer(read_only=True)
```
This means a property response includes the owner's `id`, `email`, `full_name`, and `role` inline — no need for a separate request to look up the owner.

### `select_related` and N+1 prevention

Wherever nested serializers are used, the queryset uses `select_related()` to fetch related objects in a single SQL query:
```python
Booking.objects.select_related("user", "property", "property__owner")
```
Without this, serializing 10 bookings would fire 21 SQL queries (1 for bookings + 10 for users + 10 for properties). With `select_related`, it's 1 query with JOINs.

---

## 11. How Everything Connects

Here is a complete flow for a common scenario: **a tenant books a property and leaves a review**.

```
1. POST /auth/register/
   RegisterSerializer validates → User created → 201

2. POST /auth/login/
   CustomTokenObtainPairSerializer validates credentials
   → access_token + refresh_token set as httpOnly cookies
   → 200 { role, full_name }

3. GET /properties/?city=Kyiv&price_max=1000
   JWTMiddleware injects Authorization header from cookie
   PropertyViewSet.list() → annotated queryset with filters
   → 200 [{ id, title, price, avg_rating, ... }, ...]

4. GET /properties/42/
   PropertyViewSet.retrieve()
   → PropertyView.get_or_create() → views_count incremented if first visit
   → 200 { id, title, location, reviews, ... }

5. POST /bookings/
   { "property": 42, "check_in": "2026-06-01", "check_out": "2026-06-07" }
   BookingCreateSerializer.validate():
     - dates valid ✅
     - property is_active ✅
     - not own property ✅
     - no overlapping bookings ✅
   SELECT FOR UPDATE locks conflicting rows
   Booking created with status=PENDING
   → 201 { id, property, check_in, check_out, status: "pending" }

6. PATCH /bookings/55/status/   (landlord's request)
   { "status": "confirmed" }
   IsPropertyOwnerForBooking checks obj.property.owner_id == user.pk ✅
   BookingStatusSerializer: PENDING → CONFIRMED is allowed for landlord ✅
   → 200 { id, status: "confirmed" }

7. POST /properties/42/reviews/   (after check_out date has passed)
   { "rating": 5, "comment": "Great place!" }
   ReviewWriteSerializer.validate():
     - Booking with status=confirmed and check_out <= today exists ✅
   Review created
   UniqueConstraint prevents duplicate review
   → 201 { id, rating, comment }
```

---

*This document reflects the codebase as of the initial release. For endpoint details, see the live Swagger UI at `/api/schema/swagger/`.*
