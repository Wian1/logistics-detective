"""Route definitions: which files each route ingests and which fields are validated.

Column aliases are matched against header cells after normalisation
(see ``normalise.header``): upper-cased, whitespace/newlines collapsed,
trailing full stops removed. When a header appears more than once in a file,
the left-most occurrence is used.
"""

from dataclasses import dataclass

BAG_ID_PATTERN = r"^K\dW\d_\d{5}_\d{4}$"

# Comparator kinds
TEXT = "text"      # case-insensitive, whitespace-normalised
DATE = "date"      # calendar date only (time of day ignored)
WEIGHT = "weight"  # exact numeric match (float storage noise removed)


@dataclass(frozen=True)
class Source:
    key: str
    label: str
    key_aliases: tuple[str, ...]
    is_reference: bool = False


@dataclass(frozen=True)
class Field:
    name: str
    kind: str
    columns: dict[str, tuple[str, ...]]  # source key -> header aliases


@dataclass(frozen=True)
class Route:
    name: str
    description: str
    sources: tuple[Source, ...]
    fields: tuple[Field, ...]
    offers_templates: bool = False  # show "download template" buttons in the app

    @property
    def reference(self) -> Source:
        return next(s for s in self.sources if s.is_reference)


IVM = Route(
    name="IVM Route",
    description="Reconciles the AHK, WIRE and LSP files.",
    sources=(
        Source("wire", "WIRE", ("BAG ID",), is_reference=True),
        Source("ahk", "AHK", ("BAG NUMBER",)),
        Source("lsp", "LSP", ("BAG NUMBER",)),
    ),
    fields=(
        Field("LOT NUMBER", TEXT, {
            "wire": ("LOT NO",),
            "ahk": ("LOT NUMBER",),
            "lsp": ("LOT NUMBER",),
        }),
        Field("OFFTAKER", TEXT, {
            "wire": ("OFFTAKER",),
            "ahk": ("CLIENT",),
            "lsp": ("OFFTAKER",),
        }),
        Field("RECEIVE DATE", DATE, {
            "wire": ("PORT WHS RECEIVED DATE",),
            "ahk": ("RECEPTION DATE",),
            "lsp": ("RECEIVE DATE (YYYY/MM/DD)", "RECEIVE DATE"),
        }),
        Field("Receiving Warehouse Weight (kg)", WEIGHT, {
            "wire": ("PORT WHS GROSS WEIGHT (KG)",),
            "ahk": ("BAGS GROSS (KG)",),  # first occurrence = reception weighing
            "lsp": (
                "RECEIVING WAREHOUSE WEIGHT (KG) (INCL. BAG WEIGHT)",
                "RECEIVING WAREHOUSE WEIGHT (KG)",
            ),
        }),
    ),
)

WITNESSING = Route(
    name="Witnessing Route",
    description="Reconciles the Warehouse and WIRE files.",
    sources=(
        Source("wire", "WIRE", ("BAG ID",), is_reference=True),
        Source("warehouse", "Warehouse", ("UNIT ID", "BAG ID")),
    ),
    fields=(
        Field("TRUCK REG", TEXT, {
            "wire": ("RECEIVED TRUCK REG",),
            "warehouse": ("RECEIVING TRUCK REG",),
        }),
        Field("MINE SEAL", TEXT, {
            "wire": ("RECEIVED KICO SEAL",),
            "warehouse": ("MINE SEAL",),
        }),
        Field("ZAMBIA WAREHOUSE GROSS WEIGHT (KG)", WEIGHT, {
            "wire": ("ZAMBIA WAREHOUSE GROSS WEIGHT (KG)",),
            "warehouse": ("RECEIVING WAREHOUSE GROSS WEIGHT (KG)",),
        }),
        Field("RECEIVED TRANSIT WAREHOUSE", TEXT, {
            "wire": ("RECEIVED TRANSIT WAREHOUSE",),
            "warehouse": ("RECEIVING WAREHOUSE",),
        }),
    ),
    offers_templates=True,
)

ROUTES = {r.name: r for r in (IVM, WITNESSING)}
