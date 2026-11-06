import { buzzerLabel } from "../lib/buzzer.js";

// The big round button. It only reports a press: the server decides who won.
export default function BuzzerButton({ status, state, onBuzz }) {
  function handlePress() {
    onBuzz();
    navigator.vibrate?.(60);            // small buzz on phones that support it
  }

  return (
    <button
      type="button"
      className={`buzzer ${status}`}
      disabled={status !== "open"}
      onPointerDown={handlePress}       // fires on touch, no waiting for release
    >
      {buzzerLabel(status, state)}
    </button>
  );
}
