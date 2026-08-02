import { useState, useEffect, useCallback } from 'react'
import { Plus, Search, Edit3, Trash2, Share2, Archive, Copy, History, Code2, FileText } from 'lucide-react'
import {
  Card, Button, Badge, Modal, Input, Textarea, Select, Loading, EmptyState,
  useToast, fmtDate,
} from '../components/ui'
import { strategyApi } from '../lib/api'
import type { Strategy, StrategyVersion, BacktestTemplate } from '../lib/types'

const STATUS_COLORS: Record<string, 'gray' | 'green' | 'blue' | 'orange' | 'red'> = {
  draft: 'gray', testing: 'orange', published: 'green', archived: 'red',
}

export default function Strategies() {
  const toast = useToast()
  const [strategies, setStrategies] = useState<Strategy[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing] = useState<Strategy | null>(null)
  const [versions, setVersions] = useState<StrategyVersion[] | null>(null)
  const [templates, setTemplates] = useState<BacktestTemplate[]>([])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [listRes, tplRes] = await Promise.allSettled([
        strategyApi.list({ ...(search && { search }), ...(statusFilter && { status: statusFilter }) }),
        strategyApi.templates(),
      ])
      if (listRes.status === 'fulfilled') {
        setStrategies(Array.isArray(listRes.value) ? listRes.value : listRes.value?.items || [])
      }
      if (tplRes.status === 'fulfilled') {
        setTemplates(Array.isArray(tplRes.value) ? tplRes.value : tplRes.value?.items || [])
      }
    } catch (e: any) {
      toast(e.message, 'error')
    }
    setLoading(false)
  }, [search, statusFilter, toast])

  useEffect(() => {
    const t = setTimeout(load, 300)
    return () => clearTimeout(t)
  }, [load])

  const handleSave = async (data: any) => {
    try {
      if (editing) {
        await strategyApi.update(editing.id, data)
        toast('策略更新成功', 'success')
      } else {
        await strategyApi.create(data)
        toast('策略创建成功', 'success')
      }
      setShowModal(false)
      setEditing(null)
      load()
    } catch (e: any) {
      toast(e.message, 'error')
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('确认删除该策略？')) return
    try {
      await strategyApi.delete(id)
      toast('已删除', 'success')
      load()
    } catch (e: any) {
      toast(e.message, 'error')
    }
  }

  const handlePublish = async (id: string) => {
    try {
      await strategyApi.publish(id)
      toast('已发布到市场', 'success')
      load()
    } catch (e: any) {
      toast(e.message, 'error')
    }
  }

  const handleArchive = async (id: string) => {
    try {
      await strategyApi.archive(id)
      toast('已归档', 'success')
      load()
    } catch (e: any) {
      toast(e.message, 'error')
    }
  }

  const handleClone = async (id: string) => {
    try {
      await strategyApi.clone(id)
      toast('已克隆到我的策略', 'success')
      load()
    } catch (e: any) {
      toast(e.message, 'error')
    }
  }

  const loadVersions = async (id: string) => {
    try {
      const res = await strategyApi.versions(id)
      setVersions(Array.isArray(res) ? res : res?.items || [])
    } catch (e: any) {
      toast(e.message, 'error')
    }
  }

  const handleRollback = async (id: string, ver: number) => {
    if (!confirm(`回滚到版本 v${ver}？`)) return
    try {
      await strategyApi.rollback(id, ver)
      toast('已回滚', 'success')
      setVersions(null)
      load()
    } catch (e: any) {
      toast(e.message, 'error')
    }
  }

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600" />
          <input
            className="w-full pl-9 pr-3 py-2 bg-surface border border-border rounded-lg text-sm placeholder-slate-600 focus:outline-none focus:border-accent"
            placeholder="搜索策略名称..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="w-auto">
          <option value="">全部状态</option>
          <option value="draft">草稿</option>
          <option value="testing">测试中</option>
          <option value="published">已发布</option>
          <option value="archived">已归档</option>
        </Select>
        <Button onClick={() => { setEditing(null); setShowModal(true) }}>
          <Plus className="w-4 h-4 inline mr-1" /> 新建策略
        </Button>
      </div>

      {/* List */}
      {loading ? (
        <Loading />
      ) : strategies.length === 0 ? (
        <Card>
          <EmptyState icon={<Code2 className="w-12 h-12" />} title="暂无策略" subtitle="点击右上角创建你的第一个策略" />
        </Card>
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
                {strategies.map((s) => (
                  <tr key={s.id} className="border-t border-border hover:bg-surface2/50">
                    <td className="px-4 py-3">
                      <div className="text-sm font-medium">{s.name}</div>
                      {s.description && <div className="text-xs text-slate-500 truncate max-w-xs">{s.description}</div>}
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-400">{s.category || '-'}</td>
                    <td className="px-4 py-3">
                      <Badge color={STATUS_COLORS[s.status] || 'gray'}>{s.status}</Badge>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-400">v{s.version}</td>
                    <td className="px-4 py-3 text-sm text-slate-500">{fmtDate(s.updated_at)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <button onClick={() => { setEditing(s); setShowModal(true) }} className="p-1.5 hover:bg-surface3 rounded text-slate-400 hover:text-accent-light" title="编辑">
                          <Edit3 className="w-3.5 h-3.5" />
                        </button>
                        <button onClick={() => loadVersions(s.id)} className="p-1.5 hover:bg-surface3 rounded text-slate-400 hover:text-cyan-400" title="版本">
                          <History className="w-3.5 h-3.5" />
                        </button>
                        {s.status !== 'published' && s.status !== 'archived' && (
                          <button onClick={() => handlePublish(s.id)} className="p-1.5 hover:bg-surface3 rounded text-slate-400 hover:text-green-400" title="发布">
                            <Share2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                        {s.status !== 'archived' && (
                          <button onClick={() => handleArchive(s.id)} className="p-1.5 hover:bg-surface3 rounded text-slate-400 hover:text-orange-400" title="归档">
                            <Archive className="w-3.5 h-3.5" />
                          </button>
                        )}
                        <button onClick={() => handleClone(s.id)} className="p-1.5 hover:bg-surface3 rounded text-slate-400 hover:text-blue-400" title="克隆">
                          <Copy className="w-3.5 h-3.5" />
                        </button>
                        <button onClick={() => handleDelete(s.id)} className="p-1.5 hover:bg-surface3 rounded text-slate-400 hover:text-red-400" title="删除">
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
      )}

      {/* Create/Edit Modal */}
      {showModal && (
        <StrategyModal
          strategy={editing}
          templates={templates}
          onSave={handleSave}
          onClose={() => { setShowModal(false); setEditing(null) }}
        />
      )}

      {/* Versions Modal */}
      {versions && (
        <Modal title="版本历史" onClose={() => setVersions(null)} maxWidth="max-w-lg">
          <div className="space-y-2">
            {versions.length === 0 ? (
              <p className="text-center text-sm text-slate-600 py-8">暂无版本记录</p>
            ) : (
              versions.map((v) => (
                <div key={v.id} className="flex items-center gap-3 p-3 bg-surface2 rounded-lg">
                  <Badge color="blue">v{v.version}</Badge>
                  <div className="flex-1">
                    <div className="text-sm">{v.changelog || '无变更说明'}</div>
                    <div className="text-xs text-slate-500">{fmtDate(v.created_at)}</div>
                  </div>
                  <Button size="sm" variant="ghost" onClick={() => handleRollback(v.strategy_id, v.version)}>
                    回滚
                  </Button>
                </div>
              ))
            )}
          </div>
        </Modal>
      )}
    </div>
  )
}

function StrategyModal({
  strategy, templates, onSave, onClose,
}: {
  strategy: Strategy | null
  templates: BacktestTemplate[]
  onSave: (data: any) => void
  onClose: () => void
}) {
  const [name, setName] = useState(strategy?.name || '')
  const [description, setDescription] = useState(strategy?.description || '')
  const [category, setCategory] = useState(strategy?.category || '')
  const [tags, setTags] = useState((strategy?.tags || []).join(', '))
  const [sourceCode, setSourceCode] = useState(strategy?.source_code || '')
  const [marketDesc, setMarketDesc] = useState(strategy?.market_desc || '')
  const [selectedTemplate, setSelectedTemplate] = useState('')

  const applyTemplate = (tplId: string) => {
    setSelectedTemplate(tplId)
    const tpl = templates.find((t) => t.id === tplId)
    if (tpl) {
      if (!name) setName(tpl.name)
      if (!description) setDescription(tpl.description || '')
      if (!category) setCategory(tpl.category || '')
    }
  }

  const handleSubmit = () => {
    if (!name.trim()) return
    onSave({
      name,
      description,
      category,
      tags: tags.split(',').map((t) => t.trim()).filter(Boolean),
      source_code: sourceCode,
      market_desc: marketDesc,
    })
  }

  return (
    <Modal
      title={strategy ? '编辑策略' : '新建策略'}
      onClose={onClose}
      maxWidth="max-w-3xl"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>取消</Button>
          <Button onClick={handleSubmit} disabled={!name.trim()}>保存</Button>
        </>
      }
    >
      <div className="space-y-4">
        {!strategy && templates.length > 0 && (
          <Select label="从模板创建" value={selectedTemplate} onChange={(e) => applyTemplate(e.target.value)}>
            <option value="">— 选择模板 —</option>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </Select>
        )}
        <div className="grid grid-cols-2 gap-4">
          <Input label="策略名称" value={name} onChange={(e) => setName(e.target.value)} placeholder="例如：双均线交叉" />
          <Input label="分类" value={category} onChange={(e) => setCategory(e.target.value)} placeholder="例如：趋势跟踪" />
        </div>
        <Input label="标签（逗号分隔）" value={tags} onChange={(e) => setTags(e.target.value)} placeholder="例如：动量, A股, 日线" />
        <Textarea label="描述" value={description} onChange={(e) => setDescription(e.target.value)} rows={2} placeholder="简要描述策略逻辑..." />
        <div>
          <label className="block text-xs text-slate-400 mb-1.5 font-medium">策略代码</label>
          <textarea
            className="w-full px-3 py-2 bg-[#0a0d12] border border-border rounded-lg text-sm font-mono text-slate-300 placeholder-slate-600 focus:outline-none focus:border-accent resize-vertical"
            rows={12}
            value={sourceCode}
            onChange={(e) => setSourceCode(e.target.value)}
            placeholder="def strategy(ctx): ..."
            spellCheck={false}
          />
        </div>
        <Textarea label="市场描述（发布到市场时显示）" value={marketDesc} onChange={(e) => setMarketDesc(e.target.value)} rows={2} placeholder="面向其他用户的策略介绍..." />
      </div>
    </Modal>
  )
}
