import { useState, useRef, useEffect } from "react";
import { api } from "@/util/api";
import { useSettings } from "@/util/storage";
import { Chat, ExcelFile, Message, Role } from "@/util/interfaces";
import { MessageCircle } from "lucide-react";
import { Sidebar } from "@/renderer/app/components/Sidebar";
import { AppInput } from "@/renderer/app/components/AppInput";
import { AppMessage } from "@/renderer/app/components/AppMessage";
import { SettingsPopup } from "@/renderer/app/components/SettingsPopup";
import { AppAPIOverlay } from "@/renderer/app/components/AppAPIOverlay";
import { AppTypingIndicator } from "@/renderer/app/components/AppTypingIndicator";

export default function App() {
  // Save and load settings utility
  const { settings, saveSettings } = useSettings();

  // The array of chat histories
  const [chats, setChats] = useState<Chat[]>([]);

  // The current active chat id
  const [activeChatId, setActiveChatId] = useState<string>();

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
  const scrollReference = useRef<HTMLDivElement>(null);

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
    outputDir: string,
    baseURL?: string,
  ): void {
    saveSettings({
      apiKey: apiKey,
      maxTurns: maxTurns,
      model: model,
      outputDir: outputDir,
      baseURL: baseURL || "",
    });
  }

  // Scrolls to the bottom of the dialogue box
  function scrollToBottom(): void {
    scrollReference.current?.scrollIntoView({
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
    if (words.length > 30) return words.substring(0, 30) + "...";
    else return words;
  }

  function createNewChat(): void {
    const newChat: Chat = {
      id: Date.now().toString(),
      title: "New Chat",
      messages: [],
    };
    setChats((prev) => [newChat, ...prev]);
    setActiveChatId(newChat.id);
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
                chat.messages.length === 0
                  ? generateChatTitle(content)
                  : chat.title,
            }
          : chat,
      ),
    );

    setIsTyping(true);

    try {
      let assistantContent: string;

      // Start the session if one doesnt exist, otherwise reply to the existing session
      if (isWaiting && sessionId) assistantContent = await sendReply(content);
      else assistantContent = await startConversation(content);

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

  // Creates a new session conversation
  async function startConversation(userMessage: string): Promise<string> {
    const newSessionId = Date.now().toString();
    setSessionId(newSessionId);

    const result = await api.post("/sheet-hero/start", {
      session_id: newSessionId,
      api_key: settings.apiKey,
      model: settings.model,
      max_turns: settings.maxTurns,
      base_url: settings.baseURL || "",
      output_file: settings.outputDir,
      prompt: userMessage,
      excel_paths: excelFiles.map((f) => f.path),
    });

    return processEvents(result.data.events);
  }

  // Sends a reply to an existing session
  async function sendReply(userReply: string): Promise<string> {
    const result = await api.post("/sheet-hero/reply", {
      session_id: sessionId,
      user_reply: userReply,
    });

    return processEvents(result.data.events);
  }

  // Handles specific event types from backend
  function processEvents(events: Record<string, string>[]): string {
    for (const event of events) {
      console.log(event); // testing, remove this
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

  // Renders the chat if there are existing chats with messages
  function renderChat() {
    return (
      <div className="max-w-3xl mx-auto space-y-4 py-5">
        {messages.map((message) => (
          <AppMessage
            key={message.id}
            role={message.role}
            content={message.content}
          />
        ))}
        <div ref={scrollReference} />
      </div>
    );
  }

  // Renders instructions to begin the conversation if there is an active chat but no messages
  function renderChatEmptyMessages() {
    return (
      <div className="h-full w-full flex flex-col items-center justify-center text-center px-6">
        {/* Icon */}
        <div className="bg-(--sh-green) text-(--sh-white) rounded-full p-4 mb-4">
          <MessageCircle size={36} />
        </div>

        {/* Header */}
        <h2 className="text-2xl font-bold text-(--sh-white) mb-2">
          Start the Conversation
        </h2>

        {/* Instructions */}
        <p className="text-(--sh-grey) mb-6 max-w-xs">
          Type a message below to begin chatting with SheetHero about your Excel
          files.
        </p>
      </div>
    );
  }

  // Renders instructions to create a chat if there are no existing chats
  function renderEmptyChat() {
    return (
      <div className="h-full w-full flex flex-col items-center justify-center text-center px-6">
        {/* Icon */}
        <div className="bg-(--sh-green) text-(--sh-white) rounded-full p-4 mb-4">
          <MessageCircle size={36} />
        </div>

        {/* Header */}
        <h2 className="text-2xl font-bold text-(--sh-white) mb-2">
          Create a New Conversation
        </h2>

        {/* Instructions */}
        <p className="text-(--sh-grey) mb-6 max-w-xs">
          You don’t have any chats yet. Click the New Chat button in the
          sidebar, or the button below to get started.
        </p>

        {/* Create new chat button */}
        <button
          onClick={createNewChat}
          className="px-6 py-3 bg-(--sh-green) text-(--sh-white) rounded-lg font-medium hover:bg-(--sh-green-hover) transition-colors"
        >
          + New Chat
        </button>
      </div>
    );
  }

  // HTML for the app
  return (
    <div className="h-full flex">
      {/* =-=-= Sidebar =-=-=*/}
      <Sidebar
        chats={chats}
        activeChat={activeChatId}
        files={excelFiles}
        onSettingsClick={handleSettingsClick}
        onFilesChange={setExcelFiles}
        onChatSelect={handleChatSelect}
        onNewChat={createNewChat}
      />

      {/* =-=-= Main content =-=-= */}
      <div className="flex flex-1 flex-col p-5 pl-0">
        {/* =-=-=  Main container =-=-= */}
        <div className="h-full rounded-3xl border border-(--sh-border-grey) flex flex-col overflow-hidden bg-(--sh-dark-blue)">
          <div className="flex-1 overflow-y-auto p-6 relative">
            {/* Missing API key overlay */}
            {!hasApiKey && chats.length != 0 && (
              <div className="absolute top-0 left-0 right-0 p-2">
                <AppAPIOverlay onSettingsClick={handleSettingsClick} />
              </div>
            )}

            {/* Chats container */}
            {chats.length === 0
              ? renderEmptyChat()
              : messages.length === 0
                ? renderChatEmptyMessages()
                : renderChat()}

            {/* Typing indicator */}
            {isTyping && (
              <div className="flex justify-center">
                <AppTypingIndicator />
              </div>
            )}
          </div>
          <AppInput
            onSendMessage={createNewMessage}
            hasApiKey={hasApiKey}
            isTyping={isTyping}
          />
        </div>
      </div>
      {/* =-=-= Settings =-=-= */}
      <SettingsPopup
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        onSave={handleSaveSettings}
        apiKey={settings.apiKey}
        maxTurns={settings.maxTurns}
        model={settings.model}
        baseURL={settings.baseURL}
        outputDir={settings.outputDir}
      />
    </div>
  );
}
