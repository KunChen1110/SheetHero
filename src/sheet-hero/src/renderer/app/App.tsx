import { useState, useRef, useEffect } from "react";
import { Sidebar } from "@/renderer/app/components/Sidebar";
import { Chat, ExcelFile, Message, Role } from "@/util/interfaces";
import { AppMessage } from "@/renderer/app/components/AppMessage";
import { AppInput } from "@/renderer/app/components/AppInput";
import { SettingsPopup } from "@/renderer/app/components/SettingsPopup";
import { AppAPIOverlay } from "./components/AppAPIOverlay";
import { useSettings } from "@/util/storage";
import { api } from "@/util/api";

const DEFAULT_CHAT: Chat = {
  id: Date.now().toString(),
  title: "Getting Started",
  messages: [
    {
      id: Date.now().toString(),
      role: Role.ASSISTANT,
      content:
        "Hello! I'm SheetHero. Upload or drag & drop your Excel files to get started!",
    },
  ],
};

export default function App() {
  // Save and load settings utility
  const { settings, saveSettings } = useSettings();

  // The array of chat histories
  const [chats, setChats] = useState<Chat[]>([DEFAULT_CHAT]);

  // The current active chat id
  const [activeChatId, setActiveChatId] = useState<string>(DEFAULT_CHAT.id);

  // The array of excel file interfaces active being used for query
  const [excelFiles, setExcelFiles] = useState<ExcelFile[]>([]);

  // If the model is considered to be typing
  const [isTyping, setIsTyping] = useState(false);

  // If the model is considered to be waiting for a reply from the user
  const [isWaiting, setIsWaiting] = useState(false);

  // If the settings display is currently open
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  // The session id in use, used for individual backend sessions
  const [sessionId, setSessionId] = useState<string | null>(null);

  // Reference used to scroll to the bottom of the chat box
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // The currently active chat
  const activeChat = chats.find((chat) => chat.id === activeChatId);

  // The active chat's messages, if it has any
  const messages = activeChat?.messages || [];

  // If there is an API key in use
  const hasApiKey = settings.apiKey.trim().length > 0;

  // Handles when the settings button is clicked
  function handleSettingsClick(): void {
    setIsSettingsOpen(true);
  }

  // Handles when a chat history was selected
  function handleChatSelect(chatId: string): void {
    setActiveChatId(chatId);
  }

  // Handles when the settings are saved
  function handleSaveSettings(
    apiKey: string,
    maxTurns: number,
    model: string,
  ): void {
    saveSettings({
      apiKey: apiKey,
      maxTurns: maxTurns,
      model: model,
    });
  }

  // Scrolls to the bottom of the dialogue box
  function scrollToBottom(): void {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }

  // Automatically scrolls to the bottom of the dialogue box after typing or new message creation
  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  // Creates a basic chat title for the chat history
  function generateChatTitle(firstMessage: string): string {
    const words = firstMessage.split(" ").slice(0, 4).join(" ");
    return words.length > 30 ? words.substring(0, 30) + "..." : words;
  }

  function createNewChat(): void {
    const newChat: Chat = {
      id: Date.now().toString(),
      title: "New Chat",
      messages: [
        {
          id: Date.now().toString(),
          role: Role.ASSISTANT,
          content: "How can I help you today?",
        },
      ],
    };
    setChats((prev) => [newChat, ...prev]);
    setActiveChatId(newChat.id);
    // Reset session for new chat
    setSessionId(null);
    setIsWaiting(false);
  }

  async function createNewMessage(content: string): Promise<void> {
    const userMessage: Message = {
      id: Date.now().toString(),
      role: Role.USER,
      content,
    };

    setChats((prevChats) =>
      prevChats.map((chat) =>
        chat.id === activeChatId
          ? {
              ...chat,
              messages: [...chat.messages, userMessage],
              title:
                chat.messages.length === 1
                  ? generateChatTitle(content)
                  : chat.title,
            }
          : chat,
      ),
    );

    setIsTyping(true);

    try {
      let assistantContent: string;

      if (isWaiting && sessionId) {
        // This is a reply to a clarification question
        assistantContent = await sendReply(content);
      } else {
        // This is a new conversation start
        assistantContent = await startConversation(content);
      }

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: Role.ASSISTANT,
        content: assistantContent,
      };

      setChats((prevChats) =>
        prevChats.map((chat) =>
          chat.id === activeChatId
            ? { ...chat, messages: [...chat.messages, assistantMessage] }
            : chat,
        ),
      );
    } catch (error) {
      console.error(error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: Role.ASSISTANT,
        content: "Error: Could not get response from backend",
      };
      setChats((prevChats) =>
        prevChats.map((chat) =>
          chat.id === activeChatId
            ? { ...chat, messages: [...chat.messages, errorMessage] }
            : chat,
        ),
      );
    } finally {
      setIsTyping(false);
    }
  }

  async function startConversation(userMessage: string): Promise<string> {
    const newSessionId = Date.now().toString();
    setSessionId(newSessionId);

    const result = await api.post("/sheet-hero/start", {
      session_id: newSessionId,
      api_key: settings.apiKey,
      model: settings.model,
      max_turns: settings.maxTurns,
      prompt: userMessage,
      excel_paths: excelFiles.map((f) => f.path),
    });

    return processEvents(result.data.events);
  }

  async function sendReply(userReply: string): Promise<string> {
    if (!sessionId) {
      throw new Error("No active session");
    }

    const result = await api.post("/sheet-hero/reply", {
      session_id: sessionId,
      user_reply: userReply,
    });

    return processEvents(result.data.events);
  }

  function processEvents(events: Record<string, string>[]): string {
    for (const event of events) {
      const type = event.type;

      if (type === "clarification") {
        setIsWaiting(true);
        return event.message;
      }

      if (type === "final" || type === "error") {
        setIsWaiting(false);
        if (sessionId) {
          api.delete(`/sheet-hero/session/${sessionId}`).catch(console.error);
          setSessionId(null);
        }
        return event.message;
      }
    }

    return "Processing...";
  }

  // HTML for the app
  return (
    <div className="h-full flex bg-gray-950">
      {/* =-=-= Sidebar =-=-=*/}
      <Sidebar
        onSettingsClick={handleSettingsClick}
        files={excelFiles}
        onFilesChange={setExcelFiles}
        chats={chats}
        activeChat={activeChatId}
        onChatSelect={handleChatSelect}
        onNewChat={createNewChat}
      />

      {/* =-=-= Main chat =-=-= */}
      <div className="flex flex-1 flex-col p-12 pb-0">
        <div className="h-full rounded-3xl border border-gray-700/50 flex flex-col overflow-hidden bg-gray-900">
          <div className="flex-1 overflow-y-auto p-6">
            {/* =-=-=  Missing API key overlay =-=-=  */}
            {!hasApiKey && (
              <AppAPIOverlay onSettingsClick={handleSettingsClick} />
            )}
            <div className="max-w-4xl mx-auto space-y-5 py-5">
              {/* =-=-=  Messages container =-=-=  */}
              {messages.map((message) => (
                <AppMessage
                  key={message.id}
                  role={message.role}
                  content={message.content}
                />
              ))}
              <div ref={messagesEndRef} />
            </div>
          </div>
        </div>
        <AppInput
          onSendMessage={createNewMessage}
          disabled={isTyping || !hasApiKey}
        />
      </div>
      {/* =-=-= Settings =-=-= */}
      <SettingsPopup
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        apiKey={settings.apiKey}
        maxTurns={settings.maxTurns}
        model={settings.model}
        onSave={handleSaveSettings}
      />
    </div>
  );
}
