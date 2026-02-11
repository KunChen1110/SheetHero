import { useRef } from "react";
import { ExcelFile, Chat } from "@/util/interfaces";
import { FileDisplay } from "@/renderer/app/components/FileDisplay";
import { ChatDisplay } from "./ChatDisplay";

const ACCEPTED_FILE_EXTENSIONS = ["xlsx", "xls", "csv"] as const;

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

// Returns all file extensions, used for file dialog
function getAcceptAttribute(): string {
  return [...ACCEPTED_FILE_EXTENSIONS].map((ext) => `.${ext}`).join(",");
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
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Handles when files are selected from the file dialog
  function handleFileSelect(event: React.ChangeEvent<HTMLInputElement>): void {
    const selectedFiles = Array.from(event.target.files || []).filter((file) =>
      isAcceptedFileType(getFileExtension(file.name)),
    );

    if (selectedFiles.length === 0) return;

    addFiles(selectedFiles);

    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  // Adds a file to the file list
  function addFiles(newFiles: File[]): void {
    const currentMaxIndex =
      files.length > 0 ? Math.max(...files.map((f) => f.index)) : 0;
    const excelFiles: ExcelFile[] = newFiles.map((file, idx) => ({
      id: `${Date.now()} - ${idx}`,
      name: file.name,
      index: currentMaxIndex + idx + 1,
      file,
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
      <div className="p-4 border-b border-gray-800/50">
        <div className="flex items-center p-3">
          <div className="flex-1 min-w-0">
            <div className="text-base font-semibold text-white">Sheet Hero</div>
            <div className="text-xs text-green-400">Spreadsheet AI</div>

            {/* TODO Put logo or smtnh here */}
          </div>
        </div>

        {/* File dialog for selecting files */}
        <input
          className="hidden"
          type="file"
          multiple
          accept={getAcceptAttribute()}
          onChange={handleFileSelect}
          ref={fileInputRef}
        />

        <button
          onClick={() => fileInputRef.current?.click()}
          className="flex w-full items-center bg-gray-900 p-4 rounded-lg border border-gray-700/50 text-white hover:border-green-600/30 hover:bg-gray-800/80 transition-all"
        >
          <span className="text-sm font-medium">Upload Files</span>
        </button>
      </div>

      {/* =-=-= Scrollable area for files & chat history =-=-= */}
      <div className="flex-1 overflow-y-auto relative">
        {/* =-=-= File display =-=-= */}
        <FileDisplay
          files={files}
          onAddFiles={addFiles}
          onRemoveFile={removeFile}
        />

        {/* =-=-= Chat display =-=-= */}
        <ChatDisplay
          chats={chats}
          activeChat={activeChat}
          onChatSelect={onChatSelect}
          onNewChat={onNewChat}
        />
      </div>

      {/* =-=-= Footer =-=-= */}
      <div className="p-4 border-t border-gray-800/50">
        {/* Settings button */}
        <button
          className="w-full flex items-center p-4 rounded-lg bg-gray-900 hover:bg-gray-800/80 border border-gray-700/50 hover:border-green-600/20 transition-all"
          onClick={onSettingsClick}
        >
          {/* TODO Put settings icon here */}

          <span className="text-sm text-gray-200">Settings</span>
        </button>
      </div>
    </div>
  );
}
