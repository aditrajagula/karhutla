import { StrictMode, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { LandingPage } from './components/landing/LandingPage.tsx'

function Root() {
  const [entered, setEntered] = useState<boolean>(false)
  return entered ? <App /> : <LandingPage onEnter={() => setEntered(true)} />
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
)
