import { Chat } from "@/util/interfaces";
import { SidebarDataCapsule } from "./SidebarDataCapsule";

// Properties needed for the sidebar chat display
interface SidebarChatDisplayProperties {
  chats: Chat[];
  activeChat?: string;
  onChatSelect: (chatId: string) => void;
  onNewChat: () => void;
  onRemoveChat: (chatId: string) => void;
}

export function SidebarChatDisplay({
  chats,
  activeChat,
  onChatSelect,
  onRemoveChat,
}: SidebarChatDisplayProperties) {
  // HTML for the sidebar chat display
  return (
    <div className="p-3">
      <div className="space-y-2">
        {/* List of all chats */}
        {chats.map((chat) => (
          <SidebarDataCapsule
            key={chat.id}
            id={chat.id}
            text={chat.title}
            isActive={activeChat === chat.id}
            onClick={() => onChatSelect(chat.id)}
            onRemoveCapsule={onRemoveChat}
          />
        ))}
      </div>
    </div>
  );
}
