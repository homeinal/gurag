"use client";

import { useState, useRef, useEffect } from "react";
import { useSession } from "next-auth/react";
import { sendChatMessage, ChatMessage, getChatStats } from "@/lib/api-client";
import { ChatInput } from "@/components/chat/ChatInput";
import { ChatMessageBubble } from "@/components/chat/ChatMessage";

interface MessageWithAnalytics {
  message: ChatMessage;
  analyticsId?: string;
}

export default function ChatPage() {
  const { data: session } = useSession();
  const [messages, setMessages] = useState<MessageWithAnalytics[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<{ document_count: number; features?: string[] } | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getChatStats()
      .then(setStats)
      .catch(() => setStats({ document_count: 0, features: [] }));
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSendMessage = async (query: string) => {
    if (!query.trim() || isLoading) return;

    // 사용자 메시지 추가
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: query,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, { message: userMessage }]);
    setIsLoading(true);
    setError(null);

    try {
      const response = await sendChatMessage(query, session?.user?.id);
      setMessages((prev) => [
        ...prev,
        { message: response.message, analyticsId: response.analytics_id },
      ]);
    } catch (err) {
      setError("메시지 전송에 실패했습니다. 다시 시도해주세요.");
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-64px)]">
      {/* Header */}
      <div className="border-b border-gray-200 bg-white px-4 py-3">
        <div className="max-w-3xl mx-auto flex justify-between items-center">
          <div>
            <h1 className="text-lg font-semibold text-gray-900">AI 챗봇</h1>
            <p className="text-sm text-gray-500">
              RAG + arXiv + HuggingFace 통합 검색
            </p>
          </div>
          {stats && (
            <div className="flex items-center gap-3 text-xs">
              <span className="text-gray-400">
                {stats.document_count > 0
                  ? `${stats.document_count}개 문서`
                  : "준비 중..."}
              </span>
              {stats.features && stats.features.length > 0 && (
                <div className="flex gap-1">
                  {stats.features.includes("mcp_arxiv") && (
                    <span className="px-1.5 py-0.5 bg-red-100 text-red-600 rounded text-[10px]">arXiv</span>
                  )}
                  {stats.features.includes("mcp_huggingface") && (
                    <span className="px-1.5 py-0.5 bg-yellow-100 text-yellow-600 rounded text-[10px]">HF</span>
                  )}
                  {stats.features.includes("rag") && (
                    <span className="px-1.5 py-0.5 bg-blue-100 text-blue-600 rounded text-[10px]">RAG</span>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-3xl mx-auto space-y-6">
          {messages.length === 0 ? (
            <div className="text-center py-12">
              <div className="text-4xl mb-4">💬</div>
              <h2 className="text-xl font-semibold text-gray-900 mb-2">
                AI에 대해 무엇이든 물어보세요
              </h2>
              <p className="text-gray-500 mb-6">
                지식 베이스, arXiv 논문, HuggingFace를 통합 검색합니다
              </p>

              {/* RAG 질문 */}
              <div className="mb-4">
                <div className="text-xs text-gray-400 mb-2">개념 질문 (RAG)</div>
                <div className="flex flex-wrap justify-center gap-2">
                  {[
                    "Transformer가 뭐야?",
                    "BERT와 GPT 차이점",
                    "RAG 시스템 설명해줘",
                  ].map((suggestion) => (
                    <button
                      key={suggestion}
                      onClick={() => handleSendMessage(suggestion)}
                      className="px-3 py-1.5 text-sm bg-blue-50 text-blue-700 rounded-full hover:bg-blue-100 transition-colors"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>

              {/* MCP 질문 */}
              <div className="mb-4">
                <div className="text-xs text-gray-400 mb-2">실시간 검색 (arXiv/HF)</div>
                <div className="flex flex-wrap justify-center gap-2">
                  {[
                    "최신 LLM 논문 찾아줘",
                    "요즘 뜨는 AI 모델",
                    "Diffusion 최신 연구",
                  ].map((suggestion) => (
                    <button
                      key={suggestion}
                      onClick={() => handleSendMessage(suggestion)}
                      className="px-3 py-1.5 text-sm bg-red-50 text-red-700 rounded-full hover:bg-red-100 transition-colors"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>

              {/* Hybrid 질문 */}
              <div>
                <div className="text-xs text-gray-400 mb-2">복합 질문 (RAG + MCP)</div>
                <div className="flex flex-wrap justify-center gap-2">
                  {[
                    "최신 Transformer 연구 동향 설명해줘",
                    "RLHF 개념과 최근 논문",
                  ].map((suggestion) => (
                    <button
                      key={suggestion}
                      onClick={() => handleSendMessage(suggestion)}
                      className="px-3 py-1.5 text-sm bg-purple-50 text-purple-700 rounded-full hover:bg-purple-100 transition-colors"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            messages.map((item) => (
              <ChatMessageBubble
                key={item.message.id}
                message={item.message}
                analyticsId={item.analyticsId}
              />
            ))
          )}

          {isLoading && (
            <div className="flex items-center gap-2 text-gray-500">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                <span
                  className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                  style={{ animationDelay: "0.2s" }}
                />
                <span
                  className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                  style={{ animationDelay: "0.4s" }}
                />
              </div>
              <span className="text-sm">답변 생성 중...</span>
            </div>
          )}

          {error && (
            <div className="bg-red-50 text-red-600 p-3 rounded-lg text-sm">
              {error}
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 bg-white px-4 py-4">
        <div className="max-w-3xl mx-auto">
          <ChatInput onSend={handleSendMessage} disabled={isLoading} />
        </div>
      </div>
    </div>
  );
}
