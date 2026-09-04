import { FormEvent, Fragment, useEffect, useMemo, useState } from "react";
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";
import { AlertTriangle, ArrowRight, Check, CheckCircle2, ChevronRight, CircleHelp, Flame, LayoutDashboard, Loader2, LogOut, MapPin, Plus, Satellite, ShieldCheck, Sparkles, Thermometer, X } from "lucide-react";
import { api, apiError, TOKEN_KEY } from "./api";
import { isForecast } from "./types";
import type { CheckResult, EnvironmentalContext, Jurisdiction, Organization, Site, TileData } from "./types";
import { CircleMarker, GeoJSON, MapContainer, TileLayer, useMapEvents } from "react-leaflet";

const jurisdictionLabels: Record<Jurisdiction, string> = { osha_federal: "OSHA federal", cal_osha: "Cal/OSHA", uae: "UAE" };
const jurisdictionColors: Record<Jurisdiction, string> = { osha_federal: "#f09a43", cal_osha: "#69c4b6", uae: "#e88b92" };

function getStatusPolygonStyle(site: Site, result?: CheckResult) {
  if (result?.threshold_breached) {
    return { color: "#f87171", fillColor: "#f87171", fillOpacity: 0.42, weight: 3, opacity: 0.95 };
  }
  if (result) {
    return { color: "#4ade80", fillColor: "#4ade80", fillOpacity: 0.38, weight: 3, opacity: 0.95 };
  }
  return { color: "#b7bec8", fillColor: "#b7bec8", fillOpacity: 0.3, weight: 3, opacity: 0.9 };
}

function tileColor(tempF: number, threshold: number | null) {
  if (threshold == null) return "#b7bec8";
  const ratio = Math.min(1, Math.max(0, (tempF - threshold * 0.8) / (threshold * 0.2)));
  const start = ratio < 0.5 ? [74, 222, 128] : [251, 191, 36];
  const end = ratio < 0.5 ? [251, 191, 36] : [248, 113, 113];
  const localRatio = ratio < 0.5 ? ratio * 2 : (ratio - 0.5) * 2;
  const channels = start.map((channel, index) => Math.round(channel + (end[index] - channel) * localRatio));
  return `rgb(${channels.join(",")})`;
}

function getErrorMessage(error: unknown) { return apiError(error); }
function isAuthenticated() { return Boolean(localStorage.getItem(TOKEN_KEY)); }
function actionLabel(action: string | null) { return action ? action.replaceAll("_", " ") : "No mandated action"; }

function siteCenter(site: Site): [number, number] {
  const pairs: [number, number][] = [];
  const walk = (value: unknown) => {
    if (Array.isArray(value) && value.length >= 2 && typeof value[0] === "number" && typeof value[1] === "number") pairs.push([value[1], value[0]]);
    else if (Array.isArray(value)) value.forEach(walk);
    else if (value && typeof value === "object") Object.values(value).forEach(walk);
  };
  walk(site.polygon_geojson);
  if (!pairs.length) return [34.0522, -118.2437];
  return [pairs.reduce((sum, pair) => sum + pair[0], 0) / pairs.length, pairs.reduce((sum, pair) => sum + pair[1], 0) / pairs.length];
}

