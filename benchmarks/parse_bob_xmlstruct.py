import time
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum, IntEnum
from typing import Annotated, Optional, TypeVar

import xmlstruct

E = TypeVar("E", bound=Enum)


def create_code_encoding(cls: type[E]) -> xmlstruct.Encoding[E]:
    """
    Create a specialized encoding to parse nested code items of the form

    ```xml
    <outer>
        <code>Actual Value</code>
    </outer>
    ```

    directly into an Enum, without needing to parse the nested structure
    into a custom dataclass with only one member `code`.
    """

    if issubclass(cls, IntEnum):
        enum_encoding = xmlstruct.RequiredValueEncoding.for_int_enum(cls)
    else:
        enum_encoding = xmlstruct.RequiredValueEncoding.for_enum(cls)

    def _decode_code(node: xmlstruct.XmlElement) -> E:
        assert len(node) == 1

        child = node[0]
        assert child.tag == "code"

        return enum_encoding.parse(None, child)

    return xmlstruct.RequiredValueEncoding(decode=_decode_code)


class Status(Enum):
    IN_VORBEREITUNG = "inVorbereitung"
    AKTIV = "aktiv"
    INAKTIV = "inaktiv"


StatusEncoding = create_code_encoding(Status)


class Feldart(Enum):
    INPUT = "input"
    SELECT = "select"
    LABEL = "label"


FeldartEncoding = create_code_encoding(Feldart)


class Datentyp(Enum):
    TEXT = "text"
    DATUM = "date"
    WAHRHEITSWERT = "bool"
    NUMMER = "num"
    GANZZAHL = "num_int"
    GELDBETRAG = "num_currency"
    ANLAGE = "file"
    OBJEKT = "obj"


DatentypEncoding = create_code_encoding(Datentyp)


class AbleitungsmodifikationenStruktur(IntEnum):
    NICHT_MODIFIZIERBAR = 0
    NUR_EINSCHRAENKBAR = 1
    NUR_ERWEITERBAR = 2
    ALLES_MODIFIZIERBAR = 3


AbleitungsmodifikationenStrukturEncoding = create_code_encoding(
    AbleitungsmodifikationenStruktur
)


class AbleitungsmodifikationenRepraesentation(IntEnum):
    NICHT_MODIFIZIERBAR = 0
    MODIFIZIERBAR = 1


AbleitungsmodifikationenRepraesentationEncoding = create_code_encoding(
    AbleitungsmodifikationenRepraesentation
)


@dataclass(slots=True)
class MessageHeader:
    nachrichtID: str
    erstellungszeitpunkt: datetime


@dataclass(slots=True, frozen=True)
class ElementIdentifikation:
    id: str
    version: str | None


@dataclass(slots=True)
class Struktur:
    anzahl: str
    bezug: str | None
    enthaelt: (
        Annotated["Datenfeldgruppe", xmlstruct.Variant("datenfeldgruppe")]
        | Annotated["Datenfeld", xmlstruct.Variant("datenfeld")]
    )


@dataclass(slots=True)
class AllgemeineAngaben:
    identifikation: ElementIdentifikation
    name: str
    # This is required by the standard, but not always filled in real data
    bezeichnung_einabe: Annotated[str | None, xmlstruct.Value("bezeichnungEingabe")]
    bezeichnung_ausgabe: Annotated[str | None, xmlstruct.Value("bezeichnungAusgabe")]
    beschreibung: Optional[str]
    definition: Optional[str]
    # This is required by the standard, but not always filled in real data
    bezug: str | None
    status: Annotated[Status, StatusEncoding]
    gueltig_ab: Annotated[date | None, xmlstruct.Value("gueltigAb")]
    gueltig_bis: Annotated[date | None, xmlstruct.Value("gueltigbis")]
    fachlicher_ersteller: Annotated[str | None, xmlstruct.Value("fachlicherErsteller")]
    versionshinweis: str | None
    freigabedatum: date | None
    veroeffentlichungsdatum: date | None


@dataclass(slots=True)
class Regel(AllgemeineAngaben):
    script: str


@dataclass(slots=True)
class Schema(AllgemeineAngaben):
    hilfetext: Optional[str]
    ableitungsmodifikationen_struktur: Annotated[
        AbleitungsmodifikationenStruktur,
        xmlstruct.Value("ableitungsmodifikationenStruktur"),
        AbleitungsmodifikationenStrukturEncoding,
    ]
    ableitungsmodifikationen_repraesentation: Annotated[
        AbleitungsmodifikationenRepraesentation,
        xmlstruct.Value("ableitungsmodifikationenRepraesentation"),
        AbleitungsmodifikationenRepraesentationEncoding,
    ]
    regel: list[Regel]
    struktur: list[Struktur]


@dataclass(slots=True)
class GenericodeIdentification:
    canonicalIdentification: Annotated[
        str, xmlstruct.Value("canonicalIdentification"), xmlstruct.Encodings.Token
    ]
    version: Annotated[str, xmlstruct.Encodings.Token]
    canonical_version_uri: Annotated[
        str, xmlstruct.Value("canonicalVersionUri"), xmlstruct.Encodings.Token
    ]


@dataclass(slots=True)
class CodelisteReferenz:
    identifikation: ElementIdentifikation
    genericode_identification: Annotated[
        GenericodeIdentification, xmlstruct.Value("genericodeIdentification")
    ]


@dataclass(slots=True)
class Datenfeld(AllgemeineAngaben):
    feldart: Annotated[Feldart, FeldartEncoding]
    datentyp: Annotated[Datentyp, DatentypEncoding]
    # This is required by the standard, but not always filled in real data
    praezisierung: str | None
    # This is required by the standard, but not always filled in real data
    inhalt: str | None
    codeliste_referenz: Annotated[
        CodelisteReferenz | None, xmlstruct.Value("codelisteReferenz")
    ]
    regel: list[Regel]


@dataclass(slots=True)
class Datenfeldgruppe(AllgemeineAngaben):
    regel: list[Regel]
    struktur: list[Struktur]


@dataclass(slots=True)
class SchemaMessage:
    header: MessageHeader
    stammdatenschema: Schema


XDF3_NS = "urn:xoev-de:fim:standard:xdatenfelder_2"
XDF3_SCHEMA_MESSAGE = "xdatenfelder.stammdatenschema.0102"

SchemaMessageEncoding = xmlstruct.derive(
    SchemaMessage, local_name=XDF3_SCHEMA_MESSAGE, namespace=XDF3_NS, localns=locals()
)


with open("./benchmarks/S60000011V2.1_xdf2.xml", "rb") as file:
    start = time.time()
    message = SchemaMessageEncoding.parse(file)
    end = time.time()

diff = end - start
print("parsed in", diff * 1_000, "ms")
