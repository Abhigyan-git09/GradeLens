import { Routes, Route } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getHealth } from './api/client'
import CommandCenter from './pages/CommandCenter'
import { Activity, AlertTriangle, Radio } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

function ModelModeIndicator({ mode }: { mode: string }) {
  const config = {
    trained: { label: 'Models Active', color: 'bg-status-stable', textColor: 'text-status-stable', bgColor: 'bg-status-stable/8' },
    partial: { label: 'Partial Models', color: 'bg-status-warning', textColor: 'text-status-warning', bgColor: 'bg-status-warning/8' },
    degraded: { label: 'Degraded Mode', color: 'bg-status-critical', textColor: 'text-status-critical', bgColor: 'bg-status-critical/8' },
  }[mode] ?? { label: 'Unknown', color: 'bg-text-muted', textColor: 'text-text-muted', bgColor: 'bg-text-muted/8' }

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium ${config.bgColor} ${config.textColor} border border-current/15`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${config.color} live-indicator`} />
      {config.label}
    </motion.div>
  )
}

function App() {
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    retry: false,
  })

  return (
    <div className="min-h-dvh bg-panel-bg text-text-primary flex flex-col">
      {/* ---- Top Navigation Bar ---- */}
      <header className="border-b border-panel-border/60 bg-panel-surface/60 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-[1920px] mx-auto px-5 md:px-8 h-14 flex items-center justify-between">
          {/* Logo & Title */}
          <div className="flex items-center gap-3">
            <motion.div
              className="w-9 h-9 rounded-xl bg-gradient-to-br from-accent/90 to-status-predicted/80 flex items-center justify-center shadow-lg shadow-accent/10"
              whileHover={{ scale: 1.05, rotate: -2 }}
              transition={{ type: 'spring', stiffness: 300, damping: 20 }}
            >
              <Activity className="w-5 h-5 text-text-inverse" strokeWidth={2.5} />
            </motion.div>
            <div>
              <h1 className="text-[0.9375rem] font-semibold tracking-tight leading-none">
                GradeLens
              </h1>
              <p className="text-[0.6875rem] text-text-muted leading-none mt-0.5 font-medium tracking-wide uppercase">
                Grade Change Intelligence
              </p>
            </div>
          </div>

          {/* Right Side Indicators */}
          <div className="flex items-center gap-3">
            <AnimatePresence mode="wait">
              {health ? (
                <ModelModeIndicator key="mode" mode={health.model_mode} />
              ) : (
                <motion.div
                  key="offline"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-status-warning/8 text-status-warning border border-status-warning/15"
                >
                  <AlertTriangle className="w-3.5 h-3.5" />
                  Backend Offline
                </motion.div>
              )}
            </AnimatePresence>

            <div className="h-4 w-px bg-panel-border/50" />

            <div className="flex items-center gap-1.5 text-xs text-text-muted">
              <Radio className="w-3 h-3" />
              <span className="data-value font-medium">v{health?.version ?? '0.1.0'}</span>
            </div>
          </div>
        </div>
      </header>

      {/* ---- Main Content ---- */}
      <main className="flex-1 max-w-[1920px] mx-auto w-full">
        <Routes>
          <Route path="/" element={<CommandCenter />} />
        </Routes>
      </main>

      {/* ---- Advisory Disclaimer Footer ---- */}
      <footer className="border-t border-panel-border/40 py-2.5 px-5">
        <p className="text-[0.6875rem] text-text-muted text-center tracking-wide">
          <span className="text-status-warning/70 font-medium">Advisory only</span>
          {' — '}GradeLens does not replace or write to any live QCS/MPC system.
          All data is synthetically generated for demonstration.
        </p>
      </footer>
    </div>
  )
}

export default App
