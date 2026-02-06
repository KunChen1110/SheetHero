import { useState, useRef } from "react";
import { Sidebar } from "@/app/components/Sidebar";
import { Chat, ExcelFile, Message, Role } from "@/app/Interfaces";
import { ChatMessage } from "@/app/components/ChatMessage";
import { ChatInput } from "@/app/components/ChatInput";

export default function App() {
  // The array of chat histories
  const [chats, setChats] = useState<Chat[]>([]);

  // The current active chat id
  const [activeChatId, setActiveChatId] = useState<string>("1");

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

  function handleSettingsClick(): void {
    console.log("Settings was clicked");
  }

  function handleChatSelect(): void {
    console.log("Chat was selected");
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
  function createNewMessage(content: string): void {
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

    // Simulate AI response delay, this is kinda stupid but it looks cool lmao
    setTimeout(
      () => {
        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: Role.ASSISTANT,
          content: generateResponse(content, excelFiles),
        };

        setChats((prevChats) =>
          prevChats.map((chat) =>
            chat.id === activeChatId
              ? { ...chat, messages: [...chat.messages, assistantMessage] }
              : chat,
          ),
        );
        setIsTyping(false);
      },
      Math.random() * 500 + 1000,
    );
  }

  // Creates a basic chat title for the chat history
  function generateChatTitle(firstMessage: string): string {
    const words = firstMessage.split(" ").slice(0, 4).join(" ");
    return words.length > 30 ? words.substring(0, 30) + "..." : words;
  }

  // Response logic goes here
  function generateResponse(userMessage: string, files: ExcelFile[]): string {
    const lowerMessage = userMessage.toLowerCase();
    console.log(files);
    return lowerMessage;
  }

  return (
    <div className="h-full flex">
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
      <div className="flex-1 flex flex-col relative">
        <div className="flex-1 overflow-y-auto relative z-1">
          <div className="h-full p-12 pb-0">
            <div className="h-full rounded-3xl overflow-y-auto shadow-2xl border border-gray-700/50">
              {/* =-=-= Messages =-=-=*/}
              <div className="max-w-4xl mx-auto pt-">
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
        </div>
        {/* =-=-= Chat input =-=-=*/}
        <ChatInput onSendMessage={createNewMessage} disabled={isTyping} />
      </div>
    </div>
  );
}