function MapView({ sites, selectedId, onSelect, results, tiles, tileLoading }: { sites: Site[]; selectedId?: string; onSelect?: (site: Site) => void; results?: Record<string, CheckResult>; tiles?: Record<string, TileData>; tileLoading?: boolean }) {
  const center = sites.length ? siteCenter(sites[0]) : [34.0522, -118.2437] as [number, number];
  const selectedTiles = selectedId ? tiles?.[selectedId] : undefined;
  return <div className="relative h-full min-h-[320px] overflow-hidden rounded-xl">
    <MapContainer center={center} zoom={sites.length ? 14 : 10} scrollWheelZoom touchZoom dragging doubleClickZoom keyboard zoomSnap={1} zoomDelta={1} wheelDebounceTime={120} wheelPxPerZoomLevel={180}>
      <TileLayer className="dark-map-tiles" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' />
      {sites.map((site) => {
        const position = siteCenter(site);
              const result = results?.[site.id];
        return <Fragment key={site.id}>
          {site.id === selectedId && selectedTiles ? selectedTiles.tiles.map((tile, index) => <GeoJSON key={`${site.id}-tile-${index}`} data={{ type: "Feature", properties: {}, geometry: tile.geometry } as never} style={() => ({ color: tileColor(tile.temp_f, results?.[selectedId]?.threshold_value ?? null), fillColor: tileColor(tile.temp_f, results?.[selectedId]?.threshold_value ?? null), fillOpacity: 0.5, weight: 1, opacity: 0.9 })} />) : <GeoJSON key={`${site.id}-${result?.threshold_breached ? "breached" : result ? "clear" : "pending"}`} data={site.polygon_geojson as never} style={() => getStatusPolygonStyle(site, result)} />}
          <CircleMarker center={position} radius={selectedId === site.id ? 9 : 6} pathOptions={{ color: result?.threshold_breached ? "#f87171" : result ? "#4ade80" : jurisdictionColors[site.jurisdiction], fillColor: result?.threshold_breached ? "#f87171" : result ? "#4ade80" : jurisdictionColors[site.jurisdiction], fillOpacity: .9, weight: selectedId === site.id ? 4 : 2 }} eventHandlers={{ click: () => onSelect?.(site) }} />
        </Fragment>;
      })}
    </MapContainer>
  {tileLoading && selectedId && <div className="absolute right-3 top-3 z-[1000] rounded-lg border border-white/10 bg-[#101417]/90 px-3 py-2 text-xs text-white/70">Loading tile temperatures...</div>}
    {selectedTiles && <div className="absolute bottom-3 left-3 z-[1000] rounded-lg border border-white/10 bg-[#101417]/90 px-3 py-2 text-xs text-white/70"><div className="mb-1 font-semibold text-white/85">{selectedTiles.metric_label} tiles</div><div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />below threshold<span className="h-2.5 w-2.5 rounded-full bg-amber-400" />approaching<span className="h-2.5 w-2.5 rounded-full bg-rose-400" />at/above</div></div>}
  </div>;
}

function Header() {
  const navigate = useNavigate();
  const location = useLocation();
  if (location.pathname === "/" || location.pathname === "/login" || location.pathname === "/register") return null;
  const logout = () => { if (!window.confirm("Log out of Heatline?")) return; localStorage.removeItem(TOKEN_KEY); navigate("/"); };
  return <header className="sticky top-0 z-20 border-b border-white/10 bg-[#101417]/90 px-5 py-4 backdrop-blur-md md:px-8">
    <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
      <Link to="/dashboard" className="flex items-center gap-3"><span className="grid h-9 w-9 place-items-center rounded-lg bg-amber-400 text-[#171513]"><Flame size={19} fill="currentColor" /></span><span className="font-display text-lg font-bold tracking-tight">Heatline</span></Link>
      <nav className="hidden items-center gap-6 text-sm text-white/55 md:flex"><Link className="hover:text-white" to="/dashboard">Overview</Link><span>Decision support</span></nav>
      <div className="flex items-center gap-2"><button className="button-quiet px-3 py-2" onClick={logout} title="Log out"><LogOut size={16} /><span className="hidden sm:inline">Log out</span></button></div>
    </div>
  </header>;
}

function Footer() {
  return (
    <footer className="border-t border-white/10 bg-[#0d1113]">
      <div className="mx-auto flex max-w-7xl flex-col gap-3 px-5 py-6 text-xs text-white/35 md:flex-row md:items-center md:justify-between md:px-8">
        <div>
          <p className="font-semibold text-white/60">Heatline</p>
          <p className="mt-1">
            Hyperlocal heat-compliance decision support.
          </p>
        </div>

        <div className="text-left md:text-right">
          <p>Built for FortyGuard Hackathon '26</p>
          <p className="mt-1">Powered by FortyGuard Temperature API</p>
          <p className="mt-1">© 2026 Heatline. All rights reserved.</p>
        </div>
      </div>
    </footer>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Header />
      {children}
      <Footer />
    </>
  );
}
function ProtectedRoute({ children }: { children: React.ReactNode }) { return isAuthenticated() ? <>{children}</> : <Navigate to="/login" replace />; }

