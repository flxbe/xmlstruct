import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, TypeVar

from xsdata.formats.dataclass.parsers import XmlParser
from xsdata.formats.dataclass.parsers.config import ParserConfig

E = TypeVar("E", bound=Enum)


@dataclass(slots=True)
class Code:
    pass
    # code: str = field(metadata={"namespace": None, "name": "code"})


@dataclass(slots=True)
class MessageHeader:
    nachrichtID: str
    erstellungszeitpunkt: str


@dataclass(slots=True, frozen=True)
class ElementIdentifikation:
    id: str
    version: str | None = field(default=None)


@dataclass(slots=True)
class Enthaelt:
    datenfeld: "Datenfeld | None" = field(default=None)
    datenfeldgruppe: "Datenfeldgruppe | None" = field(default=None)


@dataclass(slots=True)
class Struktur:
    anzahl: str
    bezug: str | None
    enthaelt: Enthaelt


@dataclass(slots=True)
class Regel:
    script: str

    identifikation: ElementIdentifikation
    name: str
    # This is required by the standard, but not always filled in real data
    status: Code

    # This is required by the standard, but not always filled in real data
    bezeichnung_einabe: str | None = field(
        default=None, metadata={"name": "bezeichnungEingabe"}
    )
    bezeichnung_ausgabe: str | None = field(
        default=None, metadata={"name": "bezeichnungAusgabe"}
    )
    beschreibung: Optional[str] = field(default=None)
    definition: Optional[str] = field(default=None)
    bezug: str | None = field(default=None)
    fachlicher_ersteller: str | None = field(
        default=None, metadata={"name": "fachlicherErsteller"}
    )
    freigabedatum: str | None = field(default=None)
    veroeffentlichungsdatum: str | None = field(default=None)
    versionshinweis: Optional[str] = field(default=None)
    gueltig_ab: str | None = field(default=None, metadata={"name": "gueltigAb"})
    gueltig_bis: str | None = field(default=None, metadata={"name": "gueltigBis"})


@dataclass(slots=True)
class Schema:
    # ableitungsmodifikationen_struktur: Annotated[
    # AbleitungsmodifikationenStruktur,
    # xmlstruct.Value("ableitungsmodifikationenStruktur"),
    # AbleitungsmodifikationenStrukturEncoding,
    # ]
    # ableitungsmodifikationen_repraesentation: Annotated[
    # AbleitungsmodifikationenRepraesentation,
    # xmlstruct.Value("ableitungsmodifikationenRepraesentation"),
    # AbleitungsmodifikationenRepraesentationEncoding,
    # ]

    identifikation: ElementIdentifikation
    name: str
    # This is required by the standard, but not always filled in real data
    status: Code

    # This is required by the standard, but not always filled in real data
    bezeichnung_einabe: str | None = field(
        default=None, metadata={"name": "bezeichnungEingabe"}
    )
    bezeichnung_ausgabe: str | None = field(
        default=None, metadata={"name": "bezeichnungAusgabe"}
    )
    beschreibung: Optional[str] = field(default=None)
    definition: Optional[str] = field(default=None)
    bezug: str | None = field(default=None)
    fachlicher_ersteller: str | None = field(
        default=None, metadata={"name": "fachlicherErsteller"}
    )
    freigabedatum: str | None = field(default=None)
    veroeffentlichungsdatum: str | None = field(default=None)
    versionshinweis: Optional[str] = field(default=None)
    gueltig_ab: str | None = field(default=None, metadata={"name": "gueltigAb"})
    gueltig_bis: str | None = field(default=None, metadata={"name": "gueltigBis"})

    hilfetext: Optional[str] = field(default=None)

    regel: list[Regel] = field(default_factory=list)
    struktur: list[Struktur] = field(default_factory=list)


@dataclass(slots=True)
class GenericodeIdentification:
    canonicalIdentification: str
    version: str
    canonicalVersionUri: str


@dataclass(slots=True)
class CodelisteReferenz:
    identifikation: ElementIdentifikation
    genericode_identification: GenericodeIdentification = field(
        metadata={"name": "genericodeIdentification"}
    )


@dataclass(slots=True)
class Datenfeld:
    # feldart: Annotated[Feldart, FeldartEncoding]
    # datentyp: Annotated[Datentyp, DatentypEncoding]

    identifikation: ElementIdentifikation
    name: str
    # This is required by the standard, but not always filled in real data
    status: Code

    # This is required by the standard, but not always filled in real data
    bezeichnung_einabe: str | None = field(
        default=None, metadata={"name": "bezeichnungEingabe"}
    )
    bezeichnung_ausgabe: str | None = field(
        default=None, metadata={"name": "bezeichnungAusgabe"}
    )
    beschreibung: Optional[str] = field(default=None)
    definition: Optional[str] = field(default=None)
    bezug: str | None = field(default=None)
    fachlicher_ersteller: str | None = field(
        default=None, metadata={"name": "fachlicherErsteller"}
    )
    freigabedatum: str | None = field(default=None)
    veroeffentlichungsdatum: str | None = field(default=None)
    versionshinweis: Optional[str] = field(default=None)
    gueltig_ab: str | None = field(default=None, metadata={"name": "gueltigAb"})
    gueltig_bis: str | None = field(default=None, metadata={"name": "gueltigBis"})

    # This is required by the standard, but not always filled in real data
    praezisierung: str | None = field(default=None)
    # This is required by the standard, but not always filled in real data
    inhalt: str | None = field(default=None)
    codeliste_referenz: CodelisteReferenz | None = field(
        default=None, metadata={"name": "codelisteReferenz"}
    )

    regel: list[Regel] = field(default_factory=list)


@dataclass(slots=True)
class Datenfeldgruppe:
    identifikation: ElementIdentifikation
    name: str
    # This is required by the standard, but not always filled in real data
    status: Code

    # This is required by the standard, but not always filled in real data
    bezeichnung_einabe: str | None = field(
        default=None, metadata={"name": "bezeichnungEingabe"}
    )
    bezeichnung_ausgabe: str | None = field(
        default=None, metadata={"name": "bezeichnungAusgabe"}
    )
    beschreibung: Optional[str] = field(default=None)
    definition: Optional[str] = field(default=None)
    bezug: str | None = field(default=None)
    fachlicher_ersteller: str | None = field(
        default=None, metadata={"name": "fachlicherErsteller"}
    )
    freigabedatum: str | None = field(default=None)
    veroeffentlichungsdatum: str | None = field(default=None)
    versionshinweis: Optional[str] = field(default=None)
    gueltig_ab: str | None = field(default=None, metadata={"name": "gueltigAb"})
    gueltig_bis: str | None = field(default=None, metadata={"name": "gueltigBis"})

    regel: list[Regel] = field(default_factory=list)
    struktur: list[Struktur] = field(default_factory=list)


XDF3_NS = "urn:xoev-de:fim:standard:xdatenfelder_2"
XDF3_SCHEMA_MESSAGE = "xdatenfelder.stammdatenschema.0102"


@dataclass(slots=True)
class SchemaMessage:
    class Meta:
        name = XDF3_SCHEMA_MESSAGE
        namespace = XDF3_NS

    header: MessageHeader
    stammdatenschema: Schema


parser = XmlParser()

with open("./benchmarks/S60000011V2.1_xdf2.xml", "rb") as file:
    parser = XmlParser(
        ParserConfig(fail_on_unknown_properties=False, fail_on_unknown_attributes=False)
    )

    start = time.time()
    message = parser.parse(file, SchemaMessage)
    end = time.time()

diff = end - start
print("parsed in", diff * 1_000, "ms")
