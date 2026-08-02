import { useState, useEffect, useCallback } from 'react'
import { Plus, Edit3, Trash2, Users, Shield, Activity, BarChart3 } from 'lucide-react'
import {
  Card, CardHeader, Button, Badge, Modal, Input, Select, Loading, EmptyState,
  useToast, fmtDate, fmtNum,
} from '../components/ui'
import { adminApi } from '../lib/api'
import type { User } from '../lib/types'

export default function Admin() {
  const toast = useToast()
  const [users, setUsers] = useState<User[]>([])
  const [usageSummary, setUsageSummary] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing] = useState<User | null>(null)
  const [tab, setTab] = useState<'users' | 'usage'>('users')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [userRes, usageRes] = await Promise.allSettled([
        adminApi.users(),
        adminApi.usageSummary(),
      ])
      if (userRes.status === 'fulfilled') {
        setUsers(Array.isArray(userRes.value) ? userRes.value : userRes.value?.items || [])
      }
      if (usageRes.status === 'fulfilled') setUsageSummary(usageRes.value)
    } catch (e: any) {
      toast(e.message, 'error')
    }
    setLoading(false)
  }, [toast])

  useEffect(() => { load() }, [load])

  const handleSave = async (data: any) => {
    try {
      if (editing) {
        await adminApi.updateUser(editing.user_id, data)
        toast('用户更新成功', 'success')
      } else {
        await adminApi.createUser(data)
        toast('用户创建成功', 'success')
      }
      setShowModal(false)
      setEditing(null)
      load()
    } catch (e: any) {
      toast(e.message, 'error')
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('确认删除该用户？')) return
    try {
      await adminApi.deleteUser(id)
      toast('已删除', 'success')
      load()
    } catch (e: any) {
      toast(e.message, 'error')
    }
  }

  const roleColors: Record<string, 'gray' | 'green' | 'blue' | 'orange'> = {
    user: 'gray', admin: 'green', operator: 'blue',
  }

  if (loading) return <Loading text="加载用户数据..." />

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Tabs */}
      <div className="flex gap-1 bg-surface rounded-lg p-1 w-fit">
        <button className={`px-4 py-1.5 rounded-md text-sm transition-all ${tab === 'users' ? 'bg-accent text-white' : 'text-slate-400 hover:text-slate-200'}`} onClick={() => setTab('users')}>
          <Users className="w-3.5 h-3.5 inline mr-1.5" /> 用户管理
        </button>
        <button className={`px-4 py-1.5 rounded-md text-sm transition-all ${tab === 'usage' ? 'bg-accent text-white' : 'text-slate-400 hover:text-slate-200'}`} onClick={() => setTab('usage')}>
          <BarChart3 className="w-3.5 h-3.5 inline mr-1.5" /> 用量统计
        </button>
      </div>

      {tab === 'users' ? (
        <>
          {/* Toolbar */}
          <div className="flex justify-end">
            <Button onClick={() => { setEditing(null); setShowModal(true) }}>
              <Plus className="w-4 h-4 inline mr-1" /> 新建用户
            </Button>
          </div>

          {/* User list */}
          {users.length === 0 ? (
            <Card><EmptyState icon={<Users className="w-12 h-12" />} title="暂无用户" /></Card>
          ) : (
            <Card>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="text-left">
                      <th className="px-4 py-3 text-xs uppercase text-slate-500 font-medium">用户</th>
                      <th className="px-4 py-3 text-xs uppercase text-slate-500 font-medium">渠道</th>
                      <th className="px-4 py-3 text-xs uppercase text-slate-500 font-medium">角色</th>
                      <th className="px-4 py-3 text-xs uppercase text-slate-500 font-medium">状态</th>
                      <th className="px-4 py-3 text-xs uppercase text-slate-500 font-medium">今日请求</th>
                      <th className="px-4 py-3 text-xs uppercase text-slate-500 font-medium">创建时间</th>
                      <th className="px-4 py-3 text-xs uppercase text-slate-500 font-medium text-right">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u) => (
                      <tr key={u.user_id} className="border-t border-border hover:bg-surface2/50">
                        <td className="px-4 py-3">
                          <div className="text-sm font-medium">{u.name}</div>
                          <div className="text-xs text-slate-500">{u.user_id.slice(0, 12)}</div>
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-400">{u.channel}</td>
                        <td className="px-4 py-3"><Badge color={roleColors[u.role] || 'gray'}>{u.role}</Badge></td>
                        <td className="px-4 py-3"><Badge color={u.status === 'active' ? 'green' : 'red'}>{u.status}</Badge></td>
                        <td className="px-4 py-3 text-sm text-slate-400">{u.usage_summary?.today_requests || 0}</td>
                        <td className="px-4 py-3 text-sm text-slate-500">{fmtDate(u.created_at)}</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-end gap-1">
                            <button onClick={() => { setEditing(u); setShowModal(true) }} className="p-1.5 hover:bg-surface3 rounded text-slate-400 hover:text-accent-light" title="编辑">
                              <Edit3 className="w-3.5 h-3.5" />
                            </button>
                            <button onClick={() => handleDelete(u.user_id)} className="p-1.5 hover:bg-surface3 rounded text-slate-400 hover:text-red-400" title="删除">
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
        </>
      ) : (
        /* Usage stats */
        <div className="space-y-4">
          {usageSummary ? (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Users className="w-4 h-4 text-accent-light" />
                    <span className="text-xs text-slate-500">总用户数</span>
                  </div>
                  <div className="text-2xl font-bold">{usageSummary.total_users || users.length}</div>
                </Card>
                <Card className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Activity className="w-4 h-4 text-green-400" />
                    <span className="text-xs text-slate-500">今日活跃</span>
                  </div>
                  <div className="text-2xl font-bold">{usageSummary.active_today || 0}</div>
                </Card>
                <Card className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <BarChart3 className="w-4 h-4 text-cyan-400" />
                    <span className="text-xs text-slate-500">今日请求</span>
                  </div>
                  <div className="text-2xl font-bold">{fmtNum(usageSummary.today_requests)}</div>
                </Card>
                <Card className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Shield className="w-4 h-4 text-orange-400" />
                    <span className="text-xs text-slate-500">今日 Token</span>
                  </div>
                  <div className="text-2xl font-bold">{fmtNum(usageSummary.today_tokens)}</div>
                </Card>
              </div>
              <Card>
                <CardHeader title="用户用量明细" />
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="text-left">
                        <th className="px-4 py-3 text-xs uppercase text-slate-500 font-medium">用户</th>
                        <th className="px-4 py-3 text-xs uppercase text-slate-500 font-medium">今日 Token</th>
                        <th className="px-4 py-3 text-xs uppercase text-slate-500 font-medium">月度 Token</th>
                        <th className="px-4 py-3 text-xs uppercase text-slate-500 font-medium">今日请求</th>
                        <th className="px-4 py-3 text-xs uppercase text-slate-500 font-medium">月度请求</th>
                      </tr>
                    </thead>
                    <tbody>
                      {users.filter((u) => u.usage_summary).map((u) => (
                        <tr key={u.user_id} className="border-t border-border hover:bg-surface2/50">
                          <td className="px-4 py-3 text-sm font-medium">{u.name}</td>
                          <td className="px-4 py-3 text-sm text-slate-400">{fmtNum(u.usage_summary?.today_tokens)}</td>
                          <td className="px-4 py-3 text-sm text-slate-400">{fmtNum(u.usage_summary?.month_tokens)}</td>
                          <td className="px-4 py-3 text-sm text-slate-400">{u.usage_summary?.today_requests || 0}</td>
                          <td className="px-4 py-3 text-sm text-slate-400">{u.usage_summary?.month_requests || 0}</td>
                        </tr>
                      ))}
                      {users.filter((u) => u.usage_summary).length === 0 && (
                        <tr><td colSpan={5} className="px-4 py-8 text-center text-sm text-slate-600">暂无用量数据</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </Card>
            </>
          ) : (
            <Card><EmptyState icon={<BarChart3 className="w-12 h-12" />} title="暂无用量数据" /></Card>
          )}
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <UserModal user={editing} onSave={handleSave} onClose={() => { setShowModal(false); setEditing(null) }} />
      )}
    </div>
  )
}

function UserModal({ user, onSave, onClose }: { user: User | null; onSave: (data: any) => void; onClose: () => void }) {
  const [name, setName] = useState(user?.name || '')
  const [channel, setChannel] = useState(user?.channel || 'web')
  const [role, setRole] = useState<'user' | 'admin' | 'operator'>(user?.role || 'user')
  const [status, setStatus] = useState<'active' | 'disabled'>(user?.status || 'active')
  const [dailyLimit, setDailyLimit] = useState(user?.quota?.daily_token_limit?.toString() || '100000')
  const [monthlyLimit, setMonthlyLimit] = useState(user?.quota?.monthly_token_limit?.toString() || '3000000')
  const [rateLimit, setRateLimit] = useState(user?.quota?.rate_limit_per_minute?.toString() || '30')

  const handleSubmit = () => {
    if (!name.trim()) return
    onSave({
      name,
      channel,
      role,
      status,
      quota: {
        daily_token_limit: parseInt(dailyLimit) || 100000,
        monthly_token_limit: parseInt(monthlyLimit) || 3000000,
        rate_limit_per_minute: parseInt(rateLimit) || 30,
      },
    })
  }

  return (
    <Modal
      title={user ? '编辑用户' : '新建用户'}
      onClose={onClose}
      maxWidth="max-w-lg"
      footer={<><Button variant="ghost" onClick={onClose}>取消</Button><Button onClick={handleSubmit} disabled={!name.trim()}>保存</Button></>}
    >
      <div className="space-y-4">
        <Input label="用户名称" value={name} onChange={(e) => setName(e.target.value)} placeholder="用户昵称" />
        <div className="grid grid-cols-2 gap-4">
          <Select label="渠道" value={channel} onChange={(e) => setChannel(e.target.value)}>
            <option value="web">Web</option>
            <option value="feishu">飞书</option>
            <option value="api">API</option>
          </Select>
          <Select label="角色" value={role} onChange={(e) => setRole(e.target.value as 'user' | 'admin' | 'operator')}>
            <option value="user">普通用户</option>
            <option value="operator">运营</option>
            <option value="admin">管理员</option>
          </Select>
        </div>
        <Select label="状态" value={status} onChange={(e) => setStatus(e.target.value as 'active' | 'disabled')}>
          <option value="active">活跃</option>
          <option value="disabled">禁用</option>
        </Select>
        <div className="border-t border-border pt-4">
          <div className="text-xs text-slate-500 mb-3">配额设置</div>
          <div className="grid grid-cols-2 gap-4">
            <Input label="每日 Token 限制" type="number" value={dailyLimit} onChange={(e) => setDailyLimit(e.target.value)} />
            <Input label="每月 Token 限制" type="number" value={monthlyLimit} onChange={(e) => setMonthlyLimit(e.target.value)} />
          </div>
          <Input label="每分钟请求限制" type="number" value={rateLimit} onChange={(e) => setRateLimit(e.target.value)} />
        </div>
      </div>
    </Modal>
  )
}
