const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface FetchOptions extends RequestInit {
  timeout?: number;
}

async function fetchWithTimeout(
  url: string,
  options: FetchOptions = {}
): Promise<Response> {
  const { timeout = 30000, ...fetchOptions } = options;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(url, {
      ...fetchOptions,
      signal: controller.signal,
    });
    return response;
  } finally {
    clearTimeout(timeoutId);
  }
}

// Guru API
export async function getGurus() {
  const response = await fetchWithTimeout(`${API_URL}/api/feed/gurus`);
  if (!response.ok) throw new Error("Failed to fetch gurus");
  return response.json();
}

export async function getUserGurus(userId: string) {
  const response = await fetchWithTimeout(`${API_URL}/api/users/${userId}/gurus`);
  if (!response.ok) throw new Error("Failed to fetch user gurus");
  return response.json();
}

export async function updateUserGurus(userId: string, guruIds: string[]) {
  const response = await fetchWithTimeout(`${API_URL}/api/users/${userId}/gurus`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ guru_ids: guruIds }),
  });
  if (!response.ok) throw new Error("Failed to update user gurus");
  return response.json();
}

// Feed API
export async function getFeed(params: {
  userId?: string;
  guruIds?: string[];
  limit?: number;
  offset?: number;
}) {
  const searchParams = new URLSearchParams();

  if (params.userId) searchParams.set("user_id", params.userId);
  if (params.guruIds?.length) searchParams.set("guru_ids", params.guruIds.join(","));
  if (params.limit) searchParams.set("limit", params.limit.toString());
  if (params.offset) searchParams.set("offset", params.offset.toString());

  const url = `${API_URL}/api/feed?${searchParams.toString()}`;
  const response = await fetchWithTimeout(url);

  if (!response.ok) throw new Error("Failed to fetch feed");
  return response.json();
}

// Chat API
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: {
    title: string;
    url?: string;
    type: string;
    relevance_score?: number;
  }[];
  created_at: string;
}

export interface ChatResponse {
  message: ChatMessage;
  cached: boolean;
  analytics_id?: string;
}

export async function sendChatMessage(
  query: string,
  userId?: string
): Promise<ChatResponse> {
  const response = await fetchWithTimeout(`${API_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, user_id: userId }),
    timeout: 60000, // 챗봇은 더 긴 타임아웃
  });

  if (!response.ok) throw new Error("Failed to send message");
  return response.json();
}

export async function getChatStats() {
  const response = await fetchWithTimeout(`${API_URL}/api/chat/stats`);
  if (!response.ok) throw new Error("Failed to fetch chat stats");
  return response.json();
}

// User API
export async function getUserByGoogleId(googleId: string) {
  const response = await fetchWithTimeout(`${API_URL}/api/users/by-google/${googleId}`);
  if (!response.ok) {
    if (response.status === 404) return null;
    throw new Error("Failed to fetch user");
  }
  return response.json();
}

// Analytics API (Phase 3)
export interface AnalyticsSummary {
  period_days: number;
  total_queries: number;
  source_distribution: Record<string, number>;
  feedback: {
    positive: number;
    negative: number;
    total: number;
  };
  avg_latency_ms: number | null;
}

export interface PopularQuery {
  query: string;
  count: number;
  positive_feedback: number;
  negative_feedback: number;
}

export interface RecentQuery {
  id: string;
  query: string;
  source_type: string;
  feedback: number | null;
  latency_ms: number | null;
  created_at: string;
}

export interface DashboardData {
  summary: AnalyticsSummary;
  popular_queries: PopularQuery[];
  recent_queries: RecentQuery[];
  negative_feedback_queries: { query: string; total_count: number; negative_count: number }[];
}

export async function getAnalyticsDashboard(days: number = 7): Promise<DashboardData> {
  const response = await fetchWithTimeout(`${API_URL}/api/analytics/dashboard?days=${days}`);
  if (!response.ok) throw new Error("Failed to fetch dashboard data");
  return response.json();
}

export async function submitFeedback(analyticsId: string, feedback: 1 | -1): Promise<void> {
  const response = await fetchWithTimeout(`${API_URL}/api/analytics/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ analytics_id: analyticsId, feedback }),
  });
  if (!response.ok) throw new Error("Failed to submit feedback");
}

// Learning API (Phase 4)
export interface LearningStats {
  cache: {
    total_entries: number;
    total_hits: number;
    expired_entries: number;
  };
  improvement_candidates: number;
  last_learning_run: string | null;
  is_running: boolean;
}

export interface LearningStatus {
  is_running: boolean;
  last_run: string | null;
  last_result: {
    started_at?: string;
    completed_at?: string;
    pre_warming?: { total_popular: number; warmed: number; skipped: number; errors: number };
    response_improvement?: { total_negative: number; improved: number; errors: number };
    cache_cleanup?: { deleted: number; cutoff_date: string };
  } | null;
}

export async function getLearningStats(): Promise<LearningStats> {
  const response = await fetchWithTimeout(`${API_URL}/api/learning/stats`);
  if (!response.ok) throw new Error("Failed to fetch learning stats");
  return response.json();
}

export async function getLearningStatus(): Promise<LearningStatus> {
  const response = await fetchWithTimeout(`${API_URL}/api/learning/status`);
  if (!response.ok) throw new Error("Failed to fetch learning status");
  return response.json();
}

export async function triggerLearningCycle(): Promise<{ task_id: string; status: string; message: string }> {
  const response = await fetchWithTimeout(`${API_URL}/api/learning/run`, {
    method: "POST",
  });
  if (!response.ok) throw new Error("Failed to trigger learning cycle");
  return response.json();
}

export async function preWarmCache(days: number = 7, minCount: number = 3, limit: number = 20): Promise<any> {
  const response = await fetchWithTimeout(`${API_URL}/api/learning/pre-warm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ days, min_count: minCount, limit }),
  });
  if (!response.ok) throw new Error("Failed to pre-warm cache");
  return response.json();
}

export async function cleanupCache(maxAgeDays: number = 30, minHitCount: number = 0): Promise<any> {
  const response = await fetchWithTimeout(`${API_URL}/api/learning/cleanup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ max_age_days: maxAgeDays, min_hit_count: minHitCount }),
  });
  if (!response.ok) throw new Error("Failed to cleanup cache");
  return response.json();
}
