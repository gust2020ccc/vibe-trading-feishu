import { useState, useEffect, useCallback } from 'react'
import { Play, Beaker, TrendingUp, TrendingDown, BarChart3 } from 'lucide-react'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts'
import {
  Card, CardHeader, Button, Badge, Select, Input, Loading, EmptyState,
  useToast, fmtDate, fmtPct, fmtNum,
} from '../components/ui'
import { backtestApi, strategyApi } from '../lib/api'
import type { BacktestRun, BacktestTemplate, Strategy } from '../lib/types'

export default function Backtest() {
  const toast = useToast()
  const [tab, setTab] = useState<'run' | 'history'>('run')
  const [strategies, setStrategies] = useState<Strategy[]>([])
  const [templates, setTemplates] = useState<BacktestTemplate[]>([])
  const [runs, setRuns] = useState<BacktestRun[]>([])
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [selectedRun, setSelectedRun] = useState<BacktestRun | null>(null)

  // Form state
  const [strategyId, setStrategyId] = useState('')
  const [templateId, setTemplateId] = useState('')
  const [symbols, setSymbols] = useState('BTC/USDT')
  const [startDate, setStartDate] = useState('2024-01-01')
  const [endDate, setEndDate] = useState('2024-12-31')
  const [initialCapital, setInitialCapital] = useState('10000')
  const [params, setParams] = useState('{}')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [stratRes, tplRes, runRes] = await Promise.allSettled([
        strategyApi.list(),
        strategyApi.templates(),
        backtestApi.runs(20),
      ])
      if (stratRes.status === 'fulfilled') setStrategies(Array.isArray(stratRes.value) ? stratRes.value : stratRes.value?.items || [])
      if (tplRes.status === 'fulfilled') setTemplates(Array.isArray(tplRes.value) ? tplRes.value : tplRes.value?.items || [])
      if (runRes.status === 'fulfilled') setRuns(runRes.value?.runs || runRes.value || [])
    } catch (e: any) {
      toast(e.message, 'error')
    }
    setLoading(false)
  }, [toast])

  useEffect(() => { load() }, [load])

  const handleRun = async () => {
    if (!strategyId && !templateId) {
      toast('请选择策略或模板', 'error')
      return
    }
    setRunning(true)
    try {
      let parsedParams = {}
      try { parsedParams = JSON.parse(params) } catch { toast('参数 JSON 格式错误', 'error'); setRunning(false); return }
      const res = await backtestApi.run({
        strategy_id: strategyId || undefined,
        template_id: templateId || undefined,
        symbols: symbols.split(',').map((s) => s.trim()).filter(Boolean),
        start_date: startDate,
        end_date: endDate,
        initial_capital: parseFloat(initialCapital) || 10000,
        parameters: parsedParams,
      })
      toast('回测已启动', 'success')
      setTab('history')
      load()
      if (res?.run_id) {
        // Try to fetch the run details
        setTimeout(async () => {
          try {
            const updatedRuns = await backtestApi.runs(20)
            const newRuns = updatedRuns?.runs || updatedRuns || []
            setRuns(newRuns)
            const found = newRuns.find((r: BacktestRun) => r.run_id === res.run_id)
            if (found) setSelectedRun(found)
          } catch {}
        }, 3000)
      }
    } catch (e: any) {
      toast(e.message, 'error')
    }
    setRunning(false)
  }

  if (loading) return <Loading text="加载回测数据..." />

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Tabs */}
      <div className="flex gap-1 bg-surface rounded-lg p-1 w-fit">
        <button className={`px-4 py-1.5 rounded-md text-sm transition-all ${tab === 'run' ? 'bg-accent text-white' : 'text-slate-400 hover:text-slate-200'}`} onClick={() => setTab('run')}>
          <Play className="w-3.5 h-3.5 inline mr-1.5" /> 新建回测
        </button>
        <button className={`px-4 py-1.5 rounded-md text-sm transition-all ${tab === 'history' ? 'bg-accent text-white' : 'text-slate-400 hover:text-slate-200'}`} onClick={() => setTab('history')}>
          <BarChart3 className="w-3.5 h-3.5 inline mr-1.5" /> 回测历史
        </button>
      </div>

      {tab === 'run' ? (
        <div className="grid md:grid-cols-3 gap-6">
          {/* Config form */}
          <Card className="md:col-span-1">
            <CardHeader title="回测配置" />
            <div className="p-5 space-y-4">
              <Select label="选择策略" value={strategyId} onChange={(e) => { setStrategyId(e.target.value); setTemplateId('') }}>
                <option value="">— 选择已有策略 —</option>
                {strategies.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </Select>
              <div className="text-center text-xs text-slate-600">— 或 —</div>
              <Select label="选择模板" value={templateId} onChange={(e) => { setTemplateId(e.target.value); setStrategyId('') }}>
                <option value="">— 选择系统模板 —</option>
                {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </Select>
              <Input label="交易标的（逗号分隔）" value={symbols} onChange={(e) => setSymbols(e.target.value)} placeholder="BTC/USDT,ETH/USDT" />
              <div className="grid grid-cols-2 gap-3">
                <Input label="开始日期" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
                <Input label="结束日期" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
              </div>
              <Input label="初始资金" type="number" value={initialCapital} onChange={(e) => setInitialCapital(e.target.value)} />
              <div>
                <label className="block text-xs text-slate-400 mb-1.5 font-medium">策略参数 (JSON)</label>
                <textarea
                  className="w-full px-3 py-2 bg-[#0a0d12] border border-border rounded-lg text-sm font-mono text-slate-300 focus:outline-none focus:border-accent resize-vertical"
                  rows={4}
                  value={params}
                  onChange={(e) => setParams(e.target.value)}
                  spellCheck={false}
                />
              </div>
              <Button onClick={handleRun} disabled={running} className="w-full">
                {running ? <><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin inline mr-1.5" /> 运行中...</> : <><Play className="w-4 h-4 inline mr-1.5" /> 开始回测</>}
              </Button>
            </div>
          </Card>

          {/* Quick info */}
          <div className="md:col-span-2 space-y-4">
            <Card className="p-6">
              <h3 className="text-sm font-semibold text-slate-300 mb-3">回测说明</h3>
              <div className="space-y-3 text-sm text-slate-400">
                <p>1. 选择已有策略或系统模板作为回测策略</p>
                <p>2. 设置交易标的、回测时间范围和初始资金</p>
                <p>3. 可选：通过 JSON 格式调整策略参数</p>
                <p>4. 点击「开始回测」后，结果将出现在回测历史中</p>
              </div>
              <div className="mt-4 grid grid-cols-3 gap-3">
                <div className="bg-surface2 rounded-lg p-3 text-center">
                  <div className="text-lg font-bold text-accent-light">{strategies.length}</div>
                  <div className="text-xs text-slate-500">可用策略</div>
                </div>
                <div className="bg-surface2 rounded-lg p-3 text-center">
                  <div className="text-lg font-bold text-cyan-400">{templates.length}</div>
                  <div className="text-xs text-slate-500">系统模板</div>
                </div>
                <div className="bg-surface2 rounded-lg p-3 text-center">
                  <div className="text-lg font-bold text-green-400">{runs.length}</div>
                  <div className="text-xs text-slate-500">历史回测</div>
                </div>
              </div>
            </Card>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Run detail */}
          {selectedRun && selectedRun.metrics && (
            <RunDetail run={selectedRun} onClose={() => setSelectedRun(null)} />
          )}
          {/* History list */}
          <Card>
            <CardHeader title="回测记录" />
            {runs.length === 0 ? (
              <EmptyState icon={<Beaker className="w-12 h-12" />} title="暂无回测记录" subtitle="在「新建回测」标签页运行你的第一次回测" />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="text-left">
                      <th className="px-4 py-3 text-xs uppercase text-slate-500 font-medium">策略</th>
                      <th className="px-4 py-3 text-xs uppercase text-slate-500 font-medium">状态</th>
                      <th className="px-4 py-3 text-xs uppercase text-slate-500 font-medium">总收益</th>
                      <th className="px-4 py-3 text-xs uppercase text-slate-500 font-medium">夏普比率</th>
                      <th className="px-4 py-3 text-xs uppercase text-slate-500 font-medium">最大回撤</th>
                      <th className="px-4 py-3 text-xs uppercase text-slate-500 font-medium">胜率</th>
                      <th className="px-4 py-3 text-xs uppercase text-slate-500 font-medium">时间</th>
                      <th className="px-4 py-3 text-xs uppercase text-slate-500 font-medium text-right">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((r) => (
                      <tr key={r.run_id} className="border-t border-border hover:bg-surface2/50">
                        <td className="px-4 py-3 text-sm font-medium">{r.strategy_name || r.run_id.slice(0, 8)}</td>
                        <td className="px-4 py-3">
                          <Badge color={r.status === 'completed' ? 'green' : r.status === 'running' ? 'blue' : r.status === 'failed' ? 'red' : 'gray'}>
                            {r.status}
                          </Badge>
                        </td>
                        <td className="px-4 py-3">
                          {r.metrics?.total_return !== undefined ? (
                            <span className={`text-sm font-semibold ${r.metrics.total_return >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                              {r.metrics.total_return >= 0 ? '+' : ''}{fmtPct(r.metrics.total_return)}
                            </span>
                          ) : <span className="text-slate-600">-</span>}
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-400">{r.metrics?.sharpe_ratio?.toFixed(2) || '-'}</td>
                        <td className="px-4 py-3 text-sm text-red-400">{r.metrics?.max_drawdown !== undefined ? fmtPct(r.metrics.max_drawdown) : '-'}</td>
                        <td className="px-4 py-3 text-sm text-slate-400">{r.metrics?.win_rate !== undefined ? fmtPct(r.metrics.win_rate) : '-'}</td>
                        <td className="px-4 py-3 text-sm text-slate-500">{fmtDate(r.created_at)}</td>
                        <td className="px-4 py-3 text-right">
                          {r.status === 'completed' && r.metrics && (
                            <Button size="sm" variant="ghost" onClick={() => setSelectedRun(r)}>详情</Button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  )
}

function RunDetail({ run, onClose }: { run: BacktestRun; onClose: () => void }) {
  const m = run.metrics!
  const metrics = [
    { label: '总收益', value: fmtPct(m.total_return), color: (m.total_return || 0) >= 0 ? 'text-green-400' : 'text-red-400', icon: m.total_return && m.total_return >= 0 ? TrendingUp : TrendingDown },
    { label: '年化收益', value: fmtPct(m.annualized_return), color: 'text-accent-light', icon: TrendingUp },
    { label: '夏普比率', value: m.sharpe_ratio?.toFixed(2) || '-', color: 'text-cyan-400', icon: BarChart3 },
    { label: '最大回撤', value: fmtPct(m.max_drawdown), color: 'text-red-400', icon: TrendingDown },
    { label: '胜率', value: fmtPct(m.win_rate), color: 'text-green-400', icon: BarChart3 },
    { label: '总交易数', value: fmtNum(m.total_trades), color: 'text-slate-300', icon: BarChart3 },
  ]

  return (
    <Card>
      <CardHeader title={`回测详情 · ${run.strategy_name || run.run_id.slice(0, 8)}`} action={<Button size="sm" variant="ghost" onClick={onClose}>关闭</Button>} />
      <div className="p-5">
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-5">
          {metrics.map((metric) => (
            <div key={metric.label} className="bg-surface2 rounded-lg p-3 text-center">
              <metric.icon className={`w-4 h-4 mx-auto mb-1.5 ${metric.color}`} />
              <div className={`text-lg font-bold ${metric.color}`}>{metric.value}</div>
              <div className="text-xs text-slate-500 mt-0.5">{metric.label}</div>
            </div>
          ))}
        </div>
        <div className="bg-surface2 rounded-lg p-4">
          <div className="text-sm font-medium text-slate-300 mb-3">权益曲线</div>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={[]}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a3548" />
              <XAxis dataKey="date" stroke="#5a6580" fontSize={11} />
              <YAxis stroke="#5a6580" fontSize={11} />
              <Tooltip contentStyle={{ background: '#111827', border: '1px solid #2a3548', borderRadius: '8px' }} />
              <Line type="monotone" dataKey="equity" stroke="#6366f1" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
          <p className="text-xs text-slate-600 text-center mt-2">权益曲线数据将在回测完成后显示</p>
        </div>
      </div>
    </Card>
  )
}
