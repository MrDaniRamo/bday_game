// What the buzzer should look like for one team, worked out from the server state.
//   offline: no connection to the server (the server cannot hear us)
//   won:     this team buzzed first
//   lost:    another team buzzed first
//   open:    the host opened the buzzers and nobody has buzzed yet
//   locked:  waiting for the host to open the buzzers
export function buzzerStatus(state, team, connected) {
  if (!connected) return "offline";
  if (state.buzzed === team) return "won";
  if (state.buzzed) return "lost";
  if (state.buzzers_open) return "open";
  return "locked";
}

export function buzzerLabel(status, state) {
  switch (status) {
    case "open": return "BUZZ!";
    case "won": return "You buzzed!";
    case "lost": return `${state.teams[state.buzzed]?.name ?? "Another team"} was first`;
    case "offline": return "Reconnecting…";
    default: return "Wait for the question";
  }
}
