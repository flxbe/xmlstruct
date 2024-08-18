import time
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Optional

import xmlstruct


@dataclass(slots=True)
class MessageHeader:
    nachrichtID: str
    erstellungszeitpunkt: datetime


@dataclass(slots=True, frozen=True)
class ElementIdentifikation:
    id: str
    version: str | None


@dataclass(slots=True)
class Enthaelt:
    pass


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
    beschreibung: Optional[str]
    definition: Optional[str]
    fachlicherErsteller: Optional[str]


@dataclass(slots=True)
class Schema(AllgemeineAngaben):
    hilfetext: Optional[str]
    struktur: list[Struktur]


@dataclass(slots=True)
class Datenfeld(AllgemeineAngaben):
    pass


@dataclass(slots=True)
class Datenfeldgruppe(AllgemeineAngaben):
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
    xml_content = file.read()

start = time.time()
for _ in range(10):
    message = SchemaMessageEncoding.parse(xml_content)
end = time.time()

diff = end - start

print("parsed in", diff * 1_000, "ms")


def collect_elements(
    struktur_list: list[Struktur],
    groups: dict[ElementIdentifikation, Datenfeldgruppe],
    fields: dict[ElementIdentifikation, Datenfeld],
):
    for struktur in struktur_list:
        element = struktur.enthaelt

        if isinstance(element, Datenfeld):
            fields[element.identifikation] = element
        else:
            assert isinstance(element, Datenfeldgruppe)
            groups[element.identifikation] = element
            collect_elements(element.struktur, groups, fields)


groups = {}
fields = {}
collect_elements(message.stammdatenschema.struktur, groups, fields)

print("total groups:", len(groups))
print("total fields:", len(fields))
