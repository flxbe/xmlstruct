from dataclasses import dataclass
from typing import Annotated, Optional
from enum import Enum, IntEnum
from xmlstruct import Value, derive, NoNamespace


# TODO: default namespace
# TODO: Attributes

def test_should_parse_primitive_types():
    DATA = b"""
    <data>
        <a>A</a>
        <b>1</b>
        <c>1.1</c>
    </data>
    """

    @dataclass
    class Data:
        a: str
        b: int
        c: float

    DataEncoding = derive(Data, local_name="data")

    instance = DataEncoding.parse(DATA)

    assert instance == Data(
        a="A",
        b=1,
        c=1.1,
    )


def test_should_parse_nested_structs():
    DATA = b"""
    <outer>
        <inner>
            <a>A</a>
            <b>B</b>
        </inner>
    </outer>
    """

    @dataclass
    class Inner:
        a: str
        b: str

    @dataclass
    class Outer:
        inner: Inner

    OuterEncoding = derive(Outer, local_name="outer")

    instance = OuterEncoding.parse(DATA)

    assert instance == Outer(
        inner=Inner(
            a="A",
            b="B",
        )
    )


def test_should_parse_optional_fields():
    DATA = b"""
    <wrapper>
        <a>A</a>
        <b></b>
        <c/>
    </wrapper>
    """

    @dataclass
    class Wrapper:
        a: Optional[str]
        b: Optional[str]
        c: Optional[str]
        d: Optional[str]

    WrapperEncoding = derive(Wrapper, local_name="wrapper")

    instance = WrapperEncoding.parse(DATA)

    assert instance == Wrapper(
        a="A",
        b=None,
        c=None,
        d=None,
    )


def test_should_parse_recursive_structs():
    DATA = b"""
    <schema>
        <group>
            <name>Group 1</name>
            <group>
                <name>Group 1.1</name>
            </group>
        </group>
    </schema>
    """

    @dataclass
    class Group:
        name: str
        group: Optional["Group"]

    @dataclass
    class Schema:
        group: Group

    SchemaEncoding = derive(Schema, local_name="schema", localns=locals())

    instance = SchemaEncoding.parse(DATA)

    assert instance == Schema(
        group=Group(
            name="Group 1",
            group=Group(
                name="Group 1.1",
                group=None,
            ),
        )
    )


def test_should_parse_lists():
    DATA = b"""
    <list>
        <item>A</item>
        <item>B</item>
        <item>C</item>
    </list>
    """

    @dataclass
    class List:
        items: Annotated[list[str], Value(name="item")]

    ListEncoding = derive(
        List,
        local_name="list",
    )

    instance = ListEncoding.parse(DATA)

    assert instance == List(items=["A", "B", "C"])


def test_should_use_value_config():
    DATA = b"""
    <test:schema xmlns:test="urn:test">
        <test:a>A</test:a>
        <test:b>B</test:b>
        <c>C</c>
    </test:schema>
    """

    @dataclass
    class Schema:
        a: Annotated[str, Value(namespace="urn:test")]
        not_b: Annotated[str, Value(namespace="urn:test", name="b")]
        c: Annotated[str, Value(namespace=NoNamespace)]

    SchemaEncoding = derive(
        Schema,
        local_name="schema",
        namespace="urn:test",
    )

    instance = SchemaEncoding.parse(DATA)

    assert instance == Schema(
        a="A",
        not_b="B",
        c="C",
    )


def test_should_parse_enums():
    DATA = b"""
    <data>
        <a>a</a>
        <b>b</b>
        <one>1</one>
        <two>2</two>
    </data>
    """

    class StringEnum(Enum):
        A = "a"
        B = "b"

    class NumericEnum(IntEnum):
        ONE = 1
        TWO = 2

    @dataclass
    class Data:
        a: StringEnum
        b: StringEnum
        one: NumericEnum
        two: NumericEnum

    DataEncoding = derive(Data, local_name="data")

    instance = DataEncoding.parse(DATA)

    assert instance == Data(
        a=StringEnum.A,
        b=StringEnum.B,
        one=NumericEnum.ONE,
        two=NumericEnum.TWO,
    )
