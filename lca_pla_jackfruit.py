"""
LCA model: jackfruit-seed-starch bioplastic vs PLA (NatureWorks)
================================================================
Goal      : compare cradle-to-gate environmental impacts of bioplastics and find hotspots
Data from : (a) your rev1.pptx slides 7-9 (jackfruit seed starch + film, lab scale)
            (b) Vink et al. 2003, Polym. Degrad. Stab. 80:403-419 (PLA, Blair NE plant)
Impacts   : climate change, water use, acidification, eutrophication (per your slide 2)
Tool link : inventories are exported as CSV so they can be rebuilt in openLCA
            (Agribalyse 3.2 Core for background processes)

Every flow carries a `source` tag:
    "deck"        -> taken from your slides
    "Vink2003"    -> taken from the paper
    "DERIVED"     -> calculated from published numbers (formula in comment)
    "ASSUMPTION"  -> my placeholder; confirm or replace
Characterisation factors set to None are DATA GAPS: fill them from Agribalyse/openLCA.
Run:  python lca_pla_jackfruit.py
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

OUT_DIR = Path("lca_outputs")

# ----------------------------------------------------------------------------
# 1. DATA STRUCTURES
# ----------------------------------------------------------------------------
# compartment: technosphere | intermediate | fossil_energy | renewable_energy | emission | waste


@dataclass
class Flow:
    name: str
    amount: float
    unit: str
    kind: str          # "input" | "output"
    compartment: str
    source: str
    background: str = ""   # suggested background dataset to link in openLCA


@dataclass
class UnitProcess:
    name: str
    ref_product: str
    ref_amount: float
    ref_unit: str
    flows: list = field(default_factory=list)
    notes: str = ""


@dataclass
class Scenario:
    key: str
    name: str
    functional_unit: str
    fu_product: str
    fu_amount: float
    boundary: dict
    processes: list


# ----------------------------------------------------------------------------
# 2. SCENARIO A: JACKFRUIT SEED STARCH BIOPLASTIC (your lab data, rev1.pptx)
# ----------------------------------------------------------------------------
GRID = "Electricity, grid (India)"
DIST_WATER = "Water, distilled"

jackfruit = Scenario(
    key="JF",
    name="Jackfruit seed starch bioplastic film (glycerol-plasticised, casting)",
    functional_unit="1 kg of bioplastic film",
    fu_product="Bioplastic film",
    fu_amount=1.0,
    boundary={
        "type": "cradle-to-gate (lab scale)",
        "included": [
            "Jackfruit seed powder (treated as by-product, cut-off: zero upstream burden)",
            "Starch extraction (drying, grinding, centrifuge, final drying)",
            "Film casting (mixing, ultrasonic cleaning, drying)",
            "Distilled water, glycerol, grid electricity",
        ],
        "excluded": [
            "Jackfruit cultivation and fruit processing (seed is a waste/by-product)",
            "Equipment manufacture, lab building, transport of seeds (no data)",
            "Use phase and end-of-life (biodegradation not studied in the reference paper)",
        ],
        "allocation": "Cut-off for seeds. Test economic allocation as a sensitivity case.",
    },
    processes=[
        UnitProcess(
            name="Starch extraction from jackfruit seed",
            ref_product="Jackfruit seed starch", ref_amount=1.0, ref_unit="kg",
            notes="Slide 7/8. 1 kg is the reference output used for scaling, not a measured batch.",
            flows=[
                Flow("Jackfruit seed powder", 3.6, "kg", "input", "technosphere", "deck",
                     "By-product, zero burden (cut-off)"),
                Flow(DIST_WATER, 36.0, "L", "input", "technosphere", "deck",
                     "Agribalyse/ecoinvent: water, deionised"),
                Flow(GRID, 65.34, "kWh", "input", "technosphere", "deck",
                     "Agribalyse/ecoinvent: electricity, medium voltage, IN"),
                Flow("Jackfruit seed starch", 1.0, "kg", "output", "product", "deck"),
                # mass balance assumptions (not in deck)
                Flow("Seed residue (solid)", 2.6, "kg", "output", "waste",
                     "ASSUMPTION"),  # 3.6 - 1.0, ignores moisture
                Flow("Wastewater", 36.0, "L", "output", "waste",
                     "ASSUMPTION"),  # all input water leaves as wastewater
            ],
        ),
        UnitProcess(
            name="Bioplastic film casting",
            ref_product="Bioplastic film", ref_amount=0.0052, ref_unit="kg",
            notes="Slide 7/8. Basis is one lab batch of 5.2 g.",
            flows=[
                Flow("Jackfruit seed starch", 0.004, "kg", "input", "intermediate", "deck"),
                Flow("Glycerol", 0.0012, "kg", "input", "technosphere", "deck",
                     "Agribalyse/ecoinvent: glycerine"),
                Flow(DIST_WATER, 0.2, "L", "input", "technosphere", "deck",
                     "Agribalyse/ecoinvent: water, deionised"),
                Flow(GRID, 15.076, "kWh", "input", "technosphere", "deck",
                     "Agribalyse/ecoinvent: electricity, medium voltage, IN"),
                Flow("Bioplastic film", 0.0052, "kg", "output", "product", "deck"),
                Flow("Water evaporated", 0.2, "L", "output", "emission", "ASSUMPTION"),
            ],
        ),
    ],
)

# Slide 9 lists equipment but gives no power or run time. Fill these in so that
# the totals can be checked against 65.34 kWh (starch) and 15.076 kWh (film).
EQUIPMENT = {
    "Starch extraction": {  # target total = 65.34 kWh per 1 kg starch
        "Drying oven": {"power_kW": None, "hours": None},
        "Grinder": {"power_kW": None, "hours": None},
        "Fisatom 752A": {"power_kW": None, "hours": None},
        "Centrifuge": {"power_kW": None, "hours": None},
        "Final drying oven": {"power_kW": None, "hours": None},
    },
    "Bioplastic production": {  # target total = 15.076 kWh per 5.2 g film
        "Fisatom 752A": {"power_kW": None, "hours": None},
        "Ultrasonic cleaner": {"power_kW": None, "hours": None},
        "Drying oven": {"power_kW": None, "hours": None},
    },
}

# ----------------------------------------------------------------------------
# 3. SCENARIO B: PLA 1 (Vink et al. 2003, Blair, Nebraska, corn starch route)
# ----------------------------------------------------------------------------
# The paper publishes fossil energy by step (Fig. 7), not full mass balances.
# Intermediate masses are NOT published, so intermediates use a 1 kg PLA-equivalent
# basis (DATA GAP). Energy values are MJ per kg PLA.
CORN_MJ_PER_KG = 16.3          # heat of combustion of corn, Vink 2003
CORN_PER_KG_PLA = 28.4 / CORN_MJ_PER_KG   # DERIVED: ~1.74 kg corn (15.5% moisture)

pla1 = Scenario(
    key="PLA1",
    name="PLA pellets, first generation (corn, grid electricity)",
    functional_unit="1 kg of PLA pellets",
    fu_product="PLA pellets",
    fu_amount=1.0,
    boundary={
        "type": "cradle-to-pellet",
        "included": [
            "Corn growing (seed, fertiliser, fuels, irrigation, pesticides)",
            "Transport of corn to the wet mill",
            "Corn wet milling to dextrose",
            "Fermentation and purification to lactic acid",
            "Lactide formation and ring-opening polymerisation",
            "Wastewater treatment",
        ],
        "excluded": ["Use phase", "End-of-life (landfill, composting, incineration, recycling)"],
        "allocation": "Corn wet mill co-products (gluten feed, meal, germ) need an allocation "
                      "rule; the paper does not state it.",
    },
    processes=[
        UnitProcess(
            "Corn growing and transport", "Corn, 15.5% moisture", CORN_PER_KG_PLA, "kg",
            notes="Vink 2003 Fig. 7; 3.8 + 1.1 + 0.4 MJ fossil.",
            flows=[
                Flow("Fossil energy: operating supplies (farm)", 3.8, "MJ", "input", "fossil_energy", "Vink2003"),
                Flow("Fossil energy: electricity and fuels (farm)", 1.1, "MJ", "input", "fossil_energy", "Vink2003"),
                Flow("Fossil energy: transport to wet mill", 0.4, "MJ", "input", "fossil_energy", "Vink2003"),
                Flow("Renewable energy in corn feedstock", 28.4, "MJ", "input", "renewable_energy", "Vink2003"),
                Flow("Corn, 15.5% moisture", CORN_PER_KG_PLA, "kg", "output", "product", "DERIVED"),
            ],
        ),
        UnitProcess(
            "Dextrose production (corn wet mill)", "Dextrose", 1.0, "kg PLA-eq",
            notes="DATA GAP: dextrose mass per kg PLA is not published.",
            flows=[
                Flow("Corn, 15.5% moisture", CORN_PER_KG_PLA, "kg", "input", "intermediate", "DERIVED"),
                Flow("Fossil energy: operating supplies + WWT", 0.6, "MJ", "input", "fossil_energy", "Vink2003"),
                Flow("Fossil energy: electricity and fuels", 8.8, "MJ", "input", "fossil_energy", "Vink2003"),
                Flow("Dextrose", 1.0, "kg PLA-eq", "output", "product", "Vink2003"),
            ],
        ),
        UnitProcess(
            "Lactic acid production", "Lactic acid", 1.0, "kg PLA-eq",
            notes="Largest hotspot: 26.3 MJ = 49% of fossil energy.",
            flows=[
                Flow("Dextrose", 1.0, "kg PLA-eq", "input", "intermediate", "Vink2003"),
                Flow("Fossil energy: operating supplies + WWT", 11.4, "MJ", "input", "fossil_energy", "Vink2003"),
                Flow("Fossil energy: electricity and fuels", 14.9, "MJ", "input", "fossil_energy", "Vink2003"),
                Flow("Lactic acid", 1.0, "kg PLA-eq", "output", "product", "Vink2003"),
            ],
        ),
        UnitProcess(
            "Lactide and PLA production", "PLA pellets", 1.0, "kg",
            flows=[
                Flow("Lactic acid", 1.0, "kg PLA-eq", "input", "intermediate", "Vink2003"),
                Flow("Fossil energy: operating supplies + WWT", 0.4, "MJ", "input", "fossil_energy", "Vink2003"),
                Flow("Fossil energy: electricity and fuels", 12.8, "MJ", "input", "fossil_energy", "Vink2003"),
                Flow("PLA pellets", 1.0, "kg", "output", "product", "Vink2003"),
            ],
        ),
    ],
)

# Published aggregates for validation and comparison (Vink 2003, Figs. 8, 11, 12).
PLA_LITERATURE = {
    "PLA1":                         {"GFEU_MJ_per_kg": 54.1, "GWP_kgCO2e_per_kg": 1.8},
    "PLA1 + new lactic acid tech":  {"GFEU_MJ_per_kg": 48.8, "GWP_kgCO2e_per_kg": 1.2},
    "Biorefinery + grid power":     {"GFEU_MJ_per_kg": 29.2, "GWP_kgCO2e_per_kg": -0.3},
    "Biorefinery + wind (B/WP)":    {"GFEU_MJ_per_kg": 7.4,  "GWP_kgCO2e_per_kg": -1.7},
}
GER_PLA1 = 82.5  # MJ/kg, gross energy requirement

# ----------------------------------------------------------------------------
# 4. SCENARIO C: TEMPLATE for your third method (slide 2 says three methods)
# ----------------------------------------------------------------------------
method3 = Scenario(
    key="M3", name="TODO: third bioplastic route (e.g. another starch source)",
    functional_unit="1 kg of bioplastic film", fu_product="Bioplastic film", fu_amount=1.0,
    boundary={"type": "cradle-to-gate", "included": [], "excluded": [], "allocation": "TODO"},
    processes=[],   # TODO(copilot): add UnitProcess objects in the same format as above
)

# ----------------------------------------------------------------------------
# 5. CHARACTERISATION FACTORS (per unit of each technosphere flow)
# ----------------------------------------------------------------------------
# None = DATA GAP. Fill from Agribalyse 3.2 / your LCIA method in openLCA
# (e.g. EF 3.1: climate change kg CO2e, acidification mol H+ eq,
#  eutrophication freshwater kg P eq).
GRID_EF_KG_CO2E_PER_KWH = 0.75   # ASSUMPTION: rough Indian grid average; replace with
                                 # the CEA baseline or the Agribalyse/ecoinvent India dataset.
CF = {
    "Climate change (kg CO2e)": {
        GRID: GRID_EF_KG_CO2E_PER_KWH, "Jackfruit seed powder": 0.0,
        "Glycerol": None, DIST_WATER: None,
    },
    "Acidification (mol H+ eq)": {
        GRID: None, "Jackfruit seed powder": 0.0, "Glycerol": None, DIST_WATER: None,
    },
    "Eutrophication, freshwater (kg P eq)": {
        GRID: None, "Jackfruit seed powder": 0.0, "Glycerol": None, DIST_WATER: None,
    },
}

# ----------------------------------------------------------------------------
# 6. CALCULATION ENGINE
# ----------------------------------------------------------------------------


def solve(scn: Scenario) -> list[dict]:
    """Scale every unit process to deliver the functional unit."""
    producers = {p.ref_product: p for p in scn.processes}
    scale: dict[str, float] = {}

    def demand(product: str, amount: float) -> None:
        p = producers[product]
        s = amount / p.ref_amount
        scale[p.name] = scale.get(p.name, 0.0) + s
        for f in p.flows:
            if f.kind == "input" and f.compartment == "intermediate":
                demand(f.name, f.amount * s)

    demand(scn.fu_product, scn.fu_amount)
    rows = []
    for p in scn.processes:
        s = scale.get(p.name, 0.0)
        for f in p.flows:
            rows.append({
                "scenario": scn.key, "process": p.name, "flow": f.name, "kind": f.kind,
                "compartment": f.compartment, "amount": f.amount * s, "unit": f.unit,
                "source": f.source, "background": f.background,
            })
    return rows


def totals(rows: list[dict], compartments: tuple[str, ...]) -> dict[str, float]:
    out: dict[str, float] = {}
    for r in rows:
        if r["kind"] == "input" and r["compartment"] in compartments:
            out[r["flow"]] = out.get(r["flow"], 0.0) + r["amount"]
    return out


def impacts(rows: list[dict]) -> tuple[dict, dict]:
    """Impact per FU by category and by process; also returns the data gaps."""
    result = {c: {} for c in CF}
    gaps = {c: set() for c in CF}
    for r in rows:
        if r["kind"] != "input" or r["compartment"] != "technosphere":
            continue
        for cat, table in CF.items():
            factor = table.get(r["flow"])
            if factor is None:
                gaps[cat].add(r["flow"])
                continue
            result[cat][r["process"]] = result[cat].get(r["process"], 0.0) + factor * r["amount"]
    return result, gaps


def water_use_litres(rows: list[dict]) -> float:
    """Direct process water per FU (distilled water inputs). Add upstream water in openLCA."""
    return sum(r["amount"] for r in rows
               if r["kind"] == "input" and r["flow"] == DIST_WATER)


def equipment_kwh(stage: str) -> float | None:
    items = EQUIPMENT[stage].values()
    if any(i["power_kW"] is None or i["hours"] is None for i in items):
        return None
    return sum(i["power_kW"] * i["hours"] for i in items)


# ----------------------------------------------------------------------------
# 7. REPORTING
# ----------------------------------------------------------------------------


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def print_boundary(scn: Scenario) -> None:
    print(f"\n=== {scn.name} ===")
    print(f"Functional unit : {scn.functional_unit}")
    print(f"Boundary        : {scn.boundary['type']}")
    for k in ("included", "excluded"):
        print(f"  {k.capitalize()}:")
        for item in scn.boundary[k]:
            print(f"    - {item}")
    print(f"  Allocation: {scn.boundary['allocation']}")


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    summary = []

    # --- Jackfruit seed starch bioplastic
    print_boundary(jackfruit)
    rows = solve(jackfruit)
    write_csv(OUT_DIR / "inventory_JF.csv", rows)
    elec = totals(rows, ("technosphere",))
    print("\nTechnosphere inputs per 1 kg film:")
    for k, v in elec.items():
        print(f"  {k:30s} {v:12.3f}")
    res, gaps = impacts(rows)
    for cat, by_proc in res.items():
        total = sum(by_proc.values())
        print(f"\n{cat}: {total:,.1f}" + ("  (partial, see gaps)" if gaps[cat] else ""))
        for p, v in by_proc.items():
            share = 100 * v / total if total else 0
            print(f"   {p:42s} {v:12.2f}  {share:5.1f}%")
        if gaps[cat]:
            print(f"   DATA GAPS: {sorted(gaps[cat])}")
        summary.append({"scenario": "JF", "category": cat, "value": total,
                        "complete": not gaps[cat]})
    print(f"\nDirect process water: {water_use_litres(rows):.1f} L per kg film")

    # Sensitivity: lab-scale electricity is very high; test scale-up efficiency
    print("\nSensitivity, climate change vs electricity scale-up factor "
          f"(grid EF {GRID_EF_KG_CO2E_PER_KWH} kg CO2e/kWh):")
    kwh = elec[GRID]
    for f in (1.0, 0.1, 0.01, 0.001):
        print(f"   electricity x{f:<6} -> {kwh * f * GRID_EF_KG_CO2E_PER_KWH:10.2f} kg CO2e/kg (electricity only)")

    # --- PLA 1
    print_boundary(pla1)
    rows = solve(pla1)
    write_csv(OUT_DIR / "inventory_PLA1.csv", rows)
    fossil = sum(r["amount"] for r in rows if r["compartment"] == "fossil_energy")
    renew = sum(r["amount"] for r in rows if r["compartment"] == "renewable_energy")
    print(f"\nFossil energy (GFEU): {fossil:.1f} MJ/kg  (paper: {PLA_LITERATURE['PLA1']['GFEU_MJ_per_kg']})")
    print(f"Renewable energy    : {renew:.1f} MJ/kg;  GER = {fossil + renew:.1f} (paper: {GER_PLA1})")
    assert abs(fossil - 54.1) < 0.3, "fossil energy no longer matches Vink 2003"
    by_proc: dict[str, float] = {}
    for r in rows:
        if r["compartment"] == "fossil_energy":
            by_proc[r["process"]] = by_proc.get(r["process"], 0.0) + r["amount"]
    for p, v in by_proc.items():
        print(f"   {p:42s} {v:6.1f} MJ  {100 * v / fossil:5.1f}%")
    summary.append({"scenario": "PLA1", "category": "Fossil energy (MJ)", "value": fossil, "complete": True})
    print("\nLiterature benchmarks for PLA (Vink 2003):")
    for k, v in PLA_LITERATURE.items():
        print(f"   {k:30s} GFEU {v['GFEU_MJ_per_kg']:5.1f} MJ/kg   GWP {v['GWP_kgCO2e_per_kg']:5.1f} kg CO2e/kg")
        summary.append({"scenario": "PLA lit.", "category": k + " GWP", "value": v["GWP_kgCO2e_per_kg"], "complete": True})

    write_csv(OUT_DIR / "impact_summary.csv", summary)
    print(f"\nCSV files written to {OUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
