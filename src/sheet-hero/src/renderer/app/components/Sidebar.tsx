import { ExcelFile, Chat, FILE_EXTENSIONS } from "@/util/interfaces";
import { SidebarFileDisplay } from "@/renderer/app/components/SidebarFileDisplay";
import { SidebarChatDisplay } from "./SidebarChatDisplay";
import { SidebarHeader } from "./SidebarHeader";
import { FileSpreadsheet, Settings, Upload } from "lucide-react";
import { SidebarWidget } from "./SidebarWidget";

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
  return FILE_EXTENSIONS.some((ext) => ext === extension.toLowerCase());
}

// Gets the extension name of a file
function getFileExtension(fileName: string): string {
  const extension = fileName.split(".");

  if (extension.length > 1) return extension.pop()!;
  else return "";
}

// Gets the current max index of files
function getCurrentMaxIndex(files: ExcelFile[]): number {
  if (files.length > 0) return Math.max(...files.map((f) => f.index));
  else return 0;
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
  // Handles the uploading of files manually through a file dialog
  async function handleUploadClick() {
    try {
      const filePaths = await window.electronAPI.openFileDialog();

      if (filePaths && filePaths.length > 0) {
        const validFilePaths = filePaths.filter((filePath) => {
          const fileName = filePath.split(/[\\/]/).pop() || "";
          return isAcceptedFileType(getFileExtension(fileName));
        });

        if (validFilePaths.length === 0) return;

        const excelFiles: ExcelFile[] = validFilePaths.map(
          (filePath, index) => {
            const fileName = filePath.split(/[\\/]/).pop() || filePath;

            return {
              id: `${Date.now()}-${index}`,
              name: fileName,
              index: getCurrentMaxIndex(files) + index + 1,
              path: filePath,
            };
          },
        );

        onFilesChange([...files, ...excelFiles]);
      }
    } catch (error) {
      console.error("Error opening file dialog:", error);
    }
  }

  // TODO: this does not work with drag and drop, and is not used at all with manual selection
  function addFiles(newFiles: File[]): void {
    console.log(newFiles);
  }

  // Removes a file from the file list
  function removeFile(id: string): void {
    const updatedFiles = files.filter((file) => file.id !== id);
    const reindexedFiles = updatedFiles.map((file, index) => ({
      ...file,
      index: index + 1,
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
          icon={<Upload size={18} />}
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
          icon={<Settings size={18} />}
        />
      </div>
    </div>
  );
}
