(function () {
  const HEIGHT_MIN = 1080;
  const HEIGHT_1440 = 1440;
  const HEIGHT_4K = 2160;

  function numberValue(value, fallback = 0) {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : fallback;
  }

  function maxHeightForMinimum(minHeight) {
    return Math.max(HEIGHT_MIN, numberValue(minHeight, HEIGHT_MIN) - 1);
  }

  function clampBoundary(value, min, max) {
    return Math.min(Math.max(Math.round(numberValue(value, min)), min), max);
  }

  function boundariesFromValues(values = {}) {
    return {
      route1080pMaxHeight: Math.round(HEIGHT_MIN * (1 + (numberValue(values.Route1080pUpperHeightTolerancePercent, 0) / 100))),
      route1440pMinHeight: Math.round(HEIGHT_1440 * (1 - (numberValue(values.Route1440pLowerHeightTolerancePercent, 0) / 100))),
      route1440pMaxHeight: Math.round(HEIGHT_1440 * (1 + (numberValue(values.Route1440pUpperHeightTolerancePercent, 0) / 100))),
      route4kMinHeight: Math.round(HEIGHT_4K * (1 - (numberValue(values.Route4KLowerHeightTolerancePercent, 0) / 100))),
    };
  }

  function valuesFromFirstBoundary(route1440pMinHeight) {
    const boundaryStart = clampBoundary(route1440pMinHeight, HEIGHT_MIN + 1, HEIGHT_1440);
    const previousEnd = boundaryStart - 1;
    return {
      Route1080pUpperHeightTolerancePercent: ((previousEnd / HEIGHT_MIN) - 1) * 100,
      Route1440pLowerHeightTolerancePercent: (1 - (boundaryStart / HEIGHT_1440)) * 100,
    };
  }

  function valuesFromSecondBoundary(route4kMinHeight) {
    const boundaryStart = clampBoundary(route4kMinHeight, HEIGHT_1440 + 1, HEIGHT_4K);
    const previousEnd = boundaryStart - 1;
    return {
      Route1440pUpperHeightTolerancePercent: ((previousEnd / HEIGHT_1440) - 1) * 100,
      Route4KLowerHeightTolerancePercent: (1 - (boundaryStart / HEIGHT_4K)) * 100,
    };
  }

  function bitrateEstimate(values, designation, bucket, height) {
      const prefix = designation === "movie" ? "Movie" : "TV";
    const ceilingKey = `${prefix}Route${bucket}MaxMbps`;
    const perPixelKey = `${prefix}Route${bucket}PerPixelRate`;
    const ceilingMbps = numberValue(values?.[ceilingKey], 0);
    const perPixelRate = numberValue(values?.[perPixelKey], 0);
    const width = height >= HEIGHT_4K ? 3840 : height >= HEIGHT_1440 ? 2560 : 1920;
    const perPixelMbps = (width * height * perPixelRate) / 1_000_000;
    return Math.min(ceilingMbps, perPixelMbps || ceilingMbps);
  }

  function formatMbps(value) {
    return `${numberValue(value, 0).toFixed(1).replace(/\.0$/, "")} Mbps`;
  }

  function targetSummary(values, designation, bucket, height) {
    return formatMbps(bitrateEstimate(values, designation, bucket, height));
  }

  function consequenceSummary(boundaries, values = {}) {
    const useBoundaries = boundaries || boundariesFromValues(values);
    const route1080pMaxHeight = useBoundaries.route1080pMaxHeight;
    const route1440pMinHeight = useBoundaries.route1440pMinHeight;
    const route1440pMaxHeight = useBoundaries.route1440pMaxHeight;
    const route4kMinHeight = useBoundaries.route4kMinHeight;
    return [
      `<= ${route1080pMaxHeight}p uses 1080p targets`,
      `${route1440pMinHeight}p-${route1440pMaxHeight}p uses 1440p targets`,
      `>= ${route4kMinHeight}p uses 4K targets`,
    ].join(". ");
  }

  function unknownHeightSummary() {
    return "Unknown-height files wait for backend ffprobe dimensions and then use the backend routing fallback for the selected library.";
  }

  window.mediaPipelineRoutePolicyModel = {
    HEIGHT_MIN,
    HEIGHT_1440,
    HEIGHT_4K,
    bitrateEstimate,
    boundariesFromValues,
    clampBoundary,
    consequenceSummary,
    formatMbps,
    maxHeightForMinimum,
    numberValue,
    targetSummary,
    unknownHeightSummary,
    valuesFromFirstBoundary,
    valuesFromSecondBoundary,
  };
})();
