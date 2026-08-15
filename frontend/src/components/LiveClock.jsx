import { useEffect, useState } from "react";
import "./LiveClock.css";

const DATE_FMT = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  weekday: "short",
  day: "2-digit",
  month: "short",
  year: "numeric",
});

const TIME_FMT = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: true,
});

export default function LiveClock() {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="live-clock">
      <span className="live-dot" />
      <span className="live-label">Live</span>
      <span className="live-clock-divider" />
      <span className="live-clock-date">{DATE_FMT.format(now)}</span>
      <span className="live-clock-time tabular">{TIME_FMT.format(now)} IST</span>
    </div>
  );
}
