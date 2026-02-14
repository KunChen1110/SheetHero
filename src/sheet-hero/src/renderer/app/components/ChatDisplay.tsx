import { Chat } from "@/util/interfaces";
import { MessageSquare } from "lucide-react";
import { SidebarWidget } from "./SidebarWidget";

// Properties needed for the chat display
interface ChatDisplayProperties {
  chats: Chat[];
  activeChat?: string;
  onChatSelect: (chatId: string) => void;
  onNewChat: () => void;
}

export function ChatDisplay({
  chats,
  activeChat,
  onChatSelect,
}: ChatDisplayProperties) {
  // HTML for the chat display
  return (
    <div className="p-3">
      <div className="space-y-1">
        {/* List of all chats */}
        {chats.map((chat) => (
          <SidebarWidget
            className={`
              ${
                activeChat === chat.id
                  ? "bg-green-900 hover:bg-green-900 border-green-500"
                  : "hover:bg-gray-800/20"
              }
            `}
            key={chat.id}
            onWidgetClick={() => onChatSelect?.(chat.id)}
            title={chat.title}
            icon={
              <MessageSquare
                size={14}
                className={`shrink-0 
                    ${
                      activeChat === chat.id
                        ? "text-green-400"
                        : "text-gray-400 group-hover:text-green-400"
                    }
                  `}
              />
            }
          />
        ))}
      </div>
    </div>
  );
}
