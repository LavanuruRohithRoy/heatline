export type Jurisdiction = "osha_federal" | "cal_osha" | "uae";
export type Plan = "trial" | "standard";

export interface Site {
  id: string;
  org_id: string;
  name: string;
  polygon_geojson: Record<string, unknown>;
  jurisdiction: Jurisdiction;
}

export interface HistoricalCheck {
  id: string;
  site_id: string;
  checked_at: string;
  heat_index_value: number;
  threshold_breached: boolean;
  action_triggered: string | null;
  metric_label?: string;
  data_as_of?: string;
  threshold_value?: number | null;
}

export interface ForecastCheck {
  site_id: string;
  mode: "forecast";
  forecast_for: string;
  heat_index_value: number;
  threshold_breached: boolean;
  action_triggered: string | null;
  metric_label?: string;
  data_as_of?: string;
  threshold_value?: number | null;
}

export interface EnvironmentalContext {
  site_id: string;
  segments: Record<string, number>;
  satellite_image_base64: string;
}

export interface HeatmapTile {
  geometry: Record<string, unknown>;
  temp_f: number;
}

export interface TileData {
  site_id: string;
  metric_label: string;
  tiles: HeatmapTile[];
}

export interface Organization {
  id: string;
  name: string;
  plan: Plan;
  is_public_demo: boolean;
}

export type CheckResult = HistoricalCheck | ForecastCheck;

export function isForecast(result: CheckResult): result is ForecastCheck {
  return "mode" in result && result.mode === "forecast";
}
