import csv
from rdflib import Graph, Namespace, Literal, RDF, URIRef, RDFS, OWL
from rdflib.namespace import XSD

# ── Namespaces ────────────────────────────────────────────────────
TDWP     = Namespace("http://creon-film.org/ontology/tdwp#")
CREON    = Namespace("http://creon.org/ontology#")
DUL      = Namespace("http://www.loa-cnr.it/ontologies/DOLCE-Lite.owl#")
DC       = Namespace("http://purl.org/dc/elements/1.1/")

# ── Graph setup ───────────────────────────────────────────────────
g = Graph()
g.parse("creon_tdwp_v2.ttl", format="turtle")

g.bind("tdwp",  TDWP)
g.bind("creon", CREON)
g.bind("dul",   DUL)
g.bind("dc",    DC)

# ── Helper: resolve a string value into a URIRef or Literal ───────
def as_node(value: str):
    value = value.strip()
    if not value or value == "N/A":
        return None
    # full URI
    if value.startswith("http://") or value.startswith("https://"):
        return URIRef(value)
    # tdwp local name  :Foo
    if value.startswith(":"):
        local = value.replace(":", "", 1).strip()
        return TDWP[local]
    # creon:Foo
    if value.startswith("creon:"):
        local = value.replace("creon:", "").strip()
        return CREON[local]
    # dul:Foo
    if value.startswith("dul:"):
        local = value.replace("dul:", "").strip()
        return DUL[local]
    # plain literal
    return Literal(value)

# ── Map rdf_type strings to URIRefs ───────────────────────────────
def resolve_type(type_str: str):
    type_str = type_str.strip()
    if type_str.startswith(":"):
        return TDWP[type_str[1:]]
    if type_str.startswith("creon:"):
        return CREON[type_str[6:]]
    if type_str.startswith("dul:"):
        return DUL[type_str[4:]]
    return URIRef(type_str)

# ── Map property strings to URIRefs ───────────────────────────────
PROPERTY_MAP = {
    "hasReceptionContext":  TDWP.hasReceptionContext,
    "interpretsFruitionOf": TDWP.interpretsFruitionOf,
    "hasAudienceAgent":     TDWP.hasAudienceAgent,
    "interpretedThrough":   TDWP.interpretedThrough,
    "shiftsInterpretationOf": TDWP.shiftsInterpretationOf,
    "fromContext":          TDWP.fromContext,
    "toContext":            TDWP.toContext,
    "triggeredByPress":     TDWP.triggeredByPress,
    "continuesFrom":        TDWP.continuesFrom,
    "hasSocialDomain":      TDWP.hasSocialDomain,
    "hasFilmRole":          TDWP.hasFilmRole,
    "isSequelOf":           TDWP.isSequelOf,
    "adaptedFrom":          TDWP.adaptedFrom,
    "producedBy":           TDWP.producedBy,
    "hasDistributionChannel": TDWP.hasDistributionChannel,
    "precedesContext":      TDWP.precedesContext,
    "hasReceptionYear":     TDWP.hasReceptionYear,
    "hasBudgetUSD":         TDWP.hasBudgetUSD,
    "hasProductionYear":    TDWP.hasProductionYear,
    "hasReleaseYear":       TDWP.hasReleaseYear,
    "hasBoxOfficeUSD":      TDWP.hasBoxOfficeUSD,
    "hasDurationMinutes":   TDWP.hasDurationMinutes,
    "hasAgent_in":          CREON.hasAgent,
    "involves":             CREON.involves,
    "hasPress":             CREON.hasPress,
    "rdfs:comment":         RDFS.comment,
    "rdfs:label":           RDFS.label,
}

DATATYPE_PROPS = {
    "hasReceptionYear",
    "hasBudgetUSD",
    "hasProductionYear",
    "hasReleaseYear",
    "hasBoxOfficeUSD",
    "hasDurationMinutes",
}

YEAR_PROPS = {"hasReceptionYear", "hasProductionYear", "hasReleaseYear"}

# ── Read dataset CSV and add triples ─────────────────────────────
added = 0

with open("creon_tdwp_dataset.csv", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        uri_str  = row["individual_uri"].strip()
        type_str = row["rdf_type"].strip()
        label    = row["label"].strip()

        if not uri_str:
            continue

        # Subject
        subject = as_node(uri_str)
        if subject is None:
            continue

        # rdf:type
        rdf_type = resolve_type(type_str)
        g.add((subject, RDF.type, rdf_type))
        added += 1

        # rdfs:label
        if label:
            g.add((subject, RDFS.label, Literal(label, lang="en")))
            added += 1

        # property_N / value_N pairs (up to 4)
        for n in ["1", "2", "3", "4"]:
            prop_key  = (row.get(f"property_{n}") or "").strip()
            val_str   = (row.get(f"value_{n}") or "").strip()
            if not prop_key or not val_str:
                continue

            prop_uri = PROPERTY_MAP.get(prop_key)
            if prop_uri is None:
                print(f"  [WARN] Unknown property: {prop_key}")
                continue

            # Datatype properties → typed Literals
            if prop_key in DATATYPE_PROPS:
                if prop_key in YEAR_PROPS:
                    obj = Literal(val_str, datatype=XSD.gYear)
                elif prop_key == "rdfs:comment" or prop_key == "rdfs:label":
                    obj = Literal(val_str, lang="en")
                else:
                    try:
                        obj = Literal(int(val_str), datatype=XSD.integer)
                    except ValueError:
                        obj = Literal(val_str)
            elif prop_key in ("rdfs:comment", "rdfs:label"):
                obj = Literal(val_str, lang="en")
            else:
                obj = as_node(val_str)
                if obj is None:
                    continue

            g.add((subject, prop_uri, obj))
            added += 1

print(f"✓ Triples added from CSV: {added}")
print(f"✓ Total triples in graph: {len(g)}")

# ── Serialize populated graph ─────────────────────────────────────
output_file = "creon_tdwp_populated.ttl"
g.serialize(destination=output_file, format="turtle")
print(f"✓ Populated ontology saved to: {output_file}")

# ── Statistics ────────────────────────────────────────────────────
print("\n── Graph Statistics ─────────────────────────────────")

q_classes = """
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    SELECT (COUNT(DISTINCT ?c) AS ?n) WHERE { ?c a owl:Class . }
"""
q_individuals = """
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    SELECT (COUNT(DISTINCT ?i) AS ?n) WHERE {
        ?i a ?t . ?t a owl:Class .
        FILTER(!isBlank(?i))
    }
"""
q_obj_props = """
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    SELECT (COUNT(DISTINCT ?p) AS ?n) WHERE { ?p a owl:ObjectProperty . }
"""
q_data_props = """
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    SELECT (COUNT(DISTINCT ?p) AS ?n) WHERE { ?p a owl:DatatypeProperty . }
"""

for label, query in [
    ("Classes",            q_classes),
    ("Individuals",        q_individuals),
    ("Object properties",  q_obj_props),
    ("Datatype properties",q_data_props),
]:
    result = list(g.query(query))
    count  = result[0][0] if result else "?"
    print(f"  {label:25s}: {count}")

print(f"  {'Total triples':25s}: {len(g)}")
print("─────────────────────────────────────────────────────")