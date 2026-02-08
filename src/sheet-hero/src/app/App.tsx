import { useState, useRef } from "react";
import { Sidebar } from "@/app/components/Sidebar";
import { Chat, ExcelFile, Message, Role } from "@/app/Interfaces";
import { ChatMessage } from "@/app/components/ChatMessage";
import { ChatInput } from "@/app/components/ChatInput";
// import { api } from "@/api";

export default function App() {
  // The array of chat histories
  const [chats, setChats] = useState<Chat[]>([]);

  // The current active chat id
  const [activeChatId, setActiveChatId] = useState<string>("");

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

  // Handles when the settings button is clicked
  function handleSettingsClick(): void {
    console.log("Settings was clicked");
  }

  // Handles when a chat history was selected
  function handleChatSelect(chatId: string): void {
    setActiveChatId(chatId);
    console.log("Chat was selected");
  }

  // Creates a new chat
  async function createNewChat(): Promise<void> {
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

  // Creates a basic chat title for the chat history
  function generateChatTitle(firstMessage: string): string {
    const words = firstMessage.split(" ").slice(0, 4).join(" ");
    return words.length > 30 ? words.substring(0, 30) + "..." : words;
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
        <ChatInput onSendMessage={createNewMessage} disabled={isTyping} />
      </div>
    </div>
  );
}