function Landing() {
  const [sites, setSites] = useState<Site[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => { api.get<Site[]>("/public/sites").then((response) => setSites(response.data)).catch((requestError) => setError(getErrorMessage(requestError))).finally(() => setLoading(false)); }, []);
  // Derive compliance results from the already-returned latest_result so the
  // landing-page map polygons are coloured by status with no extra API calls.
  const landingResults = useMemo<Record<string, CheckResult>>(() => {
    const map: Record<string, CheckResult> = {};
    for (const site of sites) { if (site.latest_result) map[site.id] = site.latest_result; }
    return map;
  }, [sites]);
  return <main className="page-grid min-h-screen bg-[#101417]">
    <section className="mx-auto max-w-7xl px-5 pb-12 pt-7 md:px-8 md:pt-10">
      <nav className="flex items-center justify-between"><Link to="/" className="flex items-center gap-3"><span className="grid h-9 w-9 place-items-center rounded-lg bg-amber-400 text-[#171513]"><Flame size={19} fill="currentColor" /></span><span className="font-display text-lg font-bold">Heatline</span></Link><Link className="button-quiet px-3.5 py-2" to="/login">Sign in <ArrowRight size={15} /></Link></nav>
      <div className="grid gap-12 pb-16 pt-20 lg:grid-cols-[1.05fr_.95fr] lg:items-end lg:pt-28"><div className="fade-up"><div className="eyebrow mb-5 flex items-center gap-2"><Sparkles size={14} /> Hyperlocal safety intelligence</div><h1 className="font-display max-w-3xl text-5xl font-bold leading-[.98] tracking-[-0.045em] text-white md:text-7xl">Know when the heat changes the work.</h1><p className="mt-7 max-w-xl text-lg leading-8 text-white/55">Site-specific heat compliance decisions, powered by hyperlocal environmental intelligence.</p><div className="mt-9 flex flex-wrap gap-3"><Link className="button-primary" to="/register">Get started <ArrowRight size={17} /></Link><a className="button-quiet" href="#demo-map">Explore demo sites</a></div></div><div className="grid grid-cols-2 gap-3 text-sm text-white/60 lg:pb-2"><div className="border-l border-amber-300/50 pl-4"><strong className="font-display text-2xl text-white">01</strong><p className="mt-2">Map every site in your portfolio.</p></div><div className="border-l border-amber-300/50 pl-4"><strong className="font-display text-2xl text-white">02</strong><p className="mt-2">Turn weather signals into action.</p></div></div></div>
      <section id="demo-map" className="grid gap-4 lg:grid-cols-[1.35fr_.65fr]"><div className="panel overflow-hidden p-2"><div className="h-[380px] md:h-[480px]">{loading ? <div className="grid h-full place-items-center text-white/50"><Loader2 className="animate-spin" /> Loading demo sites</div> : <MapView sites={sites} results={landingResults} />}</div></div><div className="panel flex flex-col p-6"><div className="mb-6 flex items-start justify-between"><div><p className="eyebrow">Live footprint</p><h2 className="mt-2 font-display text-2xl font-bold text-white">Demo portfolio</h2></div><MapPin className="text-amber-300" size={21} /></div>{error ? <p className="text-sm leading-6 text-rose-200">{error}</p> : <div className="space-y-2">{sites.length ? sites.map((site) => <div key={site.id} className="flex items-center justify-between gap-3 border-b border-white/10 py-4"><div><p className="font-semibold text-white">{site.name}</p><p className="mt-1 text-xs text-white/45">{jurisdictionLabels[site.jurisdiction]}</p></div><StatusBadge result={site.latest_result ?? undefined} /></div>) : <p className="text-sm text-white/45">No public demo sites are available yet.</p>}</div>}<p className="mt-auto border-t border-white/10 pt-5 text-xs leading-5 text-white/35">Read-only preview. No live checks or paid actions are available from this page.</p></div></section>
    </section>
  </main>;
}

