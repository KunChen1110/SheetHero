import { FileSpreadsheet, AlertCircle, Settings } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { Sidebar } from "@/app/components/Sidebar";
import { Chat, ExcelFile, Message, Role} from "@/app/Interfaces";

function App() {
  // The array of chat interfaces in the chat box
  const [chats, setChats] = useState<Chat[]>([]);

  // The current active chat id
  const [activeChatId, setActiveChatId] = useState<string>('1');

  // The array of excel file interfaces active being used for query
  const [excelFiles, setExcelFiles] = useState<ExcelFile[]>([]);

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
    <div className="flex h-screen p-2 gap-2">
      <Sidebar 
        onSettingsClick={handleSettingsClick}
        files={excelFiles}
        onFilesChange={setExcelFiles}
        chats={chats}
        activeChat={activeChatId}
        onChatSelect={handleChatSelect}
        onNewChat={handleNewChat}
      />

      <div className="flex flex-col flex-1 bg-dark_gray rounded-4xl p-2">
        
        <div className="flex-1 overflow-y-auto rounded-3xl bg-dark_gray"></div>

        <div className="border-t border-gray p-2"></div>

      </div>
    </div>
  );
}

export default App;