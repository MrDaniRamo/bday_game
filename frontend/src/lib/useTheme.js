import { useEffect } from "react";

// Applies a look to the whole page by setting <html data-theme="...">.
// index.css has one set of colors and fonts per theme:
//   "quiz"   - black stage, sticker cards, marker lettering (TV and captain
//              phones until the reveal)
//   "reveal" - 70s game-show set: blue wall, stripes, rings, marquee bulbs
//              (after the reveal, and always on the bingo and host pages)
export function useTheme(theme) {
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
}
