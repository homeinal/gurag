"use client";

import { useState } from "react";
import { ChatMessage, submitFeedback } from "@/lib/api-client";

interface ChatMessageBubbleProps {
  message: ChatMessage;
  analyticsId?: string;
}

const SOURCE_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  arxiv: { bg: "bg-red-100", text: "text-red-700", label: "arXiv" },
  huggingface: { bg: "bg-yellow-100", text: "text-yellow-700", label: "HF" },
  rag: { bg: "bg-blue-100", text: "text-blue-700", label: "RAG" },
  cache: { bg: "bg-green-100", text: "text-green-700", label: "Cache" },
  unknown: { bg: "bg-gray-100", text: "text-gray-600", label: "unknown" },
};

export function ChatMessageBubble({ message, analyticsId }: ChatMessageBubbleProps) {
  const isUser = message.role === "user";
  const [feedback, setFeedback] = useState<1 | -1 | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const getSourceStyle = (type: string) => {
    return SOURCE_STYLES[type] || SOURCE_STYLES.unknown;
  };

  const handleFeedback = async (value: 1 | -1) => {
    if (!analyticsId || submitting || feedback !== null) return;

    setSubmitting(true);
    try {
      await submitFeedback(analyticsId, value);
      setFeedback(value);
    } catch (err) {
      console.error("Failed to submit feedback:", err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] ${
          isUser
            ? "bg-primary-600 text-white rounded-2xl rounded-br-md"
            : "bg-white border border-gray-200 text-gray-800 rounded-2xl rounded-bl-md"
        } px-4 py-3 shadow-sm`}
      >
        {/* Content */}
        <div className="whitespace-pre-wrap leading-relaxed">
          {message.content}
        </div>

        {/* Sources (assistant only) */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-100">
            <div className="text-xs text-gray-500 mb-2 flex items-center gap-2">
              <span>sources</span>
              <span className="text-gray-300">|</span>
              <span className="text-gray-400">{message.sources.length}</span>
            </div>
            <div className="space-y-1.5">
              {message.sources.slice(0, 5).map((source, index) => {
                const style = getSourceStyle(source.type);
                return (
                  <div
                    key={index}
                    className="flex items-center gap-2 text-xs text-gray-600"
                  >
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${style.bg} ${style.text}`}
                    >
                      {style.label}
                    </span>
                    {source.url ? (
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="hover:text-primary-600 truncate flex-1"
                        title={source.title}
                      >
                        {source.title}
                      </a>
                    ) : (
                      <span className="truncate flex-1" title={source.title}>
                        {source.title}
                      </span>
                    )}
                    {source.relevance_score !== undefined && source.relevance_score !== null && (
                      <span className="text-gray-400 text-[10px] shrink-0">
                        {Math.round(source.relevance_score * 100)}%
                      </span>
                    )}
                  </div>
                );
              })}
              {message.sources.length > 5 && (
                <div className="text-[10px] text-gray-400 mt-1">
                  +{message.sources.length - 5}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Feedback Buttons (assistant only, with analyticsId) */}
        {!isUser && analyticsId && (
          <div className="mt-3 pt-3 border-t border-gray-100 flex items-center gap-2">
            <span className="text-xs text-gray-400">feedback:</span>
            <button
              onClick={() => handleFeedback(1)}
              disabled={submitting || feedback !== null}
              className={`p-1.5 rounded-lg transition-colors ${
                feedback === 1
                  ? "bg-green-100 text-green-600"
                  : feedback !== null
                  ? "text-gray-300 cursor-not-allowed"
                  : "text-gray-400 hover:bg-gray-100 hover:text-green-600"
              }`}
              title="helpful"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 20 20"
                fill="currentColor"
                className="w-4 h-4"
              >
                <path d="M1 8.25a1.25 1.25 0 1 1 2.5 0v7.5a1.25 1.25 0 1 1-2.5 0v-7.5ZM11 3V1.7c0-.268.14-.526.395-.607A2 2 0 0 1 14 3c0 .995-.182 1.948-.514 2.826-.204.54.166 1.174.744 1.174h2.52c1.243 0 2.261 1.01 2.146 2.247a23.864 23.864 0 0 1-1.341 5.974 1.75 1.75 0 0 1-1.65 1.129H6.25a.75.75 0 0 1-.75-.75v-7.124a.75.75 0 0 1 .124-.416l4.257-6.254A.75.75 0 0 1 10.75 1h.25Z" />
              </svg>
            </button>
            <button
              onClick={() => handleFeedback(-1)}
              disabled={submitting || feedback !== null}
              className={`p-1.5 rounded-lg transition-colors ${
                feedback === -1
                  ? "bg-red-100 text-red-600"
                  : feedback !== null
                  ? "text-gray-300 cursor-not-allowed"
                  : "text-gray-400 hover:bg-gray-100 hover:text-red-600"
              }`}
              title="not helpful"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 20 20"
                fill="currentColor"
                className="w-4 h-4"
              >
                <path d="M18.905 12.75a1.25 1.25 0 0 1-2.5 0v-7.5a1.25 1.25 0 0 1 2.5 0v7.5ZM8.905 17v1.3c0 .268-.14.526-.395.607A2 2 0 0 1 5.905 17c0-.995.182-1.948.514-2.826.204-.54-.166-1.174-.744-1.174h-2.52c-1.243 0-2.261-1.01-2.146-2.247.193-2.08.651-4.082 1.341-5.974A1.75 1.75 0 0 1 4 3.65h9.655a.75.75 0 0 1 .75.75v7.124a.75.75 0 0 1-.124.416l-4.257 6.254a.75.75 0 0 1-.869.276h-.25Z" />
              </svg>
            </button>
            {feedback !== null && (
              <span className="text-xs text-gray-400 ml-1">thank you!</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
