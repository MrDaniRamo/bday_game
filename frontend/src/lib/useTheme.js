import { useEffect } from "react";

// Applies a look to the whole page by setting <html data-theme="...">.
// index.css has one set of colors and fonts per theme:
//   "quiz"   - retro quiz show (TV and captain phones before the reveal)
//   "reveal" - chaotic plot-twist look (after the reveal, and always on bingo and host)
export function useTheme(theme) {
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
}
