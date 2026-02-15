import { ExcelFile, Chat } from "@/util/interfaces";
import { SidebarFileDisplay } from "@/renderer/app/components/SidebarFileDisplay";
import { SidebarChatDisplay } from "./SidebarChatDisplay";
import { SidebarHeader } from "./SidebarHeader";
import { FileSpreadsheet, Settings, Upload } from "lucide-react";
import { SidebarWidget } from "./SidebarWidget";

const ACCEPTED_FILE_EXTENSIONS = ["xlsx", "xls", "csv"] as const;

// Properties needed for the sidebar
interface SidebarProperties {
  onSettingsClick: () => void;
  onFilesChange: (files: ExcelFile[]) => void;
  onChatSelect: (chatId: string) => void;
  onNewChat: () => void;
  files: ExcelFile[];
  chats: Chat[];
  activeChat?: string;
}

// Checks if a file type is valid
function isAcceptedFileType(extension: string): boolean {
  return ACCEPTED_FILE_EXTENSIONS.some(
    (ext) => ext === extension.toLowerCase(),
  );
}

// Gets the extension name of a file
function getFileExtension(fileName: string): string {
  const extension = fileName.split(".");

  if (extension.length > 1) return extension.pop()!;
  else return "";
}

export function Sidebar({
  onSettingsClick,
  onFilesChange,
  onChatSelect,
  onNewChat,
  files,
  chats,
  activeChat,
}: SidebarProperties) {
  // This uses the preload.js to open a file dialog
  // This is needed to get the file path for the selected files
  async function handleUploadClick() {
    try {
      const filePaths = await window.electronAPI.openFileDialog();

      if (filePaths && filePaths.length > 0) {
        // Filter only accepted file types
        const validFilePaths = filePaths.filter((filePath) => {
          const fileName = filePath.split(/[\\/]/).pop() || "";
          return isAcceptedFileType(getFileExtension(fileName));
        });

        if (validFilePaths.length === 0) return;

        const currentMaxIndex =
          files.length > 0 ? Math.max(...files.map((f) => f.index)) : 0;

        const excelFiles: ExcelFile[] = validFilePaths.map((filePath, idx) => {
          const fileName = filePath.split(/[\\/]/).pop() || filePath;

          return {
            id: `${Date.now()}-${idx}`,
            name: fileName,
            index: currentMaxIndex + idx + 1,
            path: filePath,
          };
        });

        onFilesChange([...files, ...excelFiles]);
      }
    } catch (error) {
      console.error("Error opening file dialog:", error);
    }
  }

  // Adds a file to the file list
  function addFiles(newFiles: File[]): void {
    const currentMaxIndex =
      files.length > 0 ? Math.max(...files.map((f) => f.index)) : 0;
    const excelFiles: ExcelFile[] = newFiles.map((file, idx) => ({
      id: `${Date.now()} - ${idx}`,
      name: file.name,
      index: currentMaxIndex + idx + 1,
      path: file.name,
    }));
    onFilesChange([...files, ...excelFiles]);
  }

  // Removes a file from the file list
  function removeFile(id: string): void {
    const updatedFiles = files.filter((f) => f.id !== id);
    const reindexedFiles = updatedFiles.map((file, idx) => ({
      ...file,
      index: idx + 1,
    }));
    onFilesChange(reindexedFiles);
  }

  // HTML for the sidebar
  return (
    <div className="w-75 bg-gray-900/80 border-r border-gray-800/50 flex flex-col h-full">
      {/* =-=-= Header =-=-=*/}
      <div className="p-3 border-b border-gray-800/50">
        {/* Logo and title */}
        <div className="flex items-center p-3 gap-3">
          <div className="w-10 h-10 rounded-lg bg-green-500 flex items-center justify-center">
            <FileSpreadsheet size={26} className="text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-base font-semibold text-white">Sheet Hero</div>
            <div className="text-xs text-green-400">Spreadsheet AI</div>
          </div>
        </div>

        {/* File dialog for selecting files */}
        <SidebarWidget
          title="Upload Files"
          onWidgetClick={handleUploadClick}
          icon={<Upload size={18} className="text-gray-400" />}
        />
      </div>

      {/* =-=-= File display =-=-= */}
      <SidebarHeader
        title="FILES"
        content={<div className="text-xs text-gray-500">{files.length}</div>}
      />

      <SidebarFileDisplay
        files={files}
        onAddFiles={addFiles}
        onRemoveFile={removeFile}
      />

      {/* =-=-= Chat display =-=-= */}
      <SidebarHeader
        title="CHATS"
        content={
          <button
            className="text-xs text-gray-500 hover:text-green-400 transition-colors"
            onClick={onNewChat}
          >
            + New
          </button>
        }
      />

      {/* Scroll container with listed chats */}
      <div className="flex-1 overflow-y-auto relative">
        <SidebarChatDisplay
          chats={chats}
          activeChat={activeChat}
          onChatSelect={onChatSelect}
          onNewChat={onNewChat}
        />
      </div>

      {/* =-=-= Footer =-=-= */}
      <div className="p-4 border-t border-gray-800/50">
        {/* Settings button */}
        <SidebarWidget
          title="Settings"
          onWidgetClick={onSettingsClick}
          icon={<Settings size={18} className="text-gray-400" />}
        />
      </div>
    </div>
  );
}
