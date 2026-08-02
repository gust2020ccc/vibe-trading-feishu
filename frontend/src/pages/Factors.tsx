import { useState, useEffect, useCallback } from 'react'
import { Plus, Search, Edit3, Trash2, FlaskConical, Layers } from 'lucide-react'
import {
  Card, Button, Badge, Modal, Input, Textarea, Select, Loading, EmptyState,
  useToast, fmtDate,
} from '../components/ui'
import { factorApi } from '../lib/api'
import type { Factor } from '../lib/types'

export default function Factors() {
  const toast = useToast()
  const [factors, setFactors] = useState<Factor[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing] = useState<Factor | null>(null)
  const [tab, setTab] = useState<'factors' | 'portfolios'>('factors')
  const [portfolios, setPortfolios] = useState<any[]>([])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      if (tab === 'factors') {
        const res = await factorApi.list({ ...(search && { search }) })
        setFactors(Array.isArray(res) ? res : res?.items || [])
      } else {
        const res = await factorApi.portfolios()
        setPortfolios(Array.isArray(res) ? res : res?.items || [])
      }
    } catch (e: any) {
      toast(e.message, 'error')
    }
    setLoading(false)
  }, [tab, search, toast])

  useEffect(() => {
    const t = setTimeout(load, 300)
    return () => clearTimeout(t)
  }, [load])

  const handleSave = async (data: any) => {
    try {
      if (editing) {
        await factorApi.update(editing.id, data)
        toast('因子更新成功', 'success')
      } else {
        await factorApi.create(data)
        toast('因子创建成功', 'success')
      }
      setShowModal(false)
      setEditing(null)
      load()
    } catch (e: any) {
      toast(e.message, 'error')
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('确认删除该因子？')) return
    try {
      await factorApi.delete(id)
      toast('已删除', 'success')
      load()
    } catch (e: any) {
      toast(e.message, 'error')
    }
  }

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Tabs */}
      <div className="flex gap-1 bg-surface rounded-lg p-1 w-fit">
        <button
          className={`px-4 py-1.5 rounded-md text-sm transition-all ${tab === 'factors' ? 'bg-accent text-white' : 'text-slate-400 hover:text-slate-200'}`}
          onClick={() => setTab('factors')}
        >
          <FlaskConical className="w-3.5 h-3.5 inline mr-1.5" /> 因子管理
        </button>
        <button
          className={`px-4 py-1.5 rounded-md text-sm transition-all ${tab === 'portfolios' ? 'bg-accent text-white' : 'text-slate-400 hover:text-slate-200'}`}
          onClick={() => setTab('portfolios')}
        >
          <Layers className="w-3.5 h-3.5 inline mr-1.5" /> 因子组合
        </button>
      </div>

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3">
        {tab === 'factors' && (
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600" />
            <input
              className="w-full pl-9 pr-3 py-2 bg-surface border border-border rounded-lg text-sm placeholder-slate-600 focus:outline-none focus:border-accent"
              placeholder="搜索因子..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        )}
        {tab === 'factors' && (
          <Button onClick={() => { setEditing(null); setShowModal(true) }}>
            <Plus className="w-4 h-4 inline mr-1" /> 新建因子
          </Button>
        )}
      </div>

      {/* Content */}
      {loading ? (
        <Loading />
      ) : tab === 'factors' ? (
        factors.length === 0 ? (
          <Card><EmptyState icon={<FlaskConical className="w-12 h-12" />} title="暂无因子" subtitle="创建你的第一个因子" /></Card>
        ) : (
          <Card>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left">
                    <th className="px-4 py-3 text-xs uppercase text-slate-500 font-medium">名称</th>
                    <th className="px-4 py-3 text-xs uppercase text-slate-500 font-medium">分类</th>
                    <th className="px-4 py-3 text-xs uppercase text-slate-500 font-medium">状态</th>
                    <th className="px-4 py-3 text-xs uppercase text-slate-500 font-medium">版本</th>
                    <th className="px-4 py-3 text-xs uppercase text-slate-500 font-medium">更新时间</th>
                    <th className="px-4 py-3 text-xs uppercase text-slate-500 font-medium text-right">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {factors.map((f) => (
                    <tr key={f.id} className="border-t border-border hover:bg-surface2/50">
                      <td className="px-4 py-3">
                        <div className="text-sm font-medium">{f.name}</div>
                        {f.description && <div className="text-xs text-slate-500 truncate max-w-xs">{f.description}</div>}
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-400">{f.category || '-'}</td>
                      <td className="px-4 py-3"><Badge color={f.status === 'published' ? 'green' : 'gray'}>{f.status}</Badge></td>
                      <td className="px-4 py-3 text-sm text-slate-400">v{f.version}</td>
                      <td className="px-4 py-3 text-sm text-slate-500">{fmtDate(f.updated_at)}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1">
                          <button onClick={() => { setEditing(f); setShowModal(true) }} className="p-1.5 hover:bg-surface3 rounded text-slate-400 hover:text-accent-light" title="编辑">
                            <Edit3 className="w-3.5 h-3.5" />
                          </button>
                          <button onClick={() => handleDelete(f.id)} className="p-1.5 hover:bg-surface3 rounded text-slate-400 hover:text-red-400" title="删除">
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )
      ) : (
        <Card>
          <Card>
            <div className="p-2">
              {portfolios.length === 0 ? (
                <EmptyState icon={<Layers className="w-12 h-12" />} title="暂无因子组合" subtitle="创建因子组合来批量管理多个因子" />
              ) : (
                portfolios.map((p) => (
                  <div key={p.id} className="flex items-center gap-3 px-3 py-3 border-b border-border last:border-0">
                    <div className="w-8 h-8 rounded-lg bg-cyan-500/10 flex items-center justify-center">
                      <Layers className="w-4 h-4 text-cyan-400" />
                    </div>
                    <div className="flex-1">
                      <div className="text-sm font-medium">{p.name}</div>
                      <div className="text-xs text-slate-500">{p.factors?.length || 0} 个因子</div>
                    </div>
                    <Badge color="blue">{p.status}</Badge>
                  </div>
                ))
              )}
            </div>
          </Card>
        </Card>
      )}

      {/* Modal */}
      {showModal && (
        <FactorModal factor={editing} onSave={handleSave} onClose={() => { setShowModal(false); setEditing(null) }} />
      )}
    </div>
  )
}

function FactorModal({ factor, onSave, onClose }: { factor: Factor | null; onSave: (data: any) => void; onClose: () => void }) {
  const [name, setName] = useState(factor?.name || '')
  const [description, setDescription] = useState(factor?.description || '')
  const [category, setCategory] = useState(factor?.category || '')
  const [tags, setTags] = useState((factor?.tags || []).join(', '))
  const [sourceCode, setSourceCode] = useState(factor?.source_code || '')

  const handleSubmit = () => {
    if (!name.trim()) return
    onSave({ name, description, category, tags: tags.split(',').map((t) => t.trim()).filter(Boolean), source_code: sourceCode })
  }

  return (
    <Modal
      title={factor ? '编辑因子' : '新建因子'}
      onClose={onClose}
      maxWidth="max-w-2xl"
      footer={<><Button variant="ghost" onClick={onClose}>取消</Button><Button onClick={handleSubmit} disabled={!name.trim()}>保存</Button></>}
    >
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <Input label="因子名称" value={name} onChange={(e) => setName(e.target.value)} placeholder="例如：动量因子" />
          <Input label="分类" value={category} onChange={(e) => setCategory(e.target.value)} placeholder="例如：技术指标" />
        </div>
        <Input label="标签（逗号分隔）" value={tags} onChange={(e) => setTags(e.target.value)} placeholder="例如：动量, 日线" />
        <Textarea label="描述" value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
        <div>
          <label className="block text-xs text-slate-400 mb-1.5 font-medium">因子代码</label>
          <textarea
            className="w-full px-3 py-2 bg-[#0a0d12] border border-border rounded-lg text-sm font-mono text-slate-300 placeholder-slate-600 focus:outline-none focus:border-accent resize-vertical"
            rows={10}
            value={sourceCode}
            onChange={(e) => setSourceCode(e.target.value)}
            placeholder="def compute(ctx): ..."
            spellCheck={false}
          />
        </div>
      </div>
    </Modal>
  )
}
