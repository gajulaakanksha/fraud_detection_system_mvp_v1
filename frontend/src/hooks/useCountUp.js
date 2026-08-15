import { useEffect, useRef, useState } from "react";

// Eases from whatever the previous target was to the new one -- used to
// give stat tiles a subtle "ticking up" feel whenever the underlying data
// changes, instead of numbers just snapping to a new value.
export function useCountUp(target, duration = 700) {
  const [value, setValue] = useState(target);
  const prevTarget = useRef(target);

  useEffect(() => {
    const from = prevTarget.current;
    if (from === target) return;
    const start = performance.now();
    let frame;

    function tick(now) {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(from + (target - from) * eased);
      if (t < 1) {
        frame = requestAnimationFrame(tick);
      } else {
        prevTarget.current = target;
      }
    }

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, duration]);

  return value;
}
