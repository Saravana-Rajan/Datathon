"use client";

/**
 * HeatmapLayer — wraps Google Maps native `HeatmapLayer` from the
 * "visualization" library. The library is requested by MapPanel's
 * <APIProvider> via the `libraries=["visualization"]` option.
 *
 * Why a separate component?
 *   - Native HeatmapLayer is *not* React-aware; we manage it imperatively.
 *   - Keeping the imperative bridge isolated makes the parent declarative.
 *
 * Each incident contributes one weighted point. Weight ramps with proximity
 * to current zoom so a single FIR at city scale doesn't paint a blob.
 */

import * as React from "react";
import { useMap } from "@vis.gl/react-google-maps";
import type { CrimeMarker } from "@/types/map";

interface HeatmapLayerProps {
  incidents: CrimeMarker[];
  visible: boolean;
  /** Optional radius (px) override; default scales with marker count. */
  radius?: number;
}

export function HeatmapLayer({
  incidents,
  visible,
  radius,
}: HeatmapLayerProps): React.ReactElement | null {
  const map = useMap();
  const heatmapRef = React.useRef<google.maps.visualization.HeatmapLayer | null>(
    null
  );

  React.useEffect(() => {
    if (!map) return;

    // The visualization library is loaded by MapPanel — but we still guard so
    // we fail closed instead of throwing if a consumer mounts us without it.
    const viz = (
      google.maps as unknown as {
        visualization?: typeof google.maps.visualization;
      }
    ).visualization;
    if (!viz) {
      // eslint-disable-next-line no-console
      console.warn(
        "[HeatmapLayer] google.maps.visualization not loaded — pass libraries={['visualization']} to APIProvider."
      );
      return;
    }

    const points = incidents
      .filter(
        (i) => Number.isFinite(i.lat) && Number.isFinite(i.lng)
      )
      .map((i) => ({
        location: new google.maps.LatLng(i.lat, i.lng),
        weight: 1,
      }));

    if (!heatmapRef.current) {
      heatmapRef.current = new viz.HeatmapLayer({
        data: points,
        radius: radius ?? Math.max(18, Math.min(40, 800 / Math.max(1, points.length / 10))),
        opacity: 0.65,
        dissipating: true,
      });
    } else {
      heatmapRef.current.setData(points);
    }

    heatmapRef.current.setMap(visible ? map : null);

    return () => {
      heatmapRef.current?.setMap(null);
    };
  }, [map, incidents, visible, radius]);

  // Dispose entirely on unmount.
  React.useEffect(
    () => () => {
      heatmapRef.current?.setMap(null);
      heatmapRef.current = null;
    },
    []
  );

  return null;
}

export default HeatmapLayer;
