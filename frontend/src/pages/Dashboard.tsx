import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { CandlestickChart, FlaskConical, Beaker, Store, TrendingUp, Bot, ArrowRight, Activity } from 'lucide-react'
import { Card, CardHeader, Loading, Badge, fmtDate, fmtPct } from '../components/ui'
import { strategyApi, factorApi, backtestApi, marketApi } from '../lib/api'
import type { Strategy, BacktestRun, MarketplaceStats } from '../lib/types'

interface DashData {
  strategies: Strategy[]
  factors: any[]
  runs: BacktestRun[]
  marketStats: MarketplaceStats | null
}

export default function Dashboard() {
  const [data, setData] = useState<DashData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.allSettled([
      strategyApi.list({ limit: '5' }),
      factorApi.list({ limit: '5' }),
      backtestApi.runs(5),
      marketApi.stats(),
    ]).then(([stratRes, factorRes, runRes, marketRes]) => {
      setData({
        strategies: stratRes.status === 'fulfilled' ? (Array.isArray(stratRes.value) ? stratRes.value : stratRes.value?.items || []) : [],
        factors: factorRes.status === 'fulfilled' ? (Array.isArray(factorRes.value) ? factorRes.value : factorRes.value?.items || []) : [],
        runs: runRes.status === 'fulfilled' ? (runRes.value?.runs || runRes.value || []) : [],
        marketStats: marketRes.status === 'fulfilled' ? marketRes.value : null,
      })
      setLoading(false)
    })
  }, [])

  if (loading) return <Loading text="加载仪表盘..." />

  const stats = [
    { label: '策略总数', value: data?.strategies.length || 0, icon: CandlestickChart, color: 'text-accent-light', link: '/strategies' },
    { label: '因子总数', value: data?.factors.length || 0, icon: FlaskConical, color: 'text-cyan-400', link: '/factors' },
    { label: '回测记录', value: data?.runs.length || 0, icon: Beaker, color: 'text-green-400', link: '/backtest' },
    { label: '市场发布', value: data?.marketStats?.strategies?.published_count || 0, icon: Store, color: 'text-orange-400', link: '/marketplace' },
  ]

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-surface via-surface2 to-surface border border-border p-6">
        <div className="relative z-10">
          <h2 className="text-2xl font-bold mb-1">AI Native 量化交易平台</h2>
          <p className="text-sm text-slate-400">自然语言生成策略 · 可视化回测 · 策略市场共享</p>
          <div className="flex gap-3 mt-4">
            <Link to="/ai-generate" className="inline-flex items-center gap-1.5 px-4 py-2 bg-accent hover:bg-accent-light rounded-lg text-sm font-medium transition-all">
              <Bot className="w-4 h-4" /> AI 生成策略
            </Link>
            <Link to="/backtest" className="inline-flex items-center gap-1.5 px-4 py-2 border border-border hover:bg-surface2 rounded-lg text-sm font-medium transition-all">
              <Beaker className="w-4 h-4" /> 开始回测
            </Link>
          </div>
        </div>
        <div className="absolute -right-8 -top-8 w-48 h-48 bg-accent/10 rounded-full blur-3xl" />
        <div className="absolute right-20 bottom-0 w-32 h-32 bg-cyan-500/10 rounded-full blur-2xl" />
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {stats.map((s) => (
          <Link key={s.label} to={s.link}>
            <Card className="card-hover p-5">
              <div className="flex items-center justify-between mb-3">
                <s.icon className={`w-5 h-5 ${s.color}`} />
                <ArrowRight className="w-3.5 h-3.5 text-slate-600" />
              </div>
              <div className="text-2xl font-bold">{s.value}</div>
              <div className="text-xs text-slate-500 mt-0.5">{s.label}</div>
            </Card>
          </Link>
        ))}
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Recent strategies */}
        <Card>
          <CardHeader title="最近策略" action={<Link to="/strategies" className="text-xs text-accent-light hover:underline">查看全部</Link>} />
          <div className="p-2">
            {data?.strategies.length === 0 ? (
              <p className="text-center text-sm text-slate-600 py-8">暂无策略</p>
            ) : (
              data?.strategies.slice(0, 5).map((s) => (
                <Link key={s.id} to="/strategies" className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-surface2 transition-all">
                  <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center flex-shrink-0">
                    <TrendingUp className="w-4 h-4 text-accent-light" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium truncate">{s.name}</div>
                    <div className="text-xs text-slate-500">{s.category || '未分类'} · v{s.version}</div>
                  </div>
                  <Badge color={s.status === 'published' ? 'green' : s.status === 'archived' ? 'red' : 'gray'}>
                    {s.status}
                  </Badge>
                </Link>
              ))
            )}
          </div>
        </Card>

        {/* Recent backtests */}
        <Card>
          <CardHeader title="最近回测" action={<Link to="/backtest" className="text-xs text-accent-light hover:underline">查看全部</Link>} />
          <div className="p-2">
            {data?.runs.length === 0 ? (
              <p className="text-center text-sm text-slate-600 py-8">暂无回测记录</p>
            ) : (
              data?.runs.slice(0, 5).map((r) => (
                <div key={r.run_id} className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-surface2 transition-all">
                  <div className="w-8 h-8 rounded-lg bg-green-500/10 flex items-center justify-center flex-shrink-0">
                    <Activity className="w-4 h-4 text-green-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium truncate">{r.strategy_name || r.run_id.slice(0, 8)}</div>
                    <div className="text-xs text-slate-500">{fmtDate(r.created_at)}</div>
                  </div>
                  {r.metrics?.total_return !== undefined && (
                    <span className={`text-sm font-semibold ${r.metrics.total_return >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {fmtPct(r.metrics.total_return)}
                    </span>
                  )}
                </div>
              ))
            )}
          </div>
        </Card>
      </div>
    </div>
  )
}
