const PATHS = {
  check: "M4 12.5 9 17l11-11",
  eye: "M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z|M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z",
  shield: "M12 2 4 5v6c0 5 3.4 8.9 8 10 4.6-1.1 8-5 8-10V5l-8-3Z",
  flag: "M5 3v18|M5 4h11l-2.5 4L16 12H5",
  x: "m5 5 14 14|m19 5-14 14",
  pause: "M7 4h3v16H7z|M14 4h3v16h-3z",
  grid: "M4 4h7v7H4z|M13 4h7v7h-7z|M4 13h7v7H4z|M13 13h7v7h-7z",
  activity: "M3 12h4l3 8 4-16 3 8h4",
  file: "M6 2h9l5 5v15H6z|M14 2v6h6",
  logout: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4|M16 17l5-5-5-5|M21 12H9",
  chevronDown: "m6 9 6 6 6-6",
  search: "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16Z|m21 21-4.3-4.3",
  download: "M12 3v13|m6 11 6 6 6-6|M4 21h16",
  alert: "M12 3 2 20h20L12 3Z|M12 10v5|M12 18h.01",
  sun: "M12 3v2|M12 19v2|M5 5l1.4 1.4|M17.6 17.6 19 19|M3 12h2|M19 12h2|M5 19l1.4-1.4|M17.6 6.4 19 5|M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z",
  moon: "M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z",
  sparkle: "M12 3v5|M12 16v5|M3 12h5|M16 12h5|m6.5 6.5 2 2|m15.5 6.5-2 2|m6.5 17.5 2-2|m15.5 17.5-2-2",
  chevronRight: "m9 6 6 6-6 6",
  arrowRight: "M5 12h14|m13 6 6 6-6 6",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z|M12 7v5l3.5 2",
  percent: "m5 19 14-14|M7.5 9a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z|M16.5 20a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z",
  mail: "M4 6h16v12H4z|m4 7 8 6 8-6",
  lock: "M6 11V7a6 6 0 0 1 12 0v4|M5 11h14v10H5z",
  zap: "M13 2 4 14h7l-1 8 10-12h-7l1-8Z",
  trendingUp: "m3 17 6-6 4 4 8-8|M17 7h4v4",
  info: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z|M12 8h.01|M11 11.5h1.2v5.5",
};

export default function Icon({ name, size = 16, color = "currentColor", strokeWidth = 1.8, className }) {
  const spec = PATHS[name];
  if (!spec) return null;
  const segments = spec.split("|");
  const fillIcons = new Set(["shield"]);
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {segments.map((d, i) => (
        <path key={i} d={d} fill={fillIcons.has(name) ? color : "none"} fillOpacity={fillIcons.has(name) ? 0.15 : 0} />
      ))}
    </svg>
  );
}
