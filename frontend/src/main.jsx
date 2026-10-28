import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import Display from "./pages/Display.jsx";
import Team from "./pages/Team.jsx";
import Host from "./pages/Host.jsx";
import Bingo from "./pages/Bingo.jsx";

const path = window.location.pathname;
const Page = path.startsWith ("/host") ? Host
           : path.startsWith ("/team") ? Team
           : path.startsWith ("/bingo") ? Bingo
           : Display;

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Page />
  </StrictMode>,
)
