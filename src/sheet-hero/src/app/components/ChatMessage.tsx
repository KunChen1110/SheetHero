import { Role } from "@/app/Interfaces";

interface ChatMessageProperties {
  role: Role;
  content: string;
}

export function ChatMessage({ role, content }: ChatMessageProperties) {
  const isUser = role === Role.USER;

  return (
    <div
      className={`flex gap-4 px-6 py-6
        ${isUser ? "bg-gray-800/50" : "bg-gray-750/50"}
    `}
    >
      <div className="shrink-0">
        {/* If its the user's message, make background blue */}
        {/* Otherwise, make background green */}
        <div
          className={`w-8 h-8 rounded-full flex items-center justify-center 
            ${
              isUser
                ? "bg-blue-500  text-white shadow-lg shadow-blue-500/20"
                : "bg-green-500 text-white shadow-lg shadow-green-500/30"
            }
        `}
        ></div>
      </div>

      {/* Message contents */}
      <div className="flex-1 min-w-0">
        <div className="text-sm text-gray-100 whitespace-pre-wrap wrap-break-words leading-relaxed">
          {content}
        </div>
      </div>
    </div>
  );
}
