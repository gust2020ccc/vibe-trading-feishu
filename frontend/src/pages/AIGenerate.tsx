import { useState } from 'react'
import { Bot, Sparkles, Code2, Check, Copy, Save, Wand2, Lightbulb } from 'lucide-react'
import {
  Card, CardHeader, Button, Badge, Input, Textarea, Loading,
  useToast,
} from '../components/ui'
import { strategyApi } from '../lib/api'
import type { NLGenerateResult } from '../lib/types'

const EXAMPLES = [
  '一个基于双均线交叉的策略，当短期均线上穿长期均线时买入，下穿时卖出',
  'RSI 超卖反弹策略，RSI 低于30时买入，高于70时卖出',
  '布林带突破策略，价格突破上轨买入，跌破中轨卖出',
  'MACD 金叉死叉策略，结合成交量确认',
]

export default function AIGenerate() {
  const toast = useToast()
  const [description, setDescription] = useState('')
  const [name, setName] = useState('')
  const [autoCreate, setAutoCreate] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [result, setResult] = useState<NLGenerateResult | null>(null)
  const [copied, setCopied] = useState(false)

  const handleGenerate = async () => {
    if (!description.trim()) {
      toast('请输入策略描述', 'error')
      return
    }
    setGenerating(true)
    setResult(null)
    try {
      const res = await strategyApi.nlGenerate(description, name || undefined, autoCreate)
      setResult(res)
      if (res.strategy_id) {
        toast('策略已生成并创建', 'success')
      } else {
        toast('代码已生成', 'success')
      }
    } catch (e: any) {
      toast(e.message, 'error')
    }
    setGenerating(false)
  }

  const handleCopy = () => {
    if (result?.source_code) {
      navigator.clipboard.writeText(result.source_code)
      setCopied(true)
      toast('已复制到剪贴板', 'success')
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const handleSave = async () => {
    if (!result?.source_code) return
    try {
      await strategyApi.create({
        name: name || 'AI 生成策略',
        description: description,
        source_code: result.source_code,
        category: 'AI生成',
        tags: ['AI', 'NL生成'],
      })
      toast('策略已保存', 'success')
    } catch (e: any) {
      toast(e.message, 'error')
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Hero */}
      <Card className="relative overflow-hidden p-6">
        <div className="relative z-10">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-cyan-500 flex items-center justify-center glow">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <h2 className="text-lg font-bold">AI 策略生成</h2>
            <Badge color="blue">Beta</Badge>
          </div>
          <p className="text-sm text-slate-400">用自然语言描述你的交易策略，AI 自动生成可执行的策略代码</p>
        </div>
        <div className="absolute -right-4 -top-4 w-40 h-40 bg-accent/10 rounded-full blur-3xl" />
      </Card>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Input */}
        <div className="space-y-4">
          <Card>
            <CardHeader title="策略描述" />
            <div className="p-5 space-y-4">
              <Input
                label="策略名称（可选）"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="例如：双均线交叉策略"
              />
              <Textarea
                label="用自然语言描述你的策略"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={6}
                placeholder="描述策略的入场、出场条件，以及风险管理规则..."
              />

              {/* Examples */}
              <div>
                <div className="flex items-center gap-1.5 text-xs text-slate-500 mb-2">
                  <Lightbulb className="w-3.5 h-3.5" /> 参考示例
                </div>
                <div className="space-y-1.5">
                  {EXAMPLES.map((ex, i) => (
                    <button
                      key={i}
                      onClick={() => setDescription(ex)}
                      className="block w-full text-left text-xs text-slate-400 hover:text-accent-light px-3 py-2 bg-surface2 rounded-lg transition-all hover:bg-surface3"
                    >
                      {ex}
                    </button>
                  ))}
                </div>
              </div>

              {/* Auto create toggle */}
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoCreate}
                  onChange={(e) => setAutoCreate(e.target.checked)}
                  className="w-4 h-4 rounded accent-accent"
                />
                <span className="text-sm text-slate-400">自动创建策略到我的策略库</span>
              </label>

              <Button onClick={handleGenerate} disabled={generating || !description.trim()} className="w-full">
                {generating ? (
                  <><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin inline mr-1.5" /> AI 生成中...</>
                ) : (
                  <><Wand2 className="w-4 h-4 inline mr-1.5" /> 生成策略</>
                )}
              </Button>
            </div>
          </Card>
        </div>

        {/* Output */}
        <div className="space-y-4">
          {generating ? (
            <Card className="p-8">
              <Loading text="AI 正在生成策略代码..." />
              <div className="mt-4 text-center text-xs text-slate-600">
                <Sparkles className="w-5 h-5 mx-auto mb-2 text-accent animate-pulse" />
                AI 正在分析你的策略描述并生成代码
              </div>
            </Card>
          ) : result ? (
            <Card>
              <CardHeader
                title="生成结果"
                action={
                  <div className="flex gap-2">
                    <Button size="sm" variant="ghost" onClick={handleCopy}>
                      {copied ? <Check className="w-3.5 h-3.5 inline mr-1" /> : <Copy className="w-3.5 h-3.5 inline mr-1" />}
                      {copied ? '已复制' : '复制'}
                    </Button>
                    {!result.strategy_id && (
                      <Button size="sm" onClick={handleSave}>
                        <Save className="w-3.5 h-3.5 inline mr-1" /> 保存
                      </Button>
                    )}
                  </div>
                }
              />
              <div className="p-5">
                {result.description && (
                  <div className="mb-4 p-3 bg-surface2 rounded-lg">
                    <div className="text-xs text-slate-500 mb-1">AI 解读</div>
                    <p className="text-sm text-slate-300">{result.description}</p>
                  </div>
                )}
                {result.strategy_id && (
                  <div className="mb-4 flex items-center gap-2 p-3 bg-green-500/10 rounded-lg">
                    <Check className="w-4 h-4 text-green-400" />
                    <span className="text-sm text-green-400">策略已自动创建，ID: {result.strategy_id.slice(0, 8)}...</span>
                  </div>
                )}
                {result.create_error && (
                  <div className="mb-4 p-3 bg-orange-500/10 rounded-lg">
                    <span className="text-sm text-orange-400">自动创建失败：{typeof result.create_error === 'string' ? result.create_error : JSON.stringify(result.create_error)}</span>
                  </div>
                )}
                <div>
                  <div className="flex items-center gap-1.5 text-xs text-slate-500 mb-2">
                    <Code2 className="w-3.5 h-3.5" /> 生成的策略代码
                  </div>
                  <pre className="bg-[#0a0d12] border border-border rounded-lg p-4 text-sm font-mono text-slate-300 overflow-x-auto max-h-[400px] overflow-y-auto">
                    <code>{result.source_code}</code>
                  </pre>
                </div>
              </div>
            </Card>
          ) : (
            <Card className="p-8">
              <div className="text-center text-slate-600">
                <Bot className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p className="text-sm">在左侧输入策略描述，AI 将为你生成代码</p>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
