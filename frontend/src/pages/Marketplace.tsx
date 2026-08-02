import { useState, useEffect, useCallback } from 'react'
import { Search, Store, Copy, Star, Users, Download, TrendingUp } from 'lucide-react'
import {
  Card, CardHeader, Button, Badge, Loading, EmptyState, Stars,
  useToast, fmtNum,
} from '../components/ui'
import { marketApi, strategyApi } from '../lib/api'
import type { Strategy, MarketplaceStats } from '../lib/types'

export default function Marketplace() {
  const toast = useToast()
  const [strategies, setStrategies] = useState<Strategy[]>([])
  const [stats, setStats] = useState<MarketplaceStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [stratRes, statRes] = await Promise.allSettled([
        marketApi.strategies({ ...(search && { search }), ...(category && { category }) }),
        marketApi.stats(),
      ])
      if (stratRes.status === 'fulfilled') {
        setStrategies(Array.isArray(stratRes.value) ? stratRes.value : stratRes.value?.items || [])
      }
      if (statRes.status === 'fulfilled') setStats(statRes.value)
    } catch (e: any) {
      toast(e.message, 'error')
    }
    setLoading(false)
  }, [search, category, toast])

  useEffect(() => {
    const t = setTimeout(load, 300)
    return () => clearTimeout(t)
  }, [load])

  const handleClone = async (id: string) => {
    try {
      await strategyApi.clone(id)
      toast('已克隆到我的策略', 'success')
    } catch (e: any) {
      toast(e.message, 'error')
    }
  }

  const handleSubscribe = async (id: string) => {
    try {
      await strategyApi.subscribe(id)
      toast('已订阅', 'success')
      load()
    } catch (e: any) {
      toast(e.message, 'error')
    }
  }

  const handleRate = async (id: string, rating: number) => {
    try {
      await strategyApi.rate(id, rating)
      toast('评分成功', 'success')
      load()
    } catch (e: any) {
      toast(e.message, 'error')
    }
  }

  const s = stats?.strategies

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Stats banner */}
      {s && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="p-4 flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center">
              <Store className="w-5 h-5 text-green-400" />
            </div>
            <div>
              <div className="text-xl font-bold">{s.published_count}</div>
              <div className="text-xs text-slate-500">已发布策略</div>
            </div>
          </Card>
          <Card className="p-4 flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center">
              <Users className="w-5 h-5 text-accent-light" />
            </div>
            <div>
              <div className="text-xl font-bold">{s.total_subscribers}</div>
              <div className="text-xs text-slate-500">总订阅数</div>
            </div>
          </Card>
          <Card className="p-4 flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-cyan-500/10 flex items-center justify-center">
              <Download className="w-5 h-5 text-cyan-400" />
            </div>
            <div>
              <div className="text-xl font-bold">{s.total_clones}</div>
              <div className="text-xs text-slate-500">总克隆数</div>
            </div>
          </Card>
          <Card className="p-4 flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-orange-500/10 flex items-center justify-center">
              <Star className="w-5 h-5 text-orange-400" />
            </div>
            <div>
              <div className="text-xl font-bold">{s.avg_rating?.toFixed(1) || '-'}</div>
              <div className="text-xs text-slate-500">平均评分</div>
            </div>
          </Card>
        </div>
      )}

      {/* Search */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600" />
          <input
            className="w-full pl-9 pr-3 py-2 bg-surface border border-border rounded-lg text-sm placeholder-slate-600 focus:outline-none focus:border-accent"
            placeholder="搜索市场策略..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          className="px-3 py-2 bg-surface border border-border rounded-lg text-sm text-slate-300 focus:outline-none focus:border-accent"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          <option value="">全部分类</option>
          <option value="trend">趋势跟踪</option>
          <option value="mean_reversion">均值回归</option>
          <option value="momentum">动量</option>
          <option value="arbitrage">套利</option>
          <option value="custom">自定义</option>
        </select>
      </div>

      {/* Grid */}
      {loading ? (
        <Loading />
      ) : strategies.length === 0 ? (
        <Card>
          <EmptyState icon={<Store className="w-12 h-12" />} title="市场暂无策略" subtitle="发布你的策略到市场，让更多用户发现" />
        </Card>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {strategies.map((strat) => (
            <Card key={strat.id} className="card-hover p-5 flex flex-col">
              {/* Header */}
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-semibold truncate">{strat.name}</h3>
                  <div className="flex items-center gap-2 mt-1">
                    {strat.category && <Badge color="blue">{strat.category}</Badge>}
                    <span className="text-xs text-slate-600">v{strat.version}</span>
                  </div>
                </div>
                <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-accent/20 to-cyan-500/20 flex items-center justify-center flex-shrink-0">
                  <TrendingUp className="w-4 h-4 text-accent-light" />
                </div>
              </div>

              {/* Description */}
              <p className="text-xs text-slate-400 leading-relaxed mb-4 flex-1 line-clamp-3">
                {strat.market_desc || strat.description || '暂无描述'}
              </p>

              {/* Tags */}
              {strat.tags && strat.tags.length > 0 && (
                <div className="flex flex-wrap gap-1 mb-3">
                  {strat.tags.slice(0, 4).map((tag) => (
                    <span key={tag} className="px-2 py-0.5 bg-surface3 rounded text-xs text-slate-500">{tag}</span>
                  ))}
                </div>
              )}

              {/* Stats */}
              <div className="flex items-center gap-4 text-xs text-slate-500 mb-4">
                <Stars avg={strat.rating_avg || 0} count={strat.rating_count} />
                <span className="flex items-center gap-1">
                  <Users className="w-3 h-3" /> {strat.subscriber_count || 0}
                </span>
                <span className="flex items-center gap-1">
                  <Copy className="w-3 h-3" /> {strat.clone_count || 0}
                </span>
              </div>

              {/* Actions */}
              <div className="flex gap-2">
                <Button size="sm" variant="ghost" onClick={() => handleSubscribe(strat.id)} className="flex-1">
                  订阅
                </Button>
                <Button size="sm" onClick={() => handleClone(strat.id)} className="flex-1">
                  <Copy className="w-3.5 h-3.5 inline mr-1" /> 克隆
                </Button>
              </div>

              {/* Rating */}
              <div className="flex items-center justify-center gap-1 mt-3 pt-3 border-t border-border">
                <span className="text-xs text-slate-600 mr-2">评分:</span>
                {[1, 2, 3, 4, 5].map((star) => (
                  <button
                    key={star}
                    onClick={() => handleRate(strat.id, star)}
                    className="text-slate-700 hover:text-orange-400 transition-colors"
                  >
                    <Star className="w-3.5 h-3.5" />
                  </button>
                ))}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