function AuthPage({ mode }: { mode: "login" | "register" }) {
  const navigate = useNavigate();
  const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [orgName, setOrgName] = useState(""); const [error, setError] = useState(""); const [loading, setLoading] = useState(false);
  const submit = async (event: FormEvent) => { event.preventDefault(); setError(""); setLoading(true); try { const endpoint = mode === "login" ? "/auth/login" : "/auth/register"; const body = mode === "login" ? { email, password } : { email, password, org_name: orgName }; const response = await api.post(endpoint, body); localStorage.setItem(TOKEN_KEY, response.data.access_token); navigate("/dashboard"); } catch (requestError) { setError(getErrorMessage(requestError)); } finally { setLoading(false); } };
  return <main className="page-grid grid min-h-screen place-items-center px-5 py-10"><div className="w-full max-w-md fade-up"><Link to="/" className="mb-10 flex items-center justify-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-lg bg-amber-400 text-[#171513]"><Flame size={20} fill="currentColor" /></span><span className="font-display text-xl font-bold">Heatline</span></Link><div className="panel p-7 md:p-9"><p className="eyebrow">{mode === "login" ? "Welcome back" : "Start a workspace"}</p><h1 className="mt-3 font-display text-3xl font-bold text-white">{mode === "login" ? "Sign in to Heatline" : "Create your account"}</h1><p className="mt-3 text-sm leading-6 text-white/45">{mode === "login" ? "Continue monitoring the conditions that shape your workday." : "Bring site-level heat intelligence to your safety operations."}</p><form className="mt-7 space-y-4" onSubmit={submit}>{mode === "register" && <label className="block text-sm font-semibold text-white/70">Organization name<input className="field mt-2" required value={orgName} onChange={(event) => setOrgName(event.target.value)} placeholder="Northstar Construction" /></label>}<label className="block text-sm font-semibold text-white/70">Email<input className="field mt-2" type="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" /></label><label className="block text-sm font-semibold text-white/70">Password<input className="field mt-2" type="password" required value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Your password" /></label>{error && <div className="rounded-lg border border-rose-300/20 bg-rose-300/10 p-3 text-sm text-rose-200">{error}</div>}<button className="button-primary mt-2 w-full" disabled={loading}>{loading && <Loader2 size={16} className="animate-spin" />}{mode === "login" ? "Sign in" : "Create workspace"}</button></form><p className="mt-7 text-center text-sm text-white/45">{mode === "login" ? "New to Heatline? " : "Already have an account? "}<Link className="font-semibold text-amber-300 hover:text-amber-200" to={mode === "login" ? "/register" : "/login"}>{mode === "login" ? "Get started" : "Sign in"}</Link></p></div></div></main>;
}

function StatusBadge({ result }: { result?: CheckResult }) { if (!result) return <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 px-2.5 py-1 text-xs font-semibold text-white/40"><CircleHelp size={13} /> Not yet checked</span>; return result.threshold_breached ? <span className="inline-flex items-center gap-1.5 rounded-full border border-rose-300/20 bg-rose-300/10 px-2.5 py-1 text-xs font-semibold text-rose-200"><AlertTriangle size={13} /> Action required</span> : <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-300/20 bg-emerald-300/10 px-2.5 py-1 text-xs font-semibold text-emerald-200"><CheckCircle2 size={13} /> Within threshold</span>; }

// ── Polygon sizing helpers ────────────────────────────────────────────────────
// FortyGuard enforces a minimum AOI of ~1 mi² before it will process a heatmap
// request. We target 1.5 mi² to stay comfortably above that floor:
//   Side of a 1.5 mi² square = √1.5 ≈ 1.2247 mi  →  half-side ≈ 0.6124 mi
//   1° latitude  ≈ 69.0 mi  (effectively constant)
//   1° longitude ≈ 69.0 × cos(lat°) mi  (compresses toward the poles)
// halfLat and halfLon are computed SEPARATELY so the AOI is a real-world square,
// not a rectangle. Existing DB sites keep their original geometry; only newly
// created sites get the larger polygon (known limitation).
const _MI_PER_DEG_LAT = 69.0;
function milesToLatDegrees(miles: number): number {
  return miles / _MI_PER_DEG_LAT;
}
function milesToLonDegrees(miles: number, atLatitude: number): number {
  return miles / (_MI_PER_DEG_LAT * Math.cos(atLatitude * (Math.PI / 180)));
}

