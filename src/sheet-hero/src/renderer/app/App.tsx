import { useState, useRef, useEffect } from "react";
import { Sidebar } from "@/renderer/app/components/Sidebar";
import { Chat, ExcelFile, Message, Role } from "@/util/interfaces";
import { ChatMessage } from "@/renderer/app/components/ChatMessage";
import { ChatInput } from "@/renderer/app/components/ChatInput";
import { Settings } from "@/renderer/app/components/Settings";
import { useSettings } from "@/util/storage";
// import { api } from "@/util/api";

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

  // If the model is considered to be typing or not
  const [isTyping, setIsTyping] = useState(false);

  // Used to ensure the chat always scrolls to the bottom of the chat box
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // The currently active chat
  const activeChat = chats.find((chat) => chat.id === activeChatId);

  // The active chat's messages, if it has any
  const messages = activeChat?.messages || [];

  // If the settings display is currently open
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

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

  // Creates a new chat
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
  }

  // Creates a new message inside of current chat
  async function createNewMessage(content: string): Promise<void> {
    const userMessage: Message = {
      id: Date.now().toString(),
      role: Role.USER,
      content,
    };

    // Update current chat with new message
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

    // Begin generating a response,

    try {
      // Wait for backend response
      const assistantContent = await generateResponse(content, excelFiles);

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: Role.ASSISTANT,
        content: assistantContent,
      };

      // Update chat with assistant message
      setChats((prevChats) =>
        prevChats.map((chat) =>
          chat.id === activeChatId
            ? { ...chat, messages: [...chat.messages, assistantMessage] }
            : chat,
        ),
      );
    } catch (error) {
      console.error(error);
    } finally {
      setIsTyping(false);
    }
  }

  // Response logic
  async function generateResponse(
    userMessage: string,
    files: ExcelFile[],
  ): Promise<string> {
    console.log(userMessage);
    console.log(files);

    // TODO This only prints the understanding output, this WILL need to be changed!!
    try {
      // const response = await api.get("/sheet-hero/run");
      // console.log(response.data);
      return (
        // response.data.result["understanding_output"] ||
        "Backend is not linked"
      );
    } catch (error) {
      console.error(error);
      return "Error: Could not get response from backend";
    }
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
        {/* =-=-= Messages container =-=-= */}
        <div className="h-full rounded-3xl border border-gray-700/50 flex flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto p-6">
            {/* =-=-=  No API key overlay =-=-=  */}
            {!hasApiKey && (
              <div className="bg-linear-to-r from-yellow-900/40 to-red-900/40 border-b border-yellow-600/30 backdrop-blur-sm rounded-3xl">
                <div className="max-w-4xl mx-auto p-5">
                  <div className="flex items-start">
                    <div className="flex-1">
                      <h3 className="text-sm font-semibold text-yellow-200">
                        API Key Required
                      </h3>
                      <p className="text-sm text-yellow-100/80 py-2">
                        Please configure your API key in settings to start
                        usings SheetHero.
                      </p>
                      <button
                        onClick={handleSettingsClick}
                        className="p-3 bg-yellow-600 hover:bg-yellow-700 text-white text-sm font-medium rounded-lg transition-colors shadow-lg"
                      >
                        Open Settings
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div className="max-w-4xl mx-auto space-y-2">
              {messages.map((message) => (
                <ChatMessage
                  key={message.id}
                  role={message.role}
                  content={message.content}
                />
              ))}
              <div ref={messagesEndRef} />
            </div>
          </div>
        </div>
        <ChatInput
          onSendMessage={createNewMessage}
          disabled={isTyping || !hasApiKey}
        />
      </div>
      {/* =-=-= Settings =-=-= */}
      <Settings
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
