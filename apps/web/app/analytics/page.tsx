"use client";

import { useEffect, useState } from "react";
import { getAnalyticsDashboard, DashboardData } from "@/lib/api-client";

const SOURCE_COLORS: Record<string, string> = {
  rag: "bg-blue-100 text-blue-800",
  mcp: "bg-purple-100 text-purple-800",
  hybrid: "bg-green-100 text-green-800",
  cache: "bg-gray-100 text-gray-800",
};

export default function AnalyticsPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(7);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const dashboard = await getAnalyticsDashboard(days);
        setData(dashboard);
      } catch (err) {
        setError("데이터를 불러오는데 실패했습니다.");
        console.error(err);
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [days]);

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-8">
        <div className="animate-pulse space-y-6">
          <div className="h-8 bg-gray-200 rounded w-48" />
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-24 bg-gray-200 rounded-xl" />
            ))}
          </div>
          <div className="h-64 bg-gray-200 rounded-xl" />
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-8">
        <div className="bg-red-50 text-red-600 p-4 rounded-xl">
          {error || "데이터를 불러올 수 없습니다."}
        </div>
      </div>
    );
  }

  const { summary, popular_queries, recent_queries, negative_feedback_queries } = data;

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Analytics Dashboard</h1>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
        >
          <option value={7}>최근 7일</option>
          <option value={14}>최근 14일</option>
          <option value={30}>최근 30일</option>
        </select>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-white rounded-xl p-6 shadow-sm border">
          <p className="text-sm text-gray-500 mb-1">총 쿼리 수</p>
          <p className="text-3xl font-bold text-gray-900">{summary.total_queries}</p>
        </div>
        <div className="bg-white rounded-xl p-6 shadow-sm border">
          <p className="text-sm text-gray-500 mb-1">평균 응답시간</p>
          <p className="text-3xl font-bold text-gray-900">
            {summary.avg_latency_ms ? `${summary.avg_latency_ms}ms` : "-"}
          </p>
        </div>
        <div className="bg-white rounded-xl p-6 shadow-sm border">
          <p className="text-sm text-gray-500 mb-1">좋아요</p>
          <p className="text-3xl font-bold text-green-600">{summary.feedback.positive}</p>
        </div>
        <div className="bg-white rounded-xl p-6 shadow-sm border">
          <p className="text-sm text-gray-500 mb-1">싫어요</p>
          <p className="text-3xl font-bold text-red-600">{summary.feedback.negative}</p>
        </div>
      </div>

      {/* Source Distribution */}
      <div className="bg-white rounded-xl p-6 shadow-sm border mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">소스 타입 분포</h2>
        <div className="flex flex-wrap gap-4">
          {Object.entries(summary.source_distribution).map(([source, count]) => (
            <div key={source} className="flex items-center gap-2">
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${SOURCE_COLORS[source] || "bg-gray-100 text-gray-800"}`}>
                {source.toUpperCase()}
              </span>
              <span className="text-gray-600">{count}건</span>
            </div>
          ))}
          {Object.keys(summary.source_distribution).length === 0 && (
            <p className="text-gray-500">데이터가 없습니다.</p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Popular Queries */}
        <div className="bg-white rounded-xl p-6 shadow-sm border">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">인기 쿼리 TOP 10</h2>
          {popular_queries.length > 0 ? (
            <div className="space-y-3">
              {popular_queries.map((q, i) => (
                <div key={i} className="flex items-start justify-between gap-4 py-2 border-b last:border-0">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-900 truncate">{q.query}</p>
                    <div className="flex gap-2 mt-1">
                      <span className="text-xs text-gray-500">{q.count}회</span>
                      {q.positive_feedback > 0 && (
                        <span className="text-xs text-green-600">+{q.positive_feedback}</span>
                      )}
                      {q.negative_feedback > 0 && (
                        <span className="text-xs text-red-600">-{q.negative_feedback}</span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-center py-8">데이터가 없습니다.</p>
          )}
        </div>

        {/* Recent Queries */}
        <div className="bg-white rounded-xl p-6 shadow-sm border">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">최근 쿼리</h2>
          {recent_queries.length > 0 ? (
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {recent_queries.map((q) => (
                <div key={q.id} className="py-2 border-b last:border-0">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm text-gray-900 flex-1">{q.query}</p>
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${SOURCE_COLORS[q.source_type] || "bg-gray-100 text-gray-800"}`}>
                      {q.source_type}
                    </span>
                  </div>
                  <div className="flex gap-3 mt-1 text-xs text-gray-500">
                    <span>{new Date(q.created_at).toLocaleString("ko-KR")}</span>
                    {q.latency_ms && <span>{q.latency_ms}ms</span>}
                    {q.feedback === 1 && <span className="text-green-600">+1</span>}
                    {q.feedback === -1 && <span className="text-red-600">-1</span>}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-center py-8">데이터가 없습니다.</p>
          )}
        </div>
      </div>

      {/* Negative Feedback Queries */}
      {negative_feedback_queries.length > 0 && (
        <div className="bg-white rounded-xl p-6 shadow-sm border mt-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">개선 필요 쿼리 (부정 피드백)</h2>
          <div className="space-y-3">
            {negative_feedback_queries.map((q, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b last:border-0">
                <p className="text-sm text-gray-900">{q.query}</p>
                <div className="flex gap-2 text-xs">
                  <span className="text-gray-500">총 {q.total_count}회</span>
                  <span className="text-red-600">부정 {q.negative_count}회</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