function AddSiteModal({ onClose, onCreated }: { onClose: () => void; onCreated: (site: Site) => void }) {
  const [name, setName] = useState(""); const [jurisdiction, setJurisdiction] = useState<Jurisdiction>("osha_federal"); const [lat, setLat] = useState("34.0522"); const [lng, setLng] = useState("-118.2437"); const [error, setError] = useState(""); const [loading, setLoading] = useState(false);
  const submit = async (event: FormEvent) => { event.preventDefault(); setError(""); setLoading(true); const latitude = Number(lat); const longitude = Number(lng); // Target ~1.5 mi² square. half-side ≈ 0.6124 mi. lat/lon half-widths differ
    // because longitude degrees compress with cos(latitude).
    const TARGET_SQ_MI = 1.5;
    const halfMi = Math.sqrt(TARGET_SQ_MI) / 2;          // ≈ 0.6124 mi
    const halfLat = milesToLatDegrees(halfMi);             // ≈ 0.00887°  (constant)
    const halfLon = milesToLonDegrees(halfMi, latitude);   // varies with cos(lat)
    const polygon_geojson = { type: "FeatureCollection", features: [{ type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [[[longitude - halfLon, latitude - halfLat], [longitude + halfLon, latitude - halfLat], [longitude + halfLon, latitude + halfLat], [longitude - halfLon, latitude + halfLat], [longitude - halfLon, latitude - halfLat]]] } }] }; try { const response = await api.post<Site>("/sites", { name, jurisdiction, polygon_geojson }); onCreated(response.data); onClose(); } catch (requestError) { setError(getErrorMessage(requestError)); } finally { setLoading(false); } };
  return <div className="site-modal fixed inset-0 grid place-items-center bg-black/70 p-5 backdrop-blur-sm"><div className="site-modal-panel panel w-full max-w-lg bg-[#151b1d] p-6 shadow-2xl"><div className="flex items-start justify-between"><div><p className="eyebrow">Portfolio setup</p><h2 className="mt-2 font-display text-2xl font-bold text-white">Add a work site</h2></div><button className="button-quiet !rounded-full p-2" onClick={onClose} title="Close"><X size={17} /></button></div><form className="mt-6 space-y-4" onSubmit={submit}><label className="block text-sm font-semibold text-white/70">Site name<input className="field mt-2" required value={name} onChange={(event) => setName(event.target.value)} placeholder="Downtown project" /></label><label className="block text-sm font-semibold text-white/70">Jurisdiction<select className="field mt-2" value={jurisdiction} onChange={(event) => setJurisdiction(event.target.value as Jurisdiction)}><option value="osha_federal">OSHA federal</option><option value="cal_osha">Cal/OSHA</option><option value="uae">UAE</option></select></label><div className="grid gap-4 sm:grid-cols-2"><label className="block text-sm font-semibold text-white/70">Latitude<input className="field mt-2" required type="number" step="any" value={lat} onChange={(event) => setLat(event.target.value)} /></label><label className="block text-sm font-semibold text-white/70">Longitude<input className="field mt-2" required type="number" step="any" value={lng} onChange={(event) => setLng(event.target.value)} /></label></div><p className="text-xs leading-5 text-white/35">A small closed square is generated around this point for the demo. You can refine geometry later.</p>{error && <div className="rounded-lg border border-rose-300/20 bg-rose-300/10 p-3 text-sm text-rose-200">{error}</div>}<button className="button-primary w-full" disabled={loading}>{loading && <Loader2 size={16} className="animate-spin" />}Add site</button></form></div></div>;
}

