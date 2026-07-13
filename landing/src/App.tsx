import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Index } from './pages/Index'
import { Scan } from './pages/Scan'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Index />} />
        <Route path="/scan" element={<Scan />} />
      </Routes>
    </BrowserRouter>
  )
}
