import { ChatMessage } from "@/lib/api-client";

interface ChatMessageBubbleProps {
  message: ChatMessage;
}

const SOURCE_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  arxiv: { bg: "bg-red-100", text: "text-red-700", label: "arXiv" },
  huggingface: { bg: "bg-yellow-100", text: "text-yellow-700", label: "HF" },
  rag: { bg: "bg-blue-100", text: "text-blue-700", label: "RAG" },
  cache: { bg: "bg-green-100", text: "text-green-700", label: "Cache" },
  unknown: { bg: "bg-gray-100", text: "text-gray-600", label: "기타" },
};

export function ChatMessageBubble({ message }: ChatMessageBubbleProps) {
  const isUser = message.role === "user";

  const getSourceStyle = (type: string) => {
    return SOURCE_STYLES[type] || SOURCE_STYLES.unknown;
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
              <span>참고 자료</span>
              <span className="text-gray-300">|</span>
              <span className="text-gray-400">{message.sources.length}개 소스</span>
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
                  +{message.sources.length - 5}개 더 보기
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