function ContextPanel({ site }: { site: Site }) {
  const [context, setContext] = useState<EnvironmentalContext>(); const [loading, setLoading] = useState(false); const [error, setError] = useState("");
  const load = async () => { setLoading(true); setError(""); try { const response = await api.get<EnvironmentalContext>(`/sites/${site.id}/context`); setContext(response.data); } catch (requestError) { setError(getErrorMessage(requestError)); } finally { setLoading(false); } };
  return <div className="mt-6 border-t border-white/10 pt-6"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="eyebrow">Site context</p><h3 className="mt-1 font-display text-lg font-bold text-white">Site heat context</h3></div><button className="button-quiet px-3 py-2" onClick={load} disabled={loading}>{loading ? <Loader2 size={15} className="animate-spin" /> : <Satellite size={15} />}Load context</button></div>{error && <p className="mt-4 text-sm text-rose-200">{error}</p>}{context && <div className="mt-5 grid gap-5 md:grid-cols-2"><div>{context.satellite_image_base64 ? <img className="h-48 w-full rounded-lg object-cover" src={context.satellite_image_base64.startsWith("data:") ? context.satellite_image_base64 : `data:image/png;base64,${context.satellite_image_base64}`} alt={`Satellite context for ${site.name}`} /> : <div className="grid h-48 place-items-center rounded-lg border border-dashed border-white/15 bg-white/[0.03] text-center text-sm text-white/35"><Satellite size={22} className="mb-2" />Satellite image unavailable</div>}</div><div><p className="mb-4 text-xs leading-5 text-white/45">Estimated land cover at this site - more paved/built surface generally means less natural cooling.</p><div className="space-y-3">{Object.entries(context.segments).map(([label, value]) => <div key={label}><div className="mb-1 flex justify-between text-xs"><span className="capitalize text-white/65">{label.replaceAll("_", " ")}</span><span className="text-white/45">{value.toFixed(1)}%</span></div><div className="h-2 overflow-hidden rounded-full bg-white/10"><div className="h-full rounded-full bg-amber-300" style={{ width: `${Math.min(100, Math.max(0, value))}%` }} /></div></div>)}</div></div></div>}</div>;
}

function SiteCard({ site, result, onResult, onSelect }: { site: Site; result?: CheckResult; onResult: (result: CheckResult) => void; onSelect: () => void }) {
  const [loading, setLoading] = useState<"historical" | "forecast" | null>(null); const [error, setError] = useState("");
  const run = async (mode: "historical" | "forecast") => { setLoading(mode); setError(""); try { const response = await api.post<CheckResult>(`/sites/${site.id}/check?mode=${mode}`); onResult(response.data); } catch (requestError) { setError(getErrorMessage(requestError)); } finally { setLoading(null); } };
  const metricLabel = result?.metric_label ?? "Temperature";
  return <article className="panel p-5 transition hover:border-white/20"><button className="block w-full text-left" onClick={onSelect}><div className="flex items-start justify-between gap-3"><div><p className="font-display text-lg font-bold text-white">{site.name}</p><p className="mt-1 text-xs text-white/45">{jurisdictionLabels[site.jurisdiction]}</p></div><ChevronRight className="text-white/25" size={18} /></div><div className="mt-5"><StatusBadge result={result} />{result && <div className="mt-4 flex items-end justify-between"><div><p className="text-3xl font-bold text-white">{result.heat_index_value.toFixed(1)}°<span className="text-base font-medium text-white/40">F</span></p><p className="mt-1 text-xs text-white/40">{isForecast(result) ? `Forecast preview · ${metricLabel}` : `Based on conditions: ${result.data_as_of ?? "latest available"}`}</p></div>{result.threshold_breached && <Flame className="text-rose-300" size={24} />}</div>}</div></button><div className="mt-5 flex flex-wrap gap-2"><button className="button-primary flex-1 px-3 py-2" onClick={() => run("historical")} disabled={Boolean(loading)}>{loading === "historical" ? <Loader2 size={15} className="animate-spin" /> : <Thermometer size={15} />}Run check</button><button className="button-quiet flex-1 px-3 py-2" onClick={() => run("forecast")} disabled={Boolean(loading)}>{loading === "forecast" ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}Preview</button></div>{error && <p className="mt-3 text-xs leading-5 text-rose-200">{error}</p>}</article>;
}

