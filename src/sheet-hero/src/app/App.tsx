import { useState, useRef, useEffect } from "react";
import { Sidebar } from "@/app/components/Sidebar";
import { Chat, ExcelFile, Message, Role} from "@/app/Interfaces";

export default function App() {
  // The array of chat interfaces in the chat box
  const [chats, setChats] = useState<Chat[]>([]);

  // The current active chat id
  const [activeChatId, setActiveChatId] = useState<string>('1');

  // The array of excel file interfaces active being used for query
  const [excelFiles, setExcelFiles] = useState<ExcelFile[]>([]);

  // Used to ensure the chat always scrolls to the bottom of the chat box
  const messagesEndRef = useRef<HTMLDivElement>(null);

  function handleSettingsClick(): void {
    console.log("Settings was clicked");
  }

  function handleChatSelect(): void {
    console.log("Chat was selected");
  }
  
  function handleNewChat(): void {
    console.log("New chat created");
  }

  return (
    <div className="h-full flex bg-linear-to-br">
      {/* =-=-= Sidebar =-=-=*/}
      <Sidebar 
        onSettingsClick={handleSettingsClick}
        files={excelFiles}
        onFilesChange={setExcelFiles}
        chats={chats}
        activeChat={activeChatId}
        onChatSelect={handleChatSelect}
        onNewChat={handleNewChat}
      />

      {/* =-=-= Main chat =-=-= */}
      <div className="flex-1 flex flex-col relative">
        
        {/* =-=-= Messages =-=-=*/}
        <div className="flex-1 overflow-y-auto relative z-10">
          <div className="h-full p-12 pb-0">
            <div className="max-w-4xl mx-auto pt-8">
              <div ref={messagesEndRef}/>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}