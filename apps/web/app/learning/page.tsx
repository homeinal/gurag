"use client";

import { useEffect, useState } from "react";
import {
  getLearningStats,
  getLearningStatus,
  triggerLearningCycle,
  preWarmCache,
  cleanupCache,
  LearningStats,
  LearningStatus,
} from "@/lib/api-client";

export default function LearningPage() {
  const [stats, setStats] = useState<LearningStats | null>(null);
  const [status, setStatus] = useState<LearningStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const loadData = async () => {
    try {
      const [statsData, statusData] = await Promise.all([
        getLearningStats(),
        getLearningStatus(),
      ]);
      setStats(statsData);
      setStatus(statusData);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    // Poll for status updates
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleRunCycle = async () => {
    setActionLoading("run");
    setMessage(null);
    try {
      await triggerLearningCycle();
      setMessage({ type: "success", text: "Learning cycle started" });
      loadData();
    } catch (err) {
      setMessage({ type: "error", text: "Failed to start learning cycle" });
    } finally {
      setActionLoading(null);
    }
  };

  const handlePreWarm = async () => {
    setActionLoading("prewarm");
    setMessage(null);
    try {
      const result = await preWarmCache(7, 2, 20);
      setMessage({
        type: "success",
        text: `Pre-warmed ${result.warmed} queries (skipped: ${result.skipped})`,
      });
      loadData();
    } catch (err) {
      setMessage({ type: "error", text: "Failed to pre-warm cache" });
    } finally {
      setActionLoading(null);
    }
  };

  const handleCleanup = async () => {
    setActionLoading("cleanup");
    setMessage(null);
    try {
      const result = await cleanupCache(30, 0);
      setMessage({
        type: "success",
        text: `Cleaned up ${result.deleted} stale cache entries`,
      });
      loadData();
    } catch (err) {
      setMessage({ type: "error", text: "Failed to cleanup cache" });
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="animate-pulse space-y-6">
          <div className="h-8 bg-gray-200 rounded w-48" />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-24 bg-gray-200 rounded-xl" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Self-Learning</h1>
          <p className="text-sm text-gray-500">Phase 4: AI learning</p>
        </div>
        {status?.is_running && (
          <span className="px-3 py-1 bg-yellow-100 text-yellow-800 rounded-full text-sm font-medium animate-pulse">
            Running...
          </span>
        )}
      </div>

      {/* Message */}
      {message && (
        <div
          className={`mb-6 p-4 rounded-lg ${
            message.type === "success"
              ? "bg-green-50 text-green-800"
              : "bg-red-50 text-red-800"
          }`}
        >
          {message.text}
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-white rounded-xl p-6 shadow-sm border">
          <p className="text-sm text-gray-500 mb-1">Cache</p>
          <p className="text-3xl font-bold text-gray-900">{stats?.cache.total_entries || 0}</p>
          <p className="text-xs text-gray-400 mt-1">
            {stats?.cache.total_hits || 0} hits
          </p>
        </div>
        <div className="bg-white rounded-xl p-6 shadow-sm border">
          <p className="text-sm text-gray-500 mb-1">Expired</p>
          <p className="text-3xl font-bold text-orange-600">{stats?.cache.expired_entries || 0}</p>
        </div>
        <div className="bg-white rounded-xl p-6 shadow-sm border">
          <p className="text-sm text-gray-500 mb-1">Need Improvement</p>
          <p className="text-3xl font-bold text-red-600">{stats?.improvement_candidates || 0}</p>
        </div>
        <div className="bg-white rounded-xl p-6 shadow-sm border">
          <p className="text-sm text-gray-500 mb-1">Last Run</p>
          <p className="text-sm font-medium text-gray-900">
            {stats?.last_learning_run
              ? new Date(stats.last_learning_run).toLocaleString("ko-KR")
              : "Never"}
          </p>
        </div>
      </div>

      {/* Actions */}
      <div className="bg-white rounded-xl p-6 shadow-sm border mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Actions</h2>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={handleRunCycle}
            disabled={status?.is_running || actionLoading !== null}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
          >
            {actionLoading === "run" ? "Starting..." : "Run Full Cycle"}
          </button>
          <button
            onClick={handlePreWarm}
            disabled={status?.is_running || actionLoading !== null}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
          >
            {actionLoading === "prewarm" ? "Running..." : "Pre-warm Cache"}
          </button>
          <button
            onClick={handleCleanup}
            disabled={status?.is_running || actionLoading !== null}
            className="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
          >
            {actionLoading === "cleanup" ? "Running..." : "Cleanup Cache"}
          </button>
        </div>
      </div>

      {/* Last Result */}
      {status?.last_result && (
        <div className="bg-white rounded-xl p-6 shadow-sm border">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Last Result</h2>
          <div className="space-y-4">
            {status.last_result.pre_warming && (
              <div className="p-4 bg-blue-50 rounded-lg">
                <h3 className="font-medium text-blue-800 mb-2">Pre-warming</h3>
                <div className="grid grid-cols-4 gap-2 text-sm">
                  <div>
                    <span className="text-blue-600">Total:</span>{" "}
                    {status.last_result.pre_warming.total_popular}
                  </div>
                  <div>
                    <span className="text-green-600">Warmed:</span>{" "}
                    {status.last_result.pre_warming.warmed}
                  </div>
                  <div>
                    <span className="text-gray-600">Skipped:</span>{" "}
                    {status.last_result.pre_warming.skipped}
                  </div>
                  <div>
                    <span className="text-red-600">Errors:</span>{" "}
                    {status.last_result.pre_warming.errors}
                  </div>
                </div>
              </div>
            )}

            {status.last_result.response_improvement && (
              <div className="p-4 bg-purple-50 rounded-lg">
                <h3 className="font-medium text-purple-800 mb-2">Response Improvement</h3>
                <div className="grid grid-cols-3 gap-2 text-sm">
                  <div>
                    <span className="text-purple-600">Total:</span>{" "}
                    {status.last_result.response_improvement.total_negative}
                  </div>
                  <div>
                    <span className="text-green-600">Improved:</span>{" "}
                    {status.last_result.response_improvement.improved}
                  </div>
                  <div>
                    <span className="text-red-600">Errors:</span>{" "}
                    {status.last_result.response_improvement.errors}
                  </div>
                </div>
              </div>
            )}

            {status.last_result.cache_cleanup && (
              <div className="p-4 bg-orange-50 rounded-lg">
                <h3 className="font-medium text-orange-800 mb-2">Cache Cleanup</h3>
                <div className="text-sm">
                  <span className="text-orange-600">Deleted:</span>{" "}
                  {status.last_result.cache_cleanup.deleted} entries
                </div>
              </div>
            )}

            <div className="text-xs text-gray-400 mt-2">
              {status.last_result.started_at && (
                <span>
                  Started: {new Date(status.last_result.started_at).toLocaleString("ko-KR")}
                </span>
              )}
              {status.last_result.completed_at && (
                <span className="ml-4">
                  Completed: {new Date(status.last_result.completed_at).toLocaleString("ko-KR")}
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Description */}
      <div className="mt-8 p-6 bg-gray-50 rounded-xl">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">How it works</h2>
        <ul className="space-y-2 text-sm text-gray-600">
          <li>
            <strong>Pre-warming:</strong> Popular queries are cached in advance for faster response
          </li>
          <li>
            <strong>Response Improvement:</strong> Responses with negative feedback are regenerated
          </li>
          <li>
            <strong>Cache Cleanup:</strong> Old and unused cache entries are removed
          </li>
          <li>
            <strong>TTL Extension:</strong> High-quality responses are cached for longer
          </li>
        </ul>
      </div>
    </div>
  );
}
