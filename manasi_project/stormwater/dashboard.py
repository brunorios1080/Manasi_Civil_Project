"""Standalone Plotly dashboard: inline data, JavaScript, and styles."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from plotly.offline import get_plotlyjs


def json_safe_frame(frame):
    return json.loads(frame.to_json(orient="records", double_precision=12))


def sampled_indices(data, dt, capacity, fraction):
    n = len(data["controlled_m3_s"])
    early_end = min(n, int(3 * 3600 / dt))
    indices = set(range(0, early_end, max(1, round(30 / dt))))
    indices.update(range(early_end, n, max(1, round(300 / dt))))
    indices.update((0, n - 1))
    downstream = data["controlled_m3_s"] + data["overflow_m3_s"]
    for sequence in (downstream, data["controlled_m3_s"], data["overflow_m3_s"], data["storage_m3"][1:]):
        peak = int(np.argmax(sequence))
        indices.update(range(max(0, peak - 1), min(n, peak + 2)))
    overflowing = np.flatnonzero(data["overflow_m3_s"] > 0)
    if len(overflowing):
        for point in (int(overflowing[0]), int(overflowing[-1])):
            indices.update(range(max(0, point - 1), min(n, point + 2)))
    above = np.flatnonzero(data["storage_m3"][1:] >= capacity * fraction)
    if len(above):
        crossing = int(above[-1])
        indices.update(range(max(0, crossing - 1), min(n, crossing + 3)))
    return np.asarray(sorted(indices), dtype=int)


def build_dashboard(root, config, cases, baselines, selection):
    root = Path(root)
    payload = {"config": config, "selection": selection, "cases": {}, "events": {}}
    for row in json_safe_frame(cases):
        key = row["event_id"] + "__" + row["design_id"]
        with np.load(root / "results/timeseries" / (key + ".npz")) as data:
            dt = row["dt_s"]
            idx = sampled_indices(data, dt, row["capacity_m3"], config["drawdown_fraction"])
            series = {
                "flow_time_h": np.round((idx + 0.5) * dt / 3600, 8).tolist(),
                "storage_time_h": np.round((np.r_[-1, idx] + 1) * dt / 3600, 8).tolist(),
                "controlled_l_s": np.round(data["controlled_m3_s"][idx] * 1000, 7).tolist(),
                "overflow_l_s": np.round(data["overflow_m3_s"][idx] * 1000, 7).tolist(),
                "depth_m": np.round(data["storage_m3"][np.r_[0, idx + 1]] / config["basin_area_m2"], 8).tolist(),
            }
            payload["cases"][key] = {"metrics": row, "series": series}
            if row["event_id"] not in payload["events"]:
                # Preserve the full active inflow and rainfall record. Their tail
                # is much shorter than basin drainage and needs no decimation.
                base = (data["parking_inflow_m3"] + data["direct_rain_m3"]) / dt * 1000
                nz = np.flatnonzero(base)
                end = min(len(base), (int(nz[-1]) + 3) if len(nz) else 2)
                rain_end = min(len(base), int(np.ceil(config["rainfall_duration_min"] * 60 / dt)) + 1)
                baseline_row = json_safe_frame(baselines[baselines.event_id == row["event_id"]])[0]
                payload["events"][row["event_id"]] = {
                    "metrics": baseline_row,
                    "flow_time_h": np.round((np.arange(end) + .5) * dt / 3600, 8).tolist(),
                    "baseline_l_s": np.round(base[:end], 7).tolist(),
                    "rain_time_h": np.round((np.arange(rain_end) + .5) * dt / 3600, 8).tolist(),
                    "rain_mm_h": np.round(data["rain_mm"][:rain_end] / dt * 3600, 7).tolist(),
                }
    data_json = json.dumps(payload, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")
    template = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Offline stormwater detention design comparison for a hypothetical parking lot.">
<title>Stormwater | Detention Design Study</title><link rel="icon" href="data:,">
<style>
:root{color-scheme:light;--ink:#163640;--muted:#596f75;--teal:#117c77;--paper:#f4f6f4;--line:#dce5e0}
*{box-sizing:border-box}body{margin:0;background:var(--paper);font-family:system-ui,-apple-system,sans-serif;color:var(--ink)}
header{background:var(--ink);color:white;padding:36px max(5vw,20px) 30px}.eyebrow{font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#9dd8c6}
h1{font-size:clamp(28px,4vw,43px);font-weight:650;letter-spacing:-1.4px;margin:9px 0 10px}header p{max-width:850px;color:#d7e5e1;line-height:1.6;margin:0}
main{max-width:1440px;margin:auto;padding:24px 5vw 45px}.recommendation{border-left:4px solid var(--teal);background:#e6f1eb;padding:15px 20px;line-height:1.65;border-radius:0 8px 8px 0}
.controls{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin:24px 0}label{display:block;font-size:12px;font-weight:650;margin:0 0 6px;letter-spacing:.2px}
select{width:100%;font:inherit;color:var(--ink);background:white;border:1px solid #b7c9c1;border-radius:7px;padding:12px;min-height:46px}select:focus,button:focus{outline:3px solid #8cd4b9;outline-offset:2px}
.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.metric{background:white;border:1px solid var(--line);padding:19px;border-radius:10px}.metric strong{display:block;font-size:30px;letter-spacing:-.8px;margin:6px 0}.metric span{font-size:12px;color:var(--muted)}
.panel{background:white;border:1px solid var(--line);border-radius:12px;margin-top:22px;overflow:hidden}.paneltop{padding:18px 22px 8px;display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap}.paneltop h2{font-size:18px;margin:0}button{background:#edf4ef;border:1px solid #c7d9ce;color:var(--ink);padding:8px 12px;border-radius:6px;cursor:pointer;font:inherit;font-size:12px;margin-left:4px}button.active{background:var(--teal);color:white}
#chart{height:680px;width:100%}.caption{font-size:12px;line-height:1.7;color:var(--muted);padding:0 22px 20px}.status{font-size:13px;margin:14px 0 0;line-height:1.6}.pass{color:#126b48}.fail{color:#984b19}
.notes{display:grid;grid-template-columns:1fr 1fr;gap:28px;margin-top:25px;font-size:13px;line-height:1.8}.notes h2{font-size:15px;margin:0 0 7px}.notes p{margin:0}footer{font-size:12px;margin-top:28px;padding-top:20px;border-top:1px solid var(--line);color:var(--muted)}
@media(max-width:760px){.controls,.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.notes{grid-template-columns:1fr}main{padding:20px 15px}#chart{height:660px}.metric{padding:13px}.metric strong{font-size:25px}}
</style></head><body>
<header><div class="eyebrow">Conceptual engineering · synthetic storms · works offline</div><h1>Where does the peak go?</h1><p>A parking-lot detention study: compare storage and outlet size, follow the rainfall through the basin, and see how a smaller discharge peak becomes a longer drainage tail.</p></header>
<main><div class="recommendation" id="recommendation"></div>
<div class="controls">
<div><label for="rain">Event rainfall</label><select id="rain"></select></div>
<div><label for="shape">Rainfall distribution</label><select id="shape"></select></div>
<div><label for="capacity">Storage capacity</label><select id="capacity"></select></div>
<div><label for="outlet">Square outlet opening</label><select id="outlet"></select></div>
</div>
<div class="metrics" aria-live="polite">
<div class="metric"><span>PEAK REDUCTION</span><strong id="reduction">—</strong><span id="peak">downstream peak</span></div>
<div class="metric"><span>MAXIMUM STORAGE</span><strong id="storage">—</strong><span id="depth">water depth</span></div>
<div class="metric"><span>OVERFLOW VOLUME</span><strong id="overflow">—</strong><span>included in downstream discharge</span></div>
<div class="metric"><span>DRAWDOWN AFTER RAIN</span><strong id="drawdown">—</strong><span id="threshold">to below 1% of capacity</span></div>
</div><p class="status" id="status" aria-live="polite"></p>
<div class="panel"><div class="paneltop"><h2 id="case-title">Rainfall, downstream flow, and basin depth</h2><div><button id="event-window" class="active">First 3 hours</button><button id="full-window">Full drainage</button></div></div><div id="chart" role="img" aria-label="Interactive rainfall, discharge, and water depth plots"></div><div class="caption" id="caption"></div></div>
<div class="notes"><div><h2>One comparison point, one water balance</h2><p id="balance-note"></p></div><div><h2>What this study establishes</h2><p id="scope-note"></p></div></div>
<footer>Numerical outputs, workbook checks, reference ordinates, and the complete method are included in the accompanying project files. Display curves are sampled for size while retaining their peaks, overflow transitions, and drainage threshold crossing. All metrics use the full numerical record.</footer>
</main><script>__PLOTLY__</script><script id="project-data" type="application/json">__DATA__</script>
<script>
"use strict";
const PROJECT=JSON.parse(document.getElementById('project-data').textContent);
const cfg=PROJECT.config, sel=PROJECT.selection, $=id=>document.getElementById(id);
window.STORMWATER_PROJECT=PROJECT;
const pretty=s=>s.replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());
const number=(x,n=1)=>x==null?'Not reached':(Math.abs(Number(x))<1e-9?0:Number(x)).toFixed(n);
function options(id, items){items.forEach(([value,label])=>{const o=document.createElement('option');o.value=value;o.textContent=label;$(id).append(o);});}
options('rain',cfg.rainfall_depths_mm.map(x=>[x,`${x} mm · ${cfg.rainfall_duration_min} minutes`]));
options('shape',Object.keys(cfg.rainfall_weights).map(x=>[x,pretty(x)]));
options('capacity',[['baseline','Baseline · no detention'],...cfg.storage_depths_m.map(x=>[x,`${number(x*cfg.basin_area_m2,0)} m³ · ${number(x,2)} m depth`])]);
options('outlet',cfg.outlet_sides_mm.map(x=>[x,`${x} × ${x} mm`]));
$('rain').value=cfg.design_rainfall_mm;$('capacity').value=sel.selected?sel.selected.storage_depth_m:cfg.storage_depths_m.at(-1);$('outlet').value=sel.selected?sel.selected.outlet_side_mm:cfg.outlet_sides_mm.at(-1);
$('recommendation').textContent=sel.selected?`Selected tested design: ${number(sel.selected.capacity_m3,0)} m³, ${number(sel.selected.storage_depth_m,2)} m modeled depth, and a ${sel.selected.outlet_side_mm} × ${sel.selected.outlet_side_mm} mm outlet. It satisfies all three objectives across the ${cfg.design_rainfall_mm} mm storm shapes.`:'No tested design satisfies all objectives. Explore the limiting scenarios below.';
$('scope-note').textContent=`The ${cfg.minimum_peak_reduction_pct}% peak-reduction and ${cfg.drawdown_limit_h}-hour drainage targets are educational objectives. The ${cfg.parking_area_m2+cfg.basin_area_m2} m² site, rainfall patterns, lag, CN, and outlet coefficient are assumptions. This model has no basin infiltration, tailwater, freeboard, or designed spillway; its geometry is conceptual.`;
let fullWindow=false;
function selectedCase(){const eventId=`${Number($('rain').value)}mm_${$('shape').value}`;const baseline=$('capacity').value==='baseline';const key=baseline?null:`${eventId}__h${Number($('capacity').value).toFixed(3)}_o${Number($('outlet').value)}`;return {event:PROJECT.events[eventId],record:key?PROJECT.cases[key]:null,baseline};}
function render(){
 const {event,record,baseline}=selectedCase();const b=event.metrics,m=record?.metrics,s=record?.series;
 $('outlet').disabled=baseline;
 $('reduction').textContent=baseline?'0.0%':`${number(m.peak_reduction_pct)}%`;
 $('peak').textContent=`${number((baseline?b.baseline_peak_m3_s:m.peak_downstream_m3_s)*1000,2)} L/s downstream peak`;
 $('storage').textContent=baseline?'0.0 m³':`${number(m.maximum_storage_m3)} m³`;
 $('depth').textContent=baseline?'no storage in baseline':`${number(m.maximum_depth_m,3)} m maximum water depth`;
 $('overflow').textContent=baseline?'N/A':`${number(m.overflow_m3,3)} m³`;
 $('drawdown').textContent=baseline?'N/A':m.drawdown_h_after_rain==null?'Not reached':`${number(m.drawdown_h_after_rain,2)} h`;
 $('threshold').textContent=baseline?'direct discharge':`to below ${number(cfg.drawdown_fraction*m.capacity_m3,2)} m³, without rebound`;
 $('status').className='status '+(baseline?'':m.all_pass?'pass':'fail');
 $('status').textContent=baseline?'Baseline: parking runoff plus direct rainfall on the reserved footprint; no detention.':`${m.all_pass?'Meets':'Does not meet'} all three objectives for this scenario. Peak: ${m.peak_pass?'pass':'fail'} · Overflow: ${m.overflow_pass?'pass':'fail'} · Drainage: ${m.drawdown_pass?'pass':'fail'}. Design selection is based on every ${cfg.design_rainfall_mm} mm shape.`;
 $('caption').textContent=`${pretty(b.shape)}, ${b.rainfall_mm} mm. Full numerical step: ${number(b.dt_s,4).replace(/0+$/,'').replace(/\.$/,'')} s. ${baseline?'Baseline peak at '+number(b.baseline_time_to_peak_min,2):'Downstream peak at '+number(m.time_to_peak_min,2)} minutes after rainfall starts. Discharge is an interval-average flow; storage is an end-of-step state. Use the legend to hide or show curves.`;
 $('balance-note').textContent=`This event supplies ${number(b.parking_runoff_m3,3)} m³ of parking runoff and ${number(b.direct_rain_m3,3)} m³ of footprint rainfall: ${number(b.total_inflow_m3,3)} m³ in total. ${baseline?'All of it discharges directly.':`By ${number(m.horizon_h,1)} hours, ${number(m.total_discharge_m3,3)} m³ has discharged and ${number(m.residual_storage_m3,3)} m³ remains in storage.`} Detention delays this volume; it does not remove it.`;
 const end=fullWindow?(m?.horizon_h||b.horizon_h):3;
 const line=(name,x,y,color,axis,dash)=>({name,x,y,type:'scatter',mode:'lines',yaxis:axis,line:{color,width:2,dash:dash||'solid'},hovertemplate:'%{x:.3f} h<br>%{y:.3f}<extra>%{fullData.name}</extra>'});
 const rain={name:'Rainfall (mm/h)',x:event.rain_time_h,y:event.rain_mm_h,type:'bar',yaxis:'y',marker:{color:'#76b8c6'},width:b.dt_s/3600,hovertemplate:'%{x:.3f} h<br>%{y:.2f} mm/h<extra>Rainfall</extra>'};
 const baselineX=[...event.flow_time_h],baselineY=[...event.baseline_l_s];
 if(end>baselineX.at(-1)){baselineX.push(end);baselineY.push(0);}
 const traces=[rain,line('Baseline (L/s)',baselineX,baselineY,'#687a8b','y2','dot')];
 if(!baseline){traces.push(line('Downstream incl. overflow (L/s)',s.flow_time_h,s.controlled_l_s.map((q,i)=>q+s.overflow_l_s[i]),'#117c77','y2'));traces.push(line('Controlled outlet (L/s)',s.flow_time_h,s.controlled_l_s,'#4c80bf','y2','dash'));traces.push(line('Overflow (L/s)',s.flow_time_h,s.overflow_l_s,'#d57736','y2'));traces.push({...line('Water depth (m)',s.storage_time_h,s.depth_m,'#117c77','y3'),fill:'tozeroy',fillcolor:'rgba(17,124,119,0.13)'});traces.push(line('Capacity depth (m)',[0,end],[m.storage_depth_m,m.storage_depth_m],'#ad6e34','y3','dash'));}
 else traces.push(line('Water depth (m)',[0,end],[0,0],'#117c77','y3'));
 const axis={gridcolor:'#e9eeeb',zeroline:false,title:{font:{size:12}},fixedrange:false};
 const layout={margin:{l:78,r:25,t:20,b:95},paper_bgcolor:'white',plot_bgcolor:'white',font:{family:'system-ui, sans-serif',color:'#163640',size:11},hovermode:'x unified',bargap:0,
   xaxis:{...axis,title:{text:'Hours after rainfall begins'},range:[0,end],anchor:'y3'},
   yaxis:{...axis,title:{text:'Rain (mm/h)'},domain:[.83,1],autorange:'reversed'},
   yaxis2:{...axis,title:{text:'Flow (L/s)'},domain:[.36,.76],rangemode:'tozero'},
   yaxis3:{...axis,title:{text:'Depth (m)'},domain:[0,.27],range:[0,baseline?1:Math.max(m.storage_depth_m*1.12,.1)]},
   legend:{orientation:'h',x:0,y:-.17,font:{size:10}},showlegend:true};
 $('event-window').classList.toggle('active',!fullWindow);$('full-window').classList.toggle('active',fullWindow);
 window.STORMWATER_RENDER=Plotly.react('chart',traces,layout,{responsive:true,displaylogo:false,scrollZoom:false,toImageButtonOptions:{format:'png',filename:'stormwater_scenario',scale:2}});
 return window.STORMWATER_RENDER;
}
window.stormwaterRender=render;
for(const id of ['rain','shape','capacity','outlet'])$(id).addEventListener('change',render);
$('event-window').addEventListener('click',()=>{fullWindow=false;render()});$('full-window').addEventListener('click',()=>{fullWindow=true;render()});render();
</script></body></html>'''
    (root / "stormwater_dashboard.html").write_text(template.replace("__PLOTLY__", get_plotlyjs()).replace("__DATA__", data_json))
    return {"candidate_cases": len(payload["cases"]), "baseline_events": len(payload["events"]),
            "bytes": (root / "stormwater_dashboard.html").stat().st_size}