function DetailPanel({ site, result, onClose }: { site: Site; result?: CheckResult; onClose: () => void }) { const forecast = result ? isForecast(result) : false; const metricLabel = result?.metric_label ?? "Temperature"; const dataAsOf = result?.data_as_of ?? "latest available"; const thresholdValue = result && "threshold_value" in result ? result.threshold_value : null; const triggerText = thresholdValue != null ? ` — trigger: ${thresholdValue.toFixed(1)}°F` : ""; return <aside className="panel p-6"><div className="flex items-start justify-between gap-3"><div><p className="eyebrow">Site detail</p><h2 className="mt-2 font-display text-2xl font-bold text-white">{site.name}</h2><p className="mt-1 text-sm text-white/45">{jurisdictionLabels[site.jurisdiction]}</p></div><button className="button-quiet !rounded-full p-2" onClick={onClose} title="Close detail"><X size={17} /></button></div>{result ? <div className="mt-7"><StatusBadge result={result} /><div className="mt-5 grid grid-cols-2 gap-3"><div className="rounded-lg bg-white/[0.04] p-4"><p className="text-xs text-white/40">{metricLabel}</p><p className="mt-1 font-display text-2xl font-bold text-white">{result.heat_index_value.toFixed(1)}°F{triggerText}</p></div><div className="rounded-lg bg-white/[0.04] p-4"><p className="text-xs text-white/40">Based on conditions</p><p className="mt-1 text-sm font-bold capitalize text-white">{dataAsOf}</p></div></div><div className="mt-5 rounded-lg border border-white/10 p-4"><p className="text-xs uppercase tracking-wider text-white/40">Mandated action</p><p className="mt-2 text-sm font-semibold capitalize text-amber-200">{actionLabel(result.action_triggered)}</p></div>{forecast && <p className="mt-3 text-xs leading-5 text-white/35">Preview only. This result is not persisted as an audited compliance decision.</p>}</div> : <div className="mt-7 rounded-lg border border-dashed border-white/15 p-5 text-sm leading-6 text-white/45">Run a check to see the threshold decision, temperature reading, and recommended action for this site.</div>}<ContextPanel site={site} /></aside>; }

