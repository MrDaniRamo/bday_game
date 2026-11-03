// Remember which bingo board this phone owns (id + private token), so a refresh
// resumes it. Same idea as savedTeam.js, but a different key: one phone could
// in theory be a captain AND a bingo player in different tabs.
const KEY = "trivia-board-v1";

export function loadBoard() {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY));
    return saved?.board_id && saved?.token ? saved : null;
  } catch {
    return null;
  }
}

export function saveBoard(board_id, token) {
  try {
    localStorage.setItem(KEY, JSON.stringify({ board_id, token }));
  } catch {
    /* ignore: the card still works, it just will not be remembered */
  }
}

export function clearBoard() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}
