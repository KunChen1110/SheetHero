import { Chat } from "@/util/interfaces";

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
  onNewChat,
}: ChatDisplayProperties) {
  // HTML for the chat display
  return (
    <div className="p-3">
      {/* Chats title */}
      <div className="flex items-center justify-between p-1">
        <h3 className="text-xs font-semibold text-gray-400 py-1">CHATS</h3>

        {/* Create new chat button */}
        <button
          onClick={onNewChat}
          className="text-xs text-gray-500 hover:text-green-400 transition-colors"
        >
          + New
        </button>
      </div>

      {/* If there are no chats, display no chat history */}
      {/* Otherwise, display all the chats in the chat array */}
      {chats.length === 0 ? (
        <div className="text-center p-3">
          {/* TODO Put some icon here */}
          <p className="text-xs text-gray-500">No chat history</p>
        </div>
      ) : (
        <div className="space-y-1">
          {chats.map((chat) => (
            <button
              key={chat.id}
              onClick={() => onChatSelect?.(chat.id)}
              className={`w-full flex p-4 rounded-lg text-left 
                      ${
                        activeChat === chat.id
                          ? "bg-gray-800/80 border border-green-600/30"
                          : "hover:bg-gray-800/20"
                      }
                    `}
            >
              <div className="flex-1">
                <div className="text-sm text-gray-200">{chat.title}</div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
