"""Publication figures and dimensioned, code-native conceptual drawings."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd

INK, TEAL, BLUE, ORANGE = "#163640", "#117c77", "#687f99", "#ca773c"


def configure():
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
        "axes.labelcolor": INK, "text.color": INK, "axes.edgecolor": "#9eb2ac",
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": "#e6ede8", "grid.linewidth": .6,
        "savefig.dpi": 180, "svg.fonttype": "none"})


def load_series(root, row):
    return np.load(Path(root) / "results/timeseries" / f'{row.event_id}__{row.design_id}.npz')


def build_figures(root, config, cases, selection, sensitivity):
    configure()
    root = Path(root)
    out = root / "results/figures"
    out.mkdir(parents=True, exist_ok=True)
    winner = selection["selected"]
    if winner is None:
        identity = cases.sort_values(["capacity_m3", "outlet_side_mm"]).iloc[-1].design_id
    else:
        identity = winner["design_id"]
    selected = cases[cases.design_id == identity]
    shapes = list(config["rainfall_weights"])
    fig, axes = plt.subplots(3, len(shapes), figsize=(10.8, 6.4), sharex=True, squeeze=False)
    for j, shape in enumerate(shapes):
        row = selected[(selected["shape"] == shape) & np.isclose(selected.rainfall_mm, config["design_rainfall_mm"])].iloc[0]
        with load_series(root, row) as data:
            dt = row.dt_s
            stop = min(len(data["rain_mm"]), int(3 * 3600 / dt))
            # Exact block rainfall, mass-normalized event hydrograph, and routed states.
            t = (np.arange(stop) + .5) * dt / 3600
            rain = data["rain_mm"][:stop] / dt * 3600
            axes[0, j].fill_between(t, rain, color="#91c6cf", step="mid")
            axes[0, j].invert_yaxis()
            base = (data["parking_inflow_m3"][:stop] + data["direct_rain_m3"][:stop]) / dt * 1000
            down = (data["controlled_m3_s"][:stop] + data["overflow_m3_s"][:stop]) * 1000
            axes[1, j].plot(t, base, color=BLUE, lw=1.6, ls="--", label="Baseline")
            axes[1, j].plot(t, down, color=TEAL, lw=2, label="Detention downstream")
            axes[1, j].text(.97, .92, f"{row.peak_reduction_pct:.2f}% peak reduction", ha="right", va="top", transform=axes[1,j].transAxes, fontsize=8)
            edges = np.arange(stop + 1) * dt / 3600
            h = data["storage_m3"][:stop+1] / config["basin_area_m2"]
            axes[2, j].plot(edges, h, color=TEAL, lw=1.8)
            axes[2, j].fill_between(edges, h, color=TEAL, alpha=.12)
            axes[2, j].axhline(row.storage_depth_m, color=ORANGE, ls="--", lw=1)
            axes[2, j].set_ylim(0, row.storage_depth_m * 1.18)
            axes[2, j].set_xlabel("Hours after rainfall starts")
            axes[0, j].set_title(shape.replace("_", " ").title(), weight="bold", fontsize=11)
            axes[2, j].text(.97, .90, f"Maximum {row.maximum_depth_m:.3f} m", ha="right", va="top", transform=axes[2,j].transAxes, fontsize=8)
    axes[0, 0].set_ylabel("Rainfall (mm/h)")
    axes[1, 0].set_ylabel("Discharge (L/s)")
    axes[2, 0].set_ylabel("Basin depth (m)")
    axes[1, 0].legend(loc="center right", fontsize=7, frameon=False)
    for ax in axes.flat: ax.set_xlim(0, 3)
    fig.suptitle(f"{config['design_rainfall_mm']:g} mm design storms | {identity}", x=.07, ha="left", weight="bold", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, .96), h_pad=1.1)
    for ext in ("pdf", "png"): fig.savefig(out / f"design_hydrographs.{ext}", bbox_inches="tight")
    plt.close(fig)

    # All 24 design alternatives, color = worst peak reduction; text = all-target pass.
    table = pd.read_csv(root / "results/design_selection.csv")
    depths, sides = sorted(config["storage_depths_m"]), sorted(config["outlet_sides_mm"])
    matrix = np.array([[table[np.isclose(table.storage_depth_m, d) & (table.outlet_side_mm == s)].worst_peak_reduction_pct.iloc[0]
                        for s in sides] for d in depths])
    fig, ax = plt.subplots(figsize=(6.9, 3.8))
    image = ax.imshow(matrix, vmin=0, vmax=100, cmap="YlGnBu", aspect="auto")
    for i, depth in enumerate(depths):
        for j, side in enumerate(sides):
            row = table[np.isclose(table.storage_depth_m, depth) & (table.outlet_side_mm == side)].iloc[0]
            label = f"{max(0,row.worst_peak_reduction_pct):.1f}%\n{'PASS' if row.all_design_storms_pass else 'FAIL'}"
            ax.text(j, i, label, ha="center", va="center", fontsize=8, color="white" if matrix[i,j] > 58 else INK)
    ax.set_xticks(range(len(sides)), [f"{s:g} mm" for s in sides])
    ax.set_yticks(range(len(depths)), [f"{d*config['basin_area_m2']:g} m³" for d in depths])
    ax.set_xlabel("Square opening side"); ax.set_ylabel("Tested capacity")
    ax.set_title("Worst peak reduction across design storm shapes", loc="left", weight="bold")
    ax.grid(False)
    fig.colorbar(image, ax=ax, label="Peak reduction (%)", fraction=.04, pad=.03)
    fig.tight_layout()
    for ext in ("pdf", "png"): fig.savefig(out / f"design_comparison.{ext}", bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.2))
    for _, row in selected[np.isclose(selected.rainfall_mm, config["design_rainfall_mm"])].iterrows():
        with load_series(root, row) as data:
            stride = max(1, int(30 / row.dt_s))
            t = np.arange(0, len(data["storage_m3"]), stride) * row.dt_s / 3600
            axes[0].plot(t, data["storage_m3"][::stride], label=row["shape"].replace("_", " "))
    axes[0].axhline(config["drawdown_fraction"] * selected.capacity_m3.iloc[0], color=ORANGE, ls="--", label="Drainage threshold")
    axes[0].set(xlim=(0, 30), xlabel="Hours after rainfall starts", ylabel="Storage (m³)", title="Long recession: temporary storage")
    axes[0].legend(fontsize=7, frameon=False)
    for shape in shapes:
        sub = selected[selected["shape"] == shape].sort_values("rainfall_mm")
        axes[1].plot(sub.rainfall_mm, sub.overflow_m3, marker="o", label=shape.replace("_", " "))
    axes[1].set(xlabel="Synthetic storm depth (mm)", ylabel="Overflow volume (m³)", title="Performance outside the design event")
    axes[1].legend(fontsize=7, frameon=False)
    fig.tight_layout()
    for ext in ("pdf", "png"): fig.savefig(out / f"drawdown_and_overflow.{ext}", bbox_inches="tight")
    plt.close(fig)
    return {"figure_files": [str(p.relative_to(root)) for p in sorted(out.glob("*"))]}


class DXF:
    """Portable ASCII R12 primitives; one drawing unit equals one metre."""
    def __init__(self):
        self.entities = []
    def line(self, x1, y1, x2, y2, layer="GEOMETRY"):
        self.entities.extend([(0,"LINE"),(8,layer),(10,x1),(20,y1),(30,0),(11,x2),(21,y2),(31,0)])
    def rect(self, x, y, w, h, layer="GEOMETRY"):
        for x1,y1,x2,y2 in ((x,y,x+w,y),(x+w,y,x+w,y+h),(x+w,y+h,x,y+h),(x,y+h,x,y)):
            self.line(x1,y1,x2,y2,layer)
    def text(self, x, y, value, height=1.2, layer="NOTES"):
        self.entities.extend([(0,"TEXT"),(8,layer),(10,x),(20,y),(30,0),(40,height),(1,value),(50,0)])
    def arrow(self,x1,y1,x2,y2):
        self.line(x1,y1,x2,y2,"FLOW")
        delta = np.array([x2-x1,y2-y1],dtype=float)
        delta /= np.linalg.norm(delta)
        perp = np.array([-delta[1],delta[0]])
        for sign in (-1,1):
            end = np.array([x2,y2])-delta*1.8+sign*perp*.7
            self.line(x2,y2,*end,"FLOW")
    def save(self, path):
        pairs=[(0,"SECTION"),(2,"HEADER"),(9,"$ACADVER"),(1,"AC1009"),
               (9,"$LUNITS"),(70,2),(9,"$LUPREC"),(70,3),(0,"ENDSEC"),
               (0,"SECTION"),(2,"TABLES"),(0,"TABLE"),(2,"LAYER"),(70,4)]
        for name,color in (("GEOMETRY",7),("FLOW",4),("DIMENSIONS",3),("NOTES",2)):
            pairs.extend([(0,"LAYER"),(2,name),(70,0),(62,color),(6,"CONTINUOUS")])
        pairs.extend([(0,"ENDTAB"),(0,"ENDSEC"),(0,"SECTION"),(2,"ENTITIES")])
        pairs.extend(self.entities)
        pairs.extend([(0,"ENDSEC"),(0,"EOF")])
        Path(path).write_text("".join(f"{code}\n{value}\n" for code,value in pairs), encoding="ascii")


def build_drawings(root, config, cases, selection):
    configure()
    root = Path(root)
    selected = selection["selected"]
    depth = selected["storage_depth_m"] if selected else config["storage_depths_m"][-1]
    side = selected["outlet_side_mm"] if selected else config["outlet_sides_mm"][-1]
    capacity = config["basin_area_m2"] * depth
    pl, pw = config["parking_length_m"], config["parking_width_m"]
    bl, bw = config["basin_length_m"], config["basin_width_m"]
    fig = plt.figure(figsize=(11.7,8.3))
    ax = fig.add_axes([.06,.35,.9,.55])
    ax.set_aspect("equal"); ax.axis("off")
    ax.add_patch(Rectangle((0,0),pl,pw,facecolor="#eef1f1",edgecolor=INK,lw=1.5))
    ax.add_patch(Rectangle((pl,0),bl,bw,facecolor="#d9eee3",edgecolor=TEAL,lw=1.6))
    ax.text(pl/2,pw*.73,f"HYPOTHETICAL PARKING LOT\n{pl:g} × {pw:g} m = {config['parking_area_m2']:g} m²\nCN {config['curve_number']:g} · assumed lag {config['lag_min']:g} min",ha="center",va="center",fontsize=12,linespacing=1.7)
    ax.text(pl+bl/2,bw/2,"BASIN\n"+f"{config['basin_area_m2']:g} m²",ha="center",va="center",fontsize=8,weight="bold")
    ax.plot([pl+bl*.88,pl+bl*.88],[-1,bw+1],color=INK,lw=.7,ls="--")
    ax.text(pl+bl*.88,bw+1.5,"A",ha="center",fontsize=7)
    ax.text(pl+bl*.88,-2.4,"A",ha="center",fontsize=7)
    for begin in ((pl*.12,pw*.4),(pl*.42,pw*.32),(pl*.73,pw*.43)):
        ax.annotate("",xy=(pl,bw/2),xytext=begin,arrowprops={"arrowstyle":"->","color":TEAL,"lw":1.8})
    ax.plot(pl,bw/2,"o",color=TEAL,ms=4)
    ax.annotate("One catchment outlet\n(conveyance not designed)",xy=(pl,bw/2),xytext=(pl*.53,-10),fontsize=8,
                arrowprops={"arrowstyle":"-","color":INK})
    ax.annotate("",xy=(pl+bl+13,bw/2),xytext=(pl+bl,bw/2),arrowprops={"arrowstyle":"->","color":TEAL,"lw":2})
    ax.text(pl+bl+1,bw+4,"Common downstream\ncomparison point",fontsize=8)
    def horizontal(x1,x2,y,label):
        ax.annotate("",xy=(x1,y),xytext=(x2,y),arrowprops={"arrowstyle":"|-|","lw":.8,"color":INK})
        ax.text((x1+x2)/2,y+1.3,label,ha="center",fontsize=9)
    horizontal(0,pl,pw+5,f"{pl:g} m")
    horizontal(pl,pl+bl,-5,f"{bl:g} m")
    ax.annotate("",xy=(-5,0),xytext=(-5,pw),arrowprops={"arrowstyle":"|-|","lw":.8,"color":INK})
    ax.text(-7,pw/2,f"{pw:g} m",rotation=90,ha="right",va="center")
    ax.annotate("",xy=(pl+bl+3,0),xytext=(pl+bl+3,bw),arrowprops={"arrowstyle":"|-|","lw":.8,"color":INK})
    ax.text(pl+bl+4,bw*.78,f"{bw:g} m",va="center")
    ax.annotate("N",xy=(pl+bl+9,pw*.65),xytext=(pl+bl+9,pw*.43),ha="center",weight="bold",arrowprops={"arrowstyle":"->","lw":1.3})
    ax.text(0,-16,"FLOW ARROWS ARE SCHEMATIC · No surveyed grades or pipe network assumed",fontsize=8)
    ax.set_xlim(-11,pl+bl+23); ax.set_ylim(-19,pw+13)
    section = fig.add_axes([.08,.115,.52,.18])
    section.set_aspect("equal");section.axis("off")
    section.add_patch(Rectangle((0,0),bw,depth,facecolor="#e4f1eb",edgecolor=INK,lw=1.2))
    section.plot([0,bw],[depth,depth],ls="--",color=ORANGE,lw=1)
    section.plot([bw,bw],[0,side/1000],color=TEAL,lw=4)
    section.annotate("",xy=(bw+1,.03),xytext=(bw,.03),arrowprops={"arrowstyle":"->","color":TEAL})
    section.annotate(f"{depth:g} m modeled storage depth",xy=(bw*.72,depth),xytext=(bw*.40,depth+1),fontsize=8,
                     arrowprops={"arrowstyle":"-","color":INK})
    section.annotate(f"{side:g} × {side:g} mm opening\nsill at floor; free discharge",xy=(bw,side/2000),xytext=(bw*.70,-1.2),fontsize=8,
                     arrowprops={"arrowstyle":"-","color":INK})
    section.text(bw*.12,-.42,f"{bw:g} m section width",fontsize=9)
    section.text(0,depth+1.55,"A–A  |  IDEALIZED CONSTANT-AREA SECTION",fontsize=10,weight="bold")
    section.set_xlim(-.3,bw+2);section.set_ylim(-1.6,depth+2)
    fig.text(.64,.245,f"{capacity:g} m³ nominal capacity\nV = A h; constant area {config['basin_area_m2']:g} m²",fontsize=11,weight="bold",linespacing=1.6)
    fig.text(.64,.135,"Vertical boundaries are a storage idealization.\nSide slopes, freeboard, structural walls, tailwater,\nand a physical spillway have not been designed.\nOverflow is an accounting boundary only.",fontsize=9,linespacing=1.6)
    fig.text(.06,.95,"PARKING-LOT DETENTION  /  CONCEPTUAL LAYOUT",fontsize=17,weight="bold")
    fig.text(.06,.915,f"Same {config['parking_area_m2']+config['basin_area_m2']:g} m² contributing study area in all cases · Dimensions in metres · No construction design",fontsize=9)
    fig.text(.06,.05,"DRAWING 01  ·  Diagrammatic plan and section; use labeled dimensions. CAD units: 1 drawing unit = 1 metre.",fontsize=8)
    for name in ("site_plan.svg", "site_plan.pdf"):
        fig.savefig(root / name, metadata={"Title": "Conceptual parking-lot detention layout"})
    fig.savefig(root / "results/figures/site_plan.png")
    plt.close(fig)

    dxf = DXF()
    dxf.rect(0,0,pl,pw); dxf.rect(pl,0,bl,bw)
    dxf.text(0,pw+13,"PARKING-LOT DETENTION - CONCEPTUAL LAYOUT",2)
    dxf.text(0,pw+9,"UNITS: 1 drawing unit = 1 metre. Import as metres.",1.2)
    dxf.text(pl*.15,pw*.73,f"PARKING LOT {pl:g} x {pw:g} m = {config['parking_area_m2']:g} m2",1.7)
    dxf.text(pl+1,bw*.6,"BASIN",1.2)
    dxf.text(pl+1,bw*.3,f"{config['basin_area_m2']:g} m2",1.2)
    dxf.line(pl+bl*.88,-1,pl+bl*.88,bw+1,"DIMENSIONS")
    dxf.text(pl+bl*.88,bw+1.5,"A",.8,"DIMENSIONS")
    dxf.text(pl+bl*.88,-2.4,"A",.8,"DIMENSIONS")
    for begin in ((pl*.12,pw*.4),(pl*.42,pw*.32),(pl*.73,pw*.43)):
        dxf.arrow(*begin,pl,bw/2)
    dxf.arrow(pl+bl,bw/2,pl+bl+12,bw/2)
    dxf.text(pl+bl+2,bw+3,"DOWNSTREAM POINT",1)
    dxf.text(pl-20,-9,"ONE CATCHMENT OUTLET",1)
    dxf.line(pl,bw/2,pl-3,-7,"NOTES")
    def dim(x1,y1,x2,y2,tx,ty,label):
        dxf.line(x1,y1,x2,y2,"DIMENSIONS")
        for x,y in ((x1,y1),(x2,y2)):
            dxf.line(x-.5,y-.5,x+.5,y+.5,"DIMENSIONS")
        dxf.text(tx,ty,label,1.2,"DIMENSIONS")
    dim(0,pw+4,pl,pw+4,pl/2-3,pw+5,f"{pl:g} m")
    dim(-4,0,-4,pw,-11,pw/2,f"{pw:g} m")
    dim(pl,-4,pl+bl,-4,pl+bl/2-2,-3,f"{bl:g} m")
    dim(pl+bl+3,0,pl+bl+3,bw,pl+bl+4,bw*.78,f"{bw:g} m")
    sy=-25
    dxf.rect(0,sy,bw,depth)
    dxf.line(bw,sy,bw,sy+side/1000,"FLOW")
    dxf.text(0,sy+5,"SECTION A-A - TRUE GEOMETRY, NO VERTICAL EXAGGERATION",1)
    dxf.text(0,sy+3,f"V = A h; A = {config['basin_area_m2']:g} m2; CAPACITY = {capacity:g} m3",1)
    dim(0,sy-1.5,bw,sy-1.5,bw/2-2,sy-3,f"{bw:g} m")
    dim(-.8,sy,-.8,sy+depth,-8,sy,f"{depth:g} m depth")
    dxf.text(bw+3,sy,f"{side:g} x {side:g} mm floor opening",.9)
    dxf.line(bw,sy+side/2000,bw+2.5,sy+.4,"NOTES")
    dxf.text(0,sy-7,"CONSTANT-AREA IDEALIZATION; NO SIDE SLOPES OR FREEBOARD DESIGNED",1)
    dxf.text(0,sy-10,"FLOW ARROWS SCHEMATIC; NO SURVEY, GRADES, PIPES, TAILWATER OR SPILLWAY DESIGN",1)
    dxf.text(0,sy-13,"ASSISTANT-GENERATED CAD. MANASI'S OWN EDITS HAVE NOT BEEN RECORDED.",1)
    dxf.save(root / "site_plan.dxf")
    return {"capacity_m3": capacity,"depth_m":depth,"outlet_side_mm":side,
            "cad_format":"ASCII DXF R12","cad_units":"1 unit = 1 metre; specify metres on import",
            "section_geometry":"True coordinates in DXF; SVG/PDF plan and section use separate scales"}
