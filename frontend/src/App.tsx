import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { RequireAuth } from './components/layout/RequireAuth'
import { Dashboard } from './pages/Dashboard'
import { History } from './pages/History'
import { Login } from './pages/Login'
import { PlanTrip } from './pages/PlanTrip'
import { SignUp } from './pages/SignUp'
import { TripResult } from './pages/TripResult'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<SignUp />} />
        <Route
          path="/app"
          element={
            <RequireAuth>
              <AppShell />
            </RequireAuth>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="plan" element={<PlanTrip />} />
          <Route path="history" element={<History />} />
          <Route path="trips/:tripId" element={<TripResult />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
