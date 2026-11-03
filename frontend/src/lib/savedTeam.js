// Remember which team this phone controls, so a refresh (or a closed browser)
// resumes it. We store the team id AND the private token the server gave the
// captain: the id alone is not enough to take a team over.
// Wrapped in try/catch because storage can be blocked (private windows).
const KEY = "trivia-team-v3";

export function loadTeam() {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY));
    return saved?.team_id && saved?.token ? saved : null;
  } catch {
    return null;
  }
}

export function saveTeam(team_id, token) {
  try {
    localStorage.setItem(KEY, JSON.stringify({ team_id, token }));
  } catch {
    /* ignore: the game still works, it just will not be remembered */
  }
}

export function clearTeam() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}
