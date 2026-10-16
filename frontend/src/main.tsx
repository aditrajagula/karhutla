import { StrictMode, useCallback, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './fonts.css'
import './index.css'
import App from './App.tsx'
import { LandingPage } from './components/landing/LandingPage.tsx'
import { LoginPage } from './components/login/LoginPage.tsx'
import { isLoggedIn } from './services/dummyAuth.ts'

type Route = '/' | '/login' | '/app'

const ROUTES: Route[] = ['/', '/login', '/app']

function currentRoute(): Route {
  const path = window.location.pathname.replace(/\/+$/, '') || '/'
  return (ROUTES as string[]).includes(path) ? (path as Route) : '/'
}

function Root() {
  const [route, setRoute] = useState<Route>(currentRoute)

  useEffect(() => {
    const onPop = () => setRoute(currentRoute())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  const navigate = useCallback((to: Route) => {
    window.history.pushState(null, '', to)
    setRoute(to)
  }, [])

  useEffect(() => {
    if (route === '/app' && !isLoggedIn()) navigate('/login')
  }, [route, navigate])

  if (route === '/login') return <LoginPage onLogin={() => navigate('/app')} />
  if (route === '/app') return isLoggedIn() ? <App /> : null
  return <LandingPage onEnter={() => navigate('/login')} />
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
)
