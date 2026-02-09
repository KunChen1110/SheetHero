import { Role } from "@/renderer/interfaces";

interface ChatMessageProperties {
  role: Role;
  content: string;
}

export function ChatMessage({ role, content }: ChatMessageProperties) {
  const isUser = role === Role.USER;

  return (
    <div
      className={`flex gap-4 p-6
        ${isUser ? "bg-gray-800/50" : "bg-gray-750/50"}
    `}
    >
      <div className="shrink-0">
        {/* If its the user's message, make background blue */}
        {/* Otherwise, make background green */}
        <div
          className={`w-8 h-8 rounded-full flex 
            ${isUser ? "bg-blue-500  text-white" : "bg-green-500 text-white"}
        `}
        ></div>
      </div>

      {/* Message contents */}
      <div className="flex-1 min-w-0">
        <div className="text-sm text-gray-100">{content}</div>
      </div>
    </div>
  );
}
