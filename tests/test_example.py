def test_exmaple_should_work():
    from typing import Annotated
    from dataclasses import dataclass
    from datetime import datetime, timezone

    import xmlstruct

    DATA = b"""
    <test:user xmlns:test="urn:test" test:id="1234">
        <test:name>user123</test:name>
        <test:email>user@example.com</test:email>
        <test:registered-since>2020-09-01T00:00:00.000000Z</test:registered-since>
    </test:user>
    """

    @dataclass
    class User:
        user_id: Annotated[int, xmlstruct.Attribute(name="id")]
        name: str
        email: str
        registered_since: Annotated[datetime, xmlstruct.Value(name="registered-since")]

    UserEncoding = xmlstruct.derive(User, local_name="user", namespace="urn:test")

    user = UserEncoding.parse(DATA)

    assert user == User(
        user_id=1234,
        name="user123",
        email="user@example.com",
        registered_since=datetime(
            2020, 9, 1, hour=0, minute=0, second=0, tzinfo=timezone.utc
        ),
    )
