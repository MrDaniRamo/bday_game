import { useEffect, useState } from "react";

// Turns "the buzzers reopen in N seconds" (sent by the server) into a number
// that counts down on screen. Returns null when there is nothing to count.
//
// The server sends the seconds REMAINING, not a clock time, because a phone's
// clock can differ from the server's. We add our own clock's "now" to it.
export function useCountdown(releaseIn) {
  const [seconds, setSeconds] = useState(null);

  useEffect(() => {
    if (releaseIn === null || releaseIn === undefined) {
      setSeconds(null);
      return;
    }
    const endsAt = Date.now() + releaseIn * 1000;
    const tick = () => setSeconds(Math.max(0, Math.ceil((endsAt - Date.now()) / 1000)));
    tick();
    const timer = setInterval(tick, 200);
    return () => clearInterval(timer);   // stop on a new value or when the page closes
  }, [releaseIn]);

  return seconds;
}
