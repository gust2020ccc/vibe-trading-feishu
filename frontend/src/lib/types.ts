// API Types

export interface Strategy {
  id: string
  user_id: string
  name: string
  name_en?: string
  description?: string
  category?: string
  tags?: string[]
  source_code?: string
  meta?: any
  version: number
  status: 'draft' | 'testing' | 'published' | 'archived'
  parent_id?: string
  is_public?: boolean
  market_desc?: string
  subscriber_count?: number
  clone_count?: number
  rating_avg?: number
  rating_count?: number
  created_at?: string
  updated_at?: string
}

export interface Factor {
  id: string
  user_id: string
  name: string
  name_en?: string
  description?: string
  category?: string
  tags?: string[]
  source_code?: string
  version: number
  status: string
  created_at?: string
  updated_at?: string
}

export interface StrategyVersion {
  id: string
  strategy_id: string
  version: number
  source_code?: string
  meta?: any
  changelog?: string
  created_at: string
}

export interface BacktestTemplate {
  id: string
  name: string
  name_en?: string
  description?: string
  category?: string
  source?: string
  tier?: string
  markets?: string[]
  parameters?: Parameter[]
}

export interface Parameter {
  key: string
  label: string
  type: 'int' | 'float'
  default: number
  min?: number
  max?: number
}

export interface BacktestRun {
  run_id: string
  status: string
  strategy_name?: string
  symbols?: string[]
  created_at?: string
  metrics?: BacktestMetrics
}

export interface BacktestMetrics {
  total_return?: number
  annualized_return?: number
  sharpe_ratio?: number
  max_drawdown?: number
  win_rate?: number
  total_trades?: number
  final_equity?: number
}

export interface MarketplaceStats {
  strategies?: {
    published_count: number
    total_subscribers: number
    total_clones: number
    avg_rating: number
  }
  factors?: {
    published_count: number
    total_subscribers: number
    total_clones: number
    avg_rating: number
  }
}

export interface User {
  user_id: string
  name: string
  channel: string
  role: 'user' | 'admin' | 'operator'
  status: 'active' | 'disabled'
  created_at?: string
  updated_at?: string
  usage_summary?: {
    today_tokens: number
    month_tokens: number
    today_requests: number
    month_requests: number
  }
  quota?: {
    daily_token_limit: number
    monthly_token_limit: number
    concurrent_session_limit: number
    rate_limit_per_minute: number
  }
}

export interface NLGenerateResult {
  source_code: string
  description: string
  strategy_id?: string
  strategy?: Strategy
  create_error?: any
}
