import { Chat } from "@/util/interfaces";

const CHAT_PREFIX = "chat-";

// Saves a chat to localStorage
export function saveChatToStorage(chat: Chat) {
  try {
    localStorage.setItem(`${CHAT_PREFIX}${chat.id}`, JSON.stringify(chat));
  } catch (error) {
    console.error("Failed to save chat:", error);
  }
}

// Deletes a chat from localStorage
export function deleteChatFromStorage(chatId: string) {
  try {
    localStorage.removeItem(`${CHAT_PREFIX}${chatId}`);
  } catch (error) {
    console.error("Failed to delete chat:", error);
  }
}

// Loads all chats from localStorage
export function loadAllChatsFromStorage(): Chat[] {
  const chats: Chat[] = [];

  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);

    if (key && key.startsWith(CHAT_PREFIX)) {
      try {
        const chat = JSON.parse(localStorage.getItem(key) || "");
        if (chat && chat.id && chat.messages) {
          chats.push(chat);
        }
      } catch (error) {
        console.error("Failed to parse chat:", key, error);
      }
    }
  }

  // Sort by most recent
  chats.sort((a, b) => Number(b.id) - Number(a.id));
  return chats;
}
