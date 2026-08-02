import { useState, useEffect } from 'react'
import { Settings as SettingsIcon, Cpu, Database, Check, RefreshCw, Server, Shield, Lock } from 'lucide-react'
import {
  Card, CardHeader, Button, Badge, Input, Select, Loading,
  useToast,
} from '../components/ui'
import { settingsApi, systemApi, authApi } from '../lib/api'
import { useAuth } from '../lib/auth'

export default function Settings() {
  const toast = useToast()
  const { user } = useAuth()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [llm, setLlm] = useState<any>(null)
  const [dataSources, setDataSources] = useState<any>(null)
  const [systemReady, setSystemReady] = useState<any>(null)
  const [tab, setTab] = useState<'account' | 'llm' | 'data' | 'system'>('account')

  // Password change state
  const [oldPw, setOldPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const [pwSaving, setPwSaving] = useState(false)

  useEffect(() => {
    Promise.allSettled([
      settingsApi.llm(),
      settingsApi.dataSources(),
      systemApi.ready(),
    ]).then(([llmRes, dataRes, readyRes]) => {
      if (llmRes.status === 'fulfilled') setLlm(llmRes.value)
      if (dataRes.status === 'fulfilled') setDataSources(dataRes.value)
      if (readyRes.status === 'fulfilled') setSystemReady(readyRes.value)
      setLoading(false)
    })
  }, [])

  const handleSaveLlm = async () => {
    setSaving(true)
    try {
      await settingsApi.updateLlm(llm)
      toast('LLM 配置已保存', 'success')
    } catch (e: any) {
      toast(e.message, 'error')
    }
    setSaving(false)
  }

  const handleSaveData = async () => {
    setSaving(true)
    try {
      await settingsApi.updateDataSources(dataSources)
      toast('数据源配置已保存', 'success')
    } catch (e: any) {
      toast(e.message, 'error')
    }
    setSaving(false)
  }

  const handleChangePassword = async () => {
    if (newPw.length < 6) {
      toast('新密码至少需要 6 个字符', 'error')
      return
    }
    if (newPw !== confirmPw) {
      toast('两次输入的密码不一致', 'error')
      return
    }
    setPwSaving(true)
    try {
      await authApi.changePassword(oldPw, newPw)
      toast('密码修改成功', 'success')
      setOldPw(''); setNewPw(''); setConfirmPw('')
    } catch (e: any) {
      toast(e.message || '密码修改失败', 'error')
    }
    setPwSaving(false)
  }

  if (loading) return <Loading text="加载设置..." />

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Tabs */}
      <div className="flex gap-1 bg-surface rounded-lg p-1 w-fit overflow-x-auto">
        <button className={`px-4 py-1.5 rounded-md text-sm transition-all whitespace-nowrap ${tab === 'account' ? 'bg-accent text-white' : 'text-slate-400 hover:text-slate-200'}`} onClick={() => setTab('account')}>
          <Shield className="w-3.5 h-3.5 inline mr-1.5" /> 账户安全
        </button>
        <button className={`px-4 py-1.5 rounded-md text-sm transition-all whitespace-nowrap ${tab === 'llm' ? 'bg-accent text-white' : 'text-slate-400 hover:text-slate-200'}`} onClick={() => setTab('llm')}>
          <Cpu className="w-3.5 h-3.5 inline mr-1.5" /> LLM 配置
        </button>
        <button className={`px-4 py-1.5 rounded-md text-sm transition-all whitespace-nowrap ${tab === 'data' ? 'bg-accent text-white' : 'text-slate-400 hover:text-slate-200'}`} onClick={() => setTab('data')}>
          <Database className="w-3.5 h-3.5 inline mr-1.5" /> 数据源
        </button>
        <button className={`px-4 py-1.5 rounded-md text-sm transition-all whitespace-nowrap ${tab === 'system' ? 'bg-accent text-white' : 'text-slate-400 hover:text-slate-200'}`} onClick={() => setTab('system')}>
          <Server className="w-3.5 h-3.5 inline mr-1.5" /> 系统状态
        </button>
      </div>

      {/* Account Security Tab */}
      {tab === 'account' && (
        <div className="space-y-4">
          {/* Account Info */}
          <Card>
            <CardHeader title="账户信息" />
            <div className="p-5 space-y-3">
              <div className="flex items-center justify-between py-2">
                <span className="text-sm text-slate-400">用户名</span>
                <span className="text-sm text-slate-200">{user?.name || '未设置'}</span>
              </div>
              <div className="flex items-center justify-between py-2 border-t border-border">
                <span className="text-sm text-slate-400">邮箱</span>
                <span className="text-sm text-slate-200">{user?.email}</span>
              </div>
              <div className="flex items-center justify-between py-2 border-t border-border">
                <span className="text-sm text-slate-400">角色</span>
                <Badge color={user?.role === 'admin' ? 'blue' : 'gray'}>
                  {user?.role === 'admin' ? '管理员' : user?.role === 'operator' ? '运营' : '普通用户'}
                </Badge>
              </div>
              <div className="flex items-center justify-between py-2 border-t border-border">
                <span className="text-sm text-slate-400">账户状态</span>
                <Badge color={user?.status === 'active' ? 'green' : 'red'}>
                  {user?.status === 'active' ? '正常' : '已禁用'}
                </Badge>
              </div>
            </div>
          </Card>

          {/* Change Password */}
          <Card>
            <CardHeader title="修改密码" />
            <div className="p-5 space-y-4 max-w-md">
              <div>
                <label className="block text-xs text-slate-400 mb-1.5 font-medium">当前密码</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600" />
                  <input
                    type="password"
                    value={oldPw}
                    onChange={(e) => setOldPw(e.target.value)}
                    placeholder="输入当前密码"
                    className="w-full pl-10 pr-3 py-2 bg-bg border border-border rounded-lg text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-accent transition-colors"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1.5 font-medium">新密码</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600" />
                  <input
                    type="password"
                    value={newPw}
                    onChange={(e) => setNewPw(e.target.value)}
                    placeholder="至少 6 个字符"
                    className="w-full pl-10 pr-3 py-2 bg-bg border border-border rounded-lg text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-accent transition-colors"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1.5 font-medium">确认新密码</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600" />
                  <input
                    type="password"
                    value={confirmPw}
                    onChange={(e) => setConfirmPw(e.target.value)}
                    placeholder="再次输入新密码"
                    className={`w-full pl-10 pr-3 py-2 bg-bg border rounded-lg text-sm text-slate-200 placeholder-slate-600 focus:outline-none transition-colors ${
                      confirmPw && newPw !== confirmPw ? 'border-red-500/50' : 'border-border focus:border-accent'
                    }`}
                  />
                </div>
              </div>
              <Button
                onClick={handleChangePassword}
                disabled={pwSaving || !oldPw || !newPw || !confirmPw}
              >
                {pwSaving ? '保存中...' : '修改密码'}
              </Button>
            </div>
          </Card>
        </div>
      )}

      {tab === 'llm' && llm && (
        <Card>
          <CardHeader title="LLM 配置" action={<Button size="sm" onClick={handleSaveLlm} disabled={saving}>{saving ? '保存中...' : '保存'}</Button>} />
          <div className="p-5 space-y-4">
            <Select label="模型提供商" value={llm.provider || ''} onChange={(e) => setLlm({ ...llm, provider: e.target.value })}>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
              <option value="deepseek">DeepSeek</option>
              <option value="custom">自定义</option>
            </Select>
            <Input label="模型名称" value={llm.model || ''} onChange={(e) => setLlm({ ...llm, model: e.target.value })} placeholder="例如：gpt-4o-mini" />
            <Input label="API Base URL" value={llm.base_url || ''} onChange={(e) => setLlm({ ...llm, base_url: e.target.value })} placeholder="https://api.openai.com/v1" />
            <Input label="API Key" type="password" value={llm.api_key || ''} onChange={(e) => setLlm({ ...llm, api_key: e.target.value })} placeholder="sk-..." />
            <div className="grid grid-cols-2 gap-4">
              <Input label="Temperature" type="number" value={llm.temperature?.toString() || '0.7'} onChange={(e) => setLlm({ ...llm, temperature: parseFloat(e.target.value) || 0.7 })} />
              <Input label="Max Tokens" type="number" value={llm.max_tokens?.toString() || '4096'} onChange={(e) => setLlm({ ...llm, max_tokens: parseInt(e.target.value) || 4096 })} />
            </div>
            <div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={llm.enabled ?? true} onChange={(e) => setLlm({ ...llm, enabled: e.target.checked })} className="w-4 h-4 rounded accent-accent" />
                <span className="text-sm text-slate-400">启用 LLM 服务</span>
              </label>
            </div>
          </div>
        </Card>
      )}

      {tab === 'data' && dataSources && (
        <Card>
          <CardHeader title="数据源配置" action={<Button size="sm" onClick={handleSaveData} disabled={saving}>{saving ? '保存中...' : '保存'}</Button>} />
          <div className="p-5 space-y-4">
            <div className="bg-surface2 rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-cyan-400" />
                  <span className="text-sm font-medium">Tushare</span>
                  <Badge color={dataSources.tushare?.enabled ? 'green' : 'gray'}>
                    {dataSources.tushare?.enabled ? '已启用' : '未启用'}
                  </Badge>
                </div>
                <input type="checkbox" checked={dataSources.tushare?.enabled ?? false} onChange={(e) => setDataSources({ ...dataSources, tushare: { ...dataSources.tushare, enabled: e.target.checked } })} className="w-4 h-4 rounded accent-accent" />
              </div>
              <Input label="Tushare Token" type="password" value={dataSources.tushare?.token || ''} onChange={(e) => setDataSources({ ...dataSources, tushare: { ...dataSources.tushare, token: e.target.value } })} placeholder="tushare token" />
            </div>

            <div className="bg-surface2 rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-green-400" />
                  <span className="text-sm font-medium">AKShare</span>
                  <Badge color={dataSources.akshare?.enabled ? 'green' : 'gray'}>
                    {dataSources.akshare?.enabled ? '已启用' : '未启用'}
                  </Badge>
                </div>
                <input type="checkbox" checked={dataSources.akshare?.enabled ?? false} onChange={(e) => setDataSources({ ...dataSources, akshare: { ...dataSources.akshare, enabled: e.target.checked } })} className="w-4 h-4 rounded accent-accent" />
              </div>
            </div>

            <div className="bg-surface2 rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-orange-400" />
                  <span className="text-sm font-medium">CCXT (加密货币)</span>
                  <Badge color={dataSources.ccxt?.enabled ? 'green' : 'gray'}>
                    {dataSources.ccxt?.enabled ? '已启用' : '未启用'}
                  </Badge>
                </div>
                <input type="checkbox" checked={dataSources.ccxt?.enabled ?? false} onChange={(e) => setDataSources({ ...dataSources, ccxt: { ...dataSources.ccxt, enabled: e.target.checked } })} className="w-4 h-4 rounded accent-accent" />
              </div>
              <Input label="默认交易所" value={dataSources.ccxt?.exchange || ''} onChange={(e) => setDataSources({ ...dataSources, ccxt: { ...dataSources.ccxt, exchange: e.target.value } })} placeholder="binance" />
            </div>
          </div>
        </Card>
      )}

      {tab === 'system' && (
        <div className="space-y-4">
          <Card>
            <CardHeader title="系统状态" action={<Button size="sm" variant="ghost" onClick={() => window.location.reload()}><RefreshCw className="w-3.5 h-3.5 inline mr-1" />刷新</Button>} />
            <div className="p-5">
              {systemReady ? (
                <div className="space-y-3">
                  {Object.entries(systemReady).map(([key, val]: [string, any]) => (
                    <div key={key} className="flex items-center justify-between p-3 bg-surface2 rounded-lg">
                      <div className="flex items-center gap-2">
                        {val?.ready || val === true ? (
                          <Check className="w-4 h-4 text-green-400" />
                        ) : (
                          <SettingsIcon className="w-4 h-4 text-slate-500" />
                        )}
                        <span className="text-sm capitalize">{key.replace(/_/g, ' ')}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        {typeof val === 'object' && val?.message && (
                          <span className="text-xs text-slate-500">{val.message}</span>
                        )}
                        <Badge color={val?.ready || val === true ? 'green' : 'gray'}>
                          {val?.ready || val === true ? '就绪' : '未就绪'}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-center text-sm text-slate-600 py-8">无法获取系统状态</p>
              )}
            </div>
          </Card>

          <Card className="p-5">
            <div className="text-xs text-slate-500 mb-3">关于</div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-400">版本</span>
                <span className="text-slate-300">v1.0.0</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">平台</span>
                <span className="text-slate-300">AI Native 量化交易</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">技术栈</span>
                <span className="text-slate-300">FastAPI + React + TypeScript</span>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}