function Dashboard() {
  const [sites, setSites] = useState<Site[]>([]); const [results, setResults] = useState<Record<string, CheckResult>>({}); const [tiles, setTiles] = useState<Record<string, TileData>>({}); const [selected, setSelected] = useState<Site>(); const [showAdd, setShowAdd] = useState(false); const [plan, setPlan] = useState<"trial" | "standard">("trial"); const [loading, setLoading] = useState(true); const [tilesLoading, setTilesLoading] = useState(false); const [error, setError] = useState(""); const [upgrading, setUpgrading] = useState(false); const [upgradeMessage, setUpgradeMessage] = useState("");
  useEffect(() => {
  Promise.all([
    api.get<Site[]>("/sites"),
    api.get<Organization>("/organizations/me"),
  ])
    .then(([sitesResponse, organizationResponse]) => {
      setSites(sitesResponse.data);
      setPlan(organizationResponse.data.plan);
    })
    .catch((requestError) => setError(getErrorMessage(requestError)))
    .finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    if (!selected || !results[selected.id] || tiles[selected.id]) return;
    let cancelled = false;
    setTilesLoading(true);
    api.get<TileData>(`/sites/${selected.id}/heatmap-tiles`)
      .then((response) => { if (!cancelled) setTiles((current) => ({ ...current, [selected.id]: response.data })); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setTilesLoading(false); });
    return () => { cancelled = true; };
  }, [selected, results, tiles]);
  const checkedCount = Object.keys(results).length; const breachedCount = Object.values(results).filter((result) => result.threshold_breached).length;
  const upgrade = async () => { setUpgrading(true); setError(""); setUpgradeMessage(""); try { const response = await api.post<Organization>("/organizations/upgrade"); setPlan(response.data.plan); setUpgradeMessage("Environmental context unlocked for Standard."); } catch (requestError) { setError(getErrorMessage(requestError)); } finally { setUpgrading(false); } };
  return <main className="page-grid min-h-[calc(100vh-73px)]"><div className="mx-auto max-w-7xl px-5 py-8 md:px-8"><div className="flex flex-col justify-between gap-6 md:flex-row md:items-end"><div><p className="eyebrow">Operations overview</p><h1 className="mt-2 font-display text-4xl font-bold tracking-tight text-white">Your heatline</h1><p className="mt-3 max-w-xl text-sm leading-6 text-white/45">Make the next safe decision with site-specific environmental signals.</p></div><div className="flex flex-wrap gap-2"><span className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-white/60"><ShieldCheck size={15} className="text-amber-300" /> {plan} plan</span>{plan === "trial" && <button className="button-primary px-3 py-2" onClick={upgrade} disabled={upgrading}>{upgrading && <Loader2 size={15} className="animate-spin" />}Upgrade demo plan</button>}{upgradeMessage && <span className="basis-full text-xs text-emerald-200/80">{upgradeMessage}</span>}<button className="button-primary px-3 py-2" onClick={() => setShowAdd(true)}><Plus size={16} /> Add site</button></div></div>{error && <div className="mt-6 rounded-lg border border-rose-300/20 bg-rose-300/10 p-3 text-sm text-rose-200">{error}</div>}<div className="mt-8 grid grid-cols-2 gap-3 md:grid-cols-3"><div className="panel p-4"><p className="text-xs text-white/40">Portfolio sites</p><p className="mt-2 font-display text-3xl font-bold text-white">{sites.length}</p></div><div className="panel p-4"><p className="text-xs text-white/40">Checked this session</p><p className="mt-2 font-display text-3xl font-bold text-white">{checkedCount}</p></div><div className="panel col-span-2 p-4 md:col-span-1"><p className="text-xs text-white/40">Action required</p><p className="mt-2 font-display text-3xl font-bold text-rose-200">{breachedCount}</p></div></div><div className="mt-5 grid gap-5 xl:grid-cols-[1.1fr_.9fr]"><div className="panel p-2"><div className="h-[390px] md:h-[560px]">{loading ? <div className="grid h-full place-items-center text-white/45"><Loader2 className="animate-spin" /></div> : <MapView sites={sites} selectedId={selected?.id} onSelect={setSelected} results={results} tiles={tiles} tileLoading={tilesLoading} />}</div><div className="flex flex-wrap gap-4 px-3 py-3 text-xs text-white/45"><span className="font-semibold text-white/60">Jurisdiction</span>{Object.entries(jurisdictionLabels).map(([key, label]) => <span key={key} className="flex items-center gap-1.5"><i className="h-2 w-2 rounded-full" style={{ backgroundColor: jurisdictionColors[key as Jurisdiction] }} />{label}</span>)}</div></div><div className="space-y-3">{selected ? <DetailPanel site={selected} result={results[selected.id]} onClose={() => setSelected(undefined)} /> : <div><div className="mb-3 flex items-center justify-between"><div><p className="eyebrow">Portfolio checks</p><p className="mt-1 text-sm text-white/45">Run a decision or select a site for more detail.</p></div></div>{sites.length ? sites.map((site) => <div className="mb-3" key={site.id}><SiteCard site={site} result={results[site.id]} onResult={(result) => { setResults((current) => ({ ...current, [site.id]: result })); setSelected(site); }} onSelect={() => setSelected(site)} /></div>) : <div className="panel p-7 text-center text-sm text-white/45">No sites yet. Add your first work site to begin.</div>}</div>}</div></div></div>{showAdd && <AddSiteModal onClose={() => setShowAdd(false)} onCreated={(site) => setSites((current) => [...current, site])} />}</main>;
}

export default function App() { return <BrowserRouter><Shell><Routes><Route path="/" element={<Landing />} /><Route path="/login" element={<AuthPage mode="login" />} /><Route path="/register" element={<AuthPage mode="register" />} /><Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} /><Route path="*" element={<Navigate to="/" replace />} /></Routes></Shell></BrowserRouter>; }
