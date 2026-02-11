import { Role } from "@/util/interfaces";
import { FileSpreadsheet, User } from "lucide-react";

interface ChatMessageProperties {
  role: Role;
  content: string;
}

export function ChatMessage({ role, content }: ChatMessageProperties) {
  // Check if the role of the message is the user
  const isUser = role === Role.USER;

  // HTML for the chat message
  return (
    <div
      className={`flex gap-4 p-6
        ${isUser ? "bg-gray-800" : "bg-gray-800/50"}
    `}
    >
      <div className="shrink-0">
        {/* If its the user's message, make background blue */}
        {/* Otherwise, make background green */}
        <div
          className={`w-8 h-8 rounded-full flex items-center justify-center
            ${isUser ? "bg-blue-500 text-white" : "bg-green-500 text-white"}
        `}
        >
          {isUser ? <User size={22} /> : <FileSpreadsheet size={22} />}
        </div>
      </div>

      {/* Message contents */}
      <div className="flex-1 min-w-0">
        <div className="text-sm text-gray-100 py-1">{content}</div>
      </div>
    </div>
  );
}
