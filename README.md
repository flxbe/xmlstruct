# xmlstruct

[![ci](https://github.com/flxbe/xmlstruct/actions/workflows/ci.yml/badge.svg)](https://github.com/flxbe/xmlstruct/actions/workflows/ci.yml)
<!-- [![pypi](https://img.shields.io/pypi/v/xmlstruct)](https://pypi.org/project/xmlstruct/) -->
<!-- [![python](https://img.shields.io/pypi/pyversions/xmlstruct)](https://img.shields.io/pypi/pyversions/xmlstruct) -->

<!-- start elevator-pitch -->

Declarative XML (de)serialization in Python using type annotations.

<!-- end elevator-pitch -->

## Getting Started

<!-- start quickstart -->

```python
from typing import Annotated
from dataclasses import dataclass
from datetime import datetime, timezone

import xmlstruct

DATA = b"""
<test:user xmlns:test="urn:test">
    <test:name>user123</test:name>
    <test:email>user@example.com</test:email>
    <test:registered-since>2020-09-01T00:00:00.000000Z</test:registered-since>
</test:user>
"""

@dataclass
class User:
    name: str
    email: str
    registered_since: Annotated[datetime, xmlstruct.Value(name="registered-since")]

UserEncoding = xmlstruct.derive(User, local_name="user", namespace="urn:test")

user = UserEncoding.parse(DATA)

assert user == User(
    name="user123",
    email="user@example.com",
    registered_since=datetime(
        2020, 9, 1, hour=0, minute=0, second=0, tzinfo=timezone.utc
    ),
)
```
