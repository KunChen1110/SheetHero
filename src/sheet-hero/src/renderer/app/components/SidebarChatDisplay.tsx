import { Chat } from "@/util/interfaces";
import { MessageSquare } from "lucide-react";
import { SidebarWidget } from "./SidebarWidget";

// Properties needed for the sidebar chat display
interface SidebarChatDisplayProperties {
  chats: Chat[];
  activeChat?: string;
  onChatSelect: (chatId: string) => void;
  onNewChat: () => void;
}

export function SidebarChatDisplay({
  chats,
  activeChat,
  onChatSelect,
}: SidebarChatDisplayProperties) {
  // HTML for the sidebar chat display
  return (
    <div className="p-3">
      <div className="space-y-1">
        {/* List of all chats */}
        {chats.map((chat) => (
          <SidebarWidget
            className={`
              ${activeChat === chat.id && "bg-(--sh-green) hover:bg-(--sh-green-hover)/50 border-(--sh-green-highlight) text-(--sh-white)"}
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
                        ? "text-(--sh-green-highlight)"
                        : "text-(--sh-medium-grey)"
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
